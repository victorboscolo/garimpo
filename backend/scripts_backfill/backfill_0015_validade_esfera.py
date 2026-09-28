"""Preenche `data_fim`/`data_inicio` em promoções da Esfera já gravadas,
extraindo do `regulamento_texto` que já está salvo no banco.

Existe porque a extração nova (coletor-esfera/esfera_api.py::_extrair_validade,
28/09/2026) só ajuda promoções coletadas dali pra frente — recoletar não
resolve o que já está gravado quando a própria fonte já trocou o texto do
regulamento por um genérico sem data (achado real: Rentcars, "válidas ...
até 27/09/2026" no regulamento salvo, mas o site já não mostra mais essa
frase hoje). O texto antigo continua no banco; só faltava ler dele.

Mesmo regex do coletor, aplicado ao texto já salvo — não busca nada na rede.
Só preenche quando `data_fim` está vazio (mesma regra de
`_completar_dados_da_campanha`: nunca sobrescreve o que já existe).

Uso:
    docker compose exec backend python -m scripts_backfill.backfill_0015_validade_esfera
    docker compose exec backend python -m scripts_backfill.backfill_0015_validade_esfera --aplicar
"""
import asyncio
import re
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from domain import governanca  # noqa: F401 — resolve a FK de promocoes.aprovada_por
from domain.cadastros import Programa
from domain.promocoes import Promocao
from infrastructure.db.session import AsyncSessionLocal

_PADRAO_VALIDADE_COMPLETA = re.compile(
    r"v[áa]lidas?[^.]*?de\s+\d{1,2}h\d{2}min?\s+do\s+dia\s+(\d{1,2}/\d{1,2}/\d{4})"
    r"\s+até\s+\d{1,2}h\d{2}min?\s+do\s+dia\s+(\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)
_PADRAO_VALIDADE_SO_FIM = re.compile(r"v[áa]lidas?[^.]*?até\s+(\d{1,2}/\d{1,2}/\d{4})", re.IGNORECASE)


def _data(texto: str) -> datetime:
    # `data_fim`/`data_inicio` são DateTime no banco (não Date) — mesma
    # convenção do resto do sistema (meia-noite UTC do dia informado).
    dia, mes, ano = texto.split("/")
    return datetime(int(ano), int(mes), int(dia), tzinfo=timezone.utc)


def _extrair_validade(regulamento: str | None) -> tuple[datetime | None, datetime | None]:
    if not regulamento:
        return None, None
    m = _PADRAO_VALIDADE_COMPLETA.search(regulamento)
    if m:
        return _data(m.group(1)), _data(m.group(2))
    m = _PADRAO_VALIDADE_SO_FIM.search(regulamento)
    if m:
        return None, _data(m.group(1))
    return None, None


async def executar(aplicar: bool) -> None:
    async with AsyncSessionLocal() as db:
        programa = (await db.execute(select(Programa).filter_by(nome="Esfera"))).scalar_one_or_none()
        if programa is None:
            print("Programa 'Esfera' não encontrado.")
            return

        promocoes = (await db.execute(
            select(Promocao).filter(
                Promocao.programa_id == programa.id,
                Promocao.data_fim.is_(None),
                Promocao.regulamento_texto.is_not(None),
            )
        )).scalars().all()

        candidatas = 0
        for promocao in promocoes:
            try:
                inicio, fim = _extrair_validade(promocao.regulamento_texto)
            except ValueError as e:
                print(f"  IGNORADA (data inválida no regulamento) {promocao.titulo}: {e}")
                continue
            if fim is None:
                continue
            candidatas += 1
            print(f"  {promocao.titulo}: data_fim -> {fim.date()}" + (f", data_inicio -> {inicio.date()}" if inicio else ""))
            if aplicar:
                promocao.data_fim = fim
                if inicio is not None:
                    promocao.data_inicio = inicio

        print(f"\n{len(promocoes)} promoções da Esfera sem data_fim examinadas, {candidatas} com validade extraível do regulamento salvo.")
        if aplicar:
            await db.commit()
            print("APLICADO.")
        else:
            print("SIMULAÇÃO — nada foi gravado. Rode com --aplicar para valer.")


if __name__ == "__main__":
    asyncio.run(executar(aplicar="--aplicar" in sys.argv))
