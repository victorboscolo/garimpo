"""Backfill da pontuação do Clube após a migration 0004.

Mesma estrutura e mesmos cuidados do backfill_0003: roda em Python para usar a
`calcular_hash` da própria aplicação, porque a coluna nova entra na fórmula de
deduplicação e um hash divergente faria a coleta seguinte tratar as ofertas
existentes como novas.

Uso:
    docker compose exec backend python -m scripts_backfill.backfill_0004
    docker compose exec backend python -m scripts_backfill.backfill_0004 --aplicar
"""
import asyncio
import sys
from decimal import Decimal

from sqlalchemy import select

from application.ingestao_service import PromocaoBrutaIn, calcular_hash
from domain.cadastros import Parceiro, Programa
from domain.promocoes import Promocao
from infrastructure.db.session import AsyncSessionLocal

from scripts_backfill.backfill_0003 import _slug_e_codigo

# Cards da Livelo com variante de Clube, capturados em 13/08/2026.
# (slug/codigo, pontuação de qualquer cliente, pontuação do Clube).
#
# A pontuação base entra na chave para que o valor do Clube só seja aplicado
# quando a oferta no banco for reconhecidamente a mesma que está no ar hoje.
OFERTAS_COM_CLUBE = [
    ("aliexpress/ALB", 1, 3), ("beleza-na-web/BLZ", 8, 10),
    ("clube-bancorbras/BCR", 25, 28), ("coffee-mais/CFF", 4, 10),
    ("giuliana-flores/GFL", 3, 5), ("hope/HPE", 2, 3),
    ("hoteis/HTC", 3, 4), ("imaginarium/IMG", 1, 2),
    ("mondaine/MDN", 12, 15), ("olympikus/OVC", 5, 15),
    ("pet-love-saude/PVS", 20, 22), ("pontofrio/PTF", 3, 4),
    ("puket/PKT", 2, 3), ("speedo/SPD", 2, 4),
    ("trocafy/ALD", 1, 2),
]


async def executar(aplicar: bool) -> None:
    clube = {(chave, Decimal(base)): Decimal(valor) for chave, base, valor in OFERTAS_COM_CLUBE}

    async with AsyncSessionLocal() as db:
        promocoes = (await db.execute(select(Promocao))).scalars().unique().all()
        parceiros = {p.id: p for p in (await db.execute(select(Parceiro))).scalars().all()}
        programas = {p.id: p for p in (await db.execute(select(Programa))).scalars().all()}

        preenchidas = 0
        for promocao in promocoes:
            slug, codigo = _slug_e_codigo(promocao.url_origem)
            if slug is None or codigo is None:
                continue
            valor = clube.get((f"{slug}/{codigo}", promocao.pontuacao))
            if valor is not None and promocao.pontuacao_clube != valor:
                print(f"  {parceiros[promocao.parceiro_id].nome}: {promocao.pontuacao} → Clube {valor}")
                preenchidas += 1
                if aplicar:
                    promocao.pontuacao_clube = valor

        recalculados = 0
        for promocao in promocoes:
            _, codigo = _slug_e_codigo(promocao.url_origem)
            novo_hash = calcular_hash(PromocaoBrutaIn(
                programa_nome=programas[promocao.programa_id].nome,
                parceiro_nome_bruto=parceiros[promocao.parceiro_id].nome,
                titulo=promocao.titulo,
                url_origem=promocao.url_origem,
                pontuacao=Decimal(int(promocao.pontuacao)),
                unidade_pontuacao=promocao.unidade_pontuacao,
                requer_clube=promocao.requer_clube,
                qual_clube=promocao.qual_clube,
                requer_cupom=promocao.requer_cupom,
                cupom=promocao.cupom,
                pontuacao_e_teto=promocao.pontuacao_e_teto,
                # O coletor envia o inteiro do card; o banco guarda Numeric.
                pontuacao_clube=(
                    Decimal(int(promocao.pontuacao_clube))
                    if promocao.pontuacao_clube is not None else None
                ),
                codigo_externo=codigo,
            ))
            if promocao.hash_promocao != novo_hash:
                recalculados += 1
                if aplicar:
                    promocao.hash_promocao = novo_hash

        print()
        print(f"  promoções com pontuação de Clube: {preenchidas}")
        print(f"  hashes recalculados:              {recalculados}")

        if aplicar:
            await db.commit()
            print("\n  APLICADO.")
        else:
            print("\n  SIMULAÇÃO — nada foi gravado. Rode com --aplicar para valer.")


if __name__ == "__main__":
    asyncio.run(executar(aplicar="--aplicar" in sys.argv))
