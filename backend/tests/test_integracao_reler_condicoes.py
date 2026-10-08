"""Teste de integração: reler o piso das condicionadas sem reprocessar tudo.

Quando a regra de leitura do regulamento muda, o piso já gravado fica com a
leitura antiga. Achado do usuário (08/10): o Sam's Club a 150 pontos saía
com a mesma nota das campanhas de 40 e 84, porque o "ou 14 pontos" do outro
plano tinha sido gravado como piso de todas elas.
"""
import uuid
from decimal import Decimal

from domain.cadastros import Dominio, Programa
from domain.promocoes import Promocao

REGULAMENTO = (
    "Campanha válida de 08 a 12/10/2026. Ganhe 150 pontos por real sob o valor da "
    "anuidade ao se tornar sócio do plano de R$95,00 ou 14 pontos por real sob a adesão "
    "do plano de R$175. Consulte o regulamento."
)


async def _seed_programa(db):
    dominio = Dominio(nome="PROMOCOES")
    db.add(dominio)
    await db.flush()
    db.add(Programa(dominio_id=dominio.id, nome="Livelo"))
    await db.commit()


async def test_piso_gravado_com_a_regra_antiga_e_relido_e_a_oferta_reclassificada(db, client):
    await _seed_programa(db)
    resposta = await client.post("/api/v1/promocoes/ingerir", json=dict(
        programa_nome="Livelo", parceiro_nome_bruto="Clube de Compras",
        titulo="Clube de Compras - 150 pontos",
        url_origem="https://livelo.com.br/clube-de-compras", pontuacao="150",
        unidade_pontuacao="pontos_por_real", regulamento_texto=REGULAMENTO,
        origem_detalhe="teste-integracao",
    ))
    promocao = await db.get(Promocao, uuid.UUID(resposta.json()["id"]))
    assert promocao.valor_condicionado is True
    # Simula o que está no banco de produção: piso lido pela regra antiga.
    promocao.valor_condicionado_piso = Decimal("14")
    await db.commit()

    resultado = (await client.post("/api/v1/promocoes/reler-condicoes")).json()

    assert resultado["pisos_alterados"] == 1
    assert resultado["reclassificadas"] == 1
    assert Decimal(resultado["itens"][0]["piso_antes"]) == Decimal("14")
    assert resultado["itens"][0]["piso_depois"] is None
    await db.refresh(promocao)
    assert promocao.valor_condicionado_piso is None


async def test_sem_nada_a_corrigir_nao_reclassifica(db, client):
    await _seed_programa(db)
    await client.post("/api/v1/promocoes/ingerir", json=dict(
        programa_nome="Livelo", parceiro_nome_bruto="Clube de Compras",
        titulo="Clube de Compras - 150 pontos",
        url_origem="https://livelo.com.br/clube-de-compras", pontuacao="150",
        unidade_pontuacao="pontos_por_real", regulamento_texto=REGULAMENTO,
        origem_detalhe="teste-integracao",
    ))

    resultado = (await client.post("/api/v1/promocoes/reler-condicoes")).json()

    assert resultado["pisos_alterados"] == 0
    assert resultado["reclassificadas"] == 0
