"""Backfill dos dados existentes após a migration 0003.

Roda uma vez, é idempotente e imprime um relatório do que mudou. Separado da
migration de propósito: precisa da função `calcular_hash` da aplicação para que
os hashes recalculados sejam idênticos aos que a próxima coleta vai produzir —
replicar a fórmula em SQL abriria espaço para divergência silenciosa, e o
sintoma seria o pior possível (a coleta seguinte trataria as 248 ofertas como
novas e duplicaria o histórico já curado à mão).

Uso:
    docker compose exec backend python -m scripts_backfill.backfill_0003
    docker compose exec backend python -m scripts_backfill.backfill_0003 --aplicar

Sem --aplicar, apenas simula e mostra o que faria.
"""
import asyncio
import sys
from decimal import Decimal

from sqlalchemy import select

from application.ingestao_service import PromocaoBrutaIn, calcular_hash
from domain.cadastros import Marca, Parceiro, Programa
from domain.promocoes import Promocao
from infrastructure.db.session import AsyncSessionLocal

# Ofertas anunciadas como "Até X pontos" na listagem da Livelo, capturadas do
# site em 13/08/2026. Cada item é (slug/codigo, pontuação anunciada).
#
# A marca só é aplicada quando a promoção no banco bate com slug/codigo E
# pontuação — ou seja, quando é reconhecidamente a mesma oferta ainda no ar.
# Registros de dias anteriores com outra pontuação ficam como estão: não
# observamos o texto do card naquela data e não cabe afirmar retroativamente.
OFERTAS_COM_TETO = [
    ("aliexpress/ALB", 1), ("avon/AVN", 6), ("beleza-na-web/BLZ", 8),
    ("buser/BSR", 2), ("cabana-magazine/GRM", 1), ("carrefour/CRM", 6),
    ("cartao-de-todos/TOD", 2), ("cea/CEA", 6), ("coffee-mais/CFF", 4),
    ("consorcio-magalu/MGC", 30), ("decathlon/DCH", 2), ("eudora/EUD", 6),
    ("extra/EXT", 5), ("fast-shop/FST", 5), ("gocase/GCS", 2),
    ("klubi-auto/AUT", 40), ("klubi-celular/KLU", 40), ("klubi-imovel/IMO", 40),
    ("klubi-moto/MOT", 40), ("klubi-viagem/VIA", 40), ("liga-vitoria/LVC", 100),
    ("localiza/LCR", 4), ("mondaine/MDN", 12), ("mycon/MYC", 32),
    ("natura/NTR", 4), ("o-boticario/BOT", 8), ("perfec-tdraft/ABV", 1),
    ("pet-love-saude/PVS", 20), ("porto-servico/PTO", 11), ("portoseguro/POT", 20),
    ("seculus/SCL", 10), ("shopee/PEE", 2), ("under-armour/VCA", 15),
]

# Significado das variantes informado pelo usuário. Só entra aqui o que foi dito
# explicitamente — os códigos não são decifráveis sozinhos (BHP é Ingressos, não
# "Beach Park Hotéis", como a sigla sugeriria).
NOMES_DE_EXIBICAO = {
    ("beach park", "BPK"): "Beach Park Hotéis",
    ("beach park", "BHP"): "Beach Park Ingressos",
}


def _slug_e_codigo(url: str) -> tuple[str | None, str | None]:
    if "/parceiros/" not in url:
        return None, None
    resto = url.split("/parceiros/", 1)[1].strip().rstrip("/")
    partes = [p.strip() for p in resto.split("/") if p.strip()]
    if len(partes) < 2:
        return (partes[0] if partes else None), None
    return partes[0], partes[1]


async def executar(aplicar: bool) -> None:
    com_teto = {(chave, Decimal(valor)) for chave, valor in OFERTAS_COM_TETO}

    async with AsyncSessionLocal() as db:
        promocoes = (await db.execute(select(Promocao))).scalars().unique().all()
        parceiros = {p.id: p for p in (await db.execute(select(Parceiro))).scalars().all()}
        programas = {p.id: p for p in (await db.execute(select(Programa))).scalars().all()}

        # 1. Código da variante em cada parceiro, e separação dos slugs que
        #    hoje colapsam ofertas distintas num parceiro só.
        codigos_por_parceiro: dict = {}
        for promocao in promocoes:
            slug, codigo = _slug_e_codigo(promocao.url_origem)
            if codigo is None:
                continue
            codigos_por_parceiro.setdefault(promocao.parceiro_id, set()).add((slug, codigo))

        criados = 0
        movidas = 0
        for parceiro_id, pares in codigos_por_parceiro.items():
            parceiro = parceiros[parceiro_id]
            ordenados = sorted(pares, key=lambda par: par[1])
            slug_principal, codigo_principal = ordenados[0]

            if parceiro.codigo_externo != codigo_principal:
                print(f"  parceiro '{parceiro.nome}': codigo_externo := {codigo_principal}")
                if aplicar:
                    parceiro.codigo_externo = codigo_principal
            chave_nome = (parceiro.nome_normalizado, codigo_principal)
            if chave_nome in NOMES_DE_EXIBICAO and aplicar:
                parceiro.nome_exibicao = NOMES_DE_EXIBICAO[chave_nome]

            # Códigos extras do mesmo nome viram parceiros próprios.
            for slug, codigo in ordenados[1:]:
                alvo = [
                    promocao for promocao in promocoes
                    if promocao.parceiro_id == parceiro_id
                    and _slug_e_codigo(promocao.url_origem)[1] == codigo
                ]
                exibicao = NOMES_DE_EXIBICAO.get((parceiro.nome_normalizado, codigo))
                print(
                    f"  SEPARANDO '{parceiro.nome}' variante {codigo}"
                    f"{' → ' + exibicao if exibicao else ''}: {len(alvo)} promoção(ões)"
                )
                criados += 1
                movidas += len(alvo)
                if not aplicar:
                    continue

                marca = Marca(nome=parceiro.nome)
                db.add(marca)
                await db.flush()
                novo = Parceiro(
                    marca_id=marca.id,
                    nome=parceiro.nome,
                    nome_normalizado=parceiro.nome_normalizado,
                    codigo_externo=codigo,
                    categoria_id=parceiro.categoria_id,
                    nome_exibicao=exibicao,
                )
                db.add(novo)
                await db.flush()
                parceiros[novo.id] = novo
                for promocao in alvo:
                    promocao.parceiro_id = novo.id

        if aplicar:
            await db.flush()

        # 2. Marca de teto, só onde a oferta atual bate com o card de hoje.
        marcadas = 0
        for promocao in promocoes:
            slug, codigo = _slug_e_codigo(promocao.url_origem)
            if slug is None or codigo is None:
                continue
            if (f"{slug}/{codigo}", promocao.pontuacao) in com_teto and not promocao.pontuacao_e_teto:
                marcadas += 1
                if aplicar:
                    promocao.pontuacao_e_teto = True

        # 3. Recálculo dos hashes com a fórmula nova. Sem isto, a próxima
        #    coleta não reconheceria nenhuma oferta existente.
        recalculados = 0
        for promocao in promocoes:
            parceiro = parceiros[promocao.parceiro_id]
            _, codigo = _slug_e_codigo(promocao.url_origem)
            novo_hash = calcular_hash(PromocaoBrutaIn(
                programa_nome=programas[promocao.programa_id].nome,
                parceiro_nome_bruto=parceiro.nome,
                titulo=promocao.titulo,
                url_origem=promocao.url_origem,
                # A coleta envia o inteiro do card ("6"); o banco guarda
                # Numeric(10,2) ("6.00"). Normaliza para o hash bater.
                pontuacao=Decimal(int(promocao.pontuacao)),
                unidade_pontuacao=promocao.unidade_pontuacao,
                requer_clube=promocao.requer_clube,
                qual_clube=promocao.qual_clube,
                requer_cupom=promocao.requer_cupom,
                cupom=promocao.cupom,
                pontuacao_e_teto=promocao.pontuacao_e_teto,
                codigo_externo=codigo,
            ))
            if promocao.hash_promocao != novo_hash:
                recalculados += 1
                if aplicar:
                    promocao.hash_promocao = novo_hash

        print()
        print(f"  parceiros novos (variantes separadas): {criados}")
        print(f"  promoções reassociadas:                {movidas}")
        print(f"  promoções marcadas como teto:          {marcadas}")
        print(f"  hashes recalculados:                   {recalculados}")

        if aplicar:
            await db.commit()
            print("\n  APLICADO.")
        else:
            print("\n  SIMULAÇÃO — nada foi gravado. Rode com --aplicar para valer.")


if __name__ == "__main__":
    asyncio.run(executar(aplicar="--aplicar" in sys.argv))
