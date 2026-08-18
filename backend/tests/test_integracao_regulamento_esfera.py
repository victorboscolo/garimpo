"""Teste de integração: regulamento real da Esfera não é tratado como placeholder.

Regressão do bug corrigido em `ingestao_service._tem_regulamento_real`: a
checagem procurava a frase "campanha válida", específica da Livelo, então todo
regulamento genuíno da Esfera (que nunca usa essa frase) era tratado como se
fosse o placeholder do coletor antigo. Isso não corrompia o valor gravado por
acidente — mas fazia toda coleta duplicada reescrever `regulamento_texto` à
toa, e o painel nunca mostrava o bloco de regulamento para nenhum dos 168
parceiros da Esfera. `test_completar_dados_campanha.py` já cobre a função em
isolamento; este teste roda o mesmo caminho pela API e pelo banco reais, que é
onde o bug apareceu de fato.
"""
from sqlalchemy import select

from domain.cadastros import Dominio, Programa
from domain.promocoes import Promocao

PLACEHOLDER = "Coletado do site oficial da Esfera em 18/08/2026, sem regulamento estruturado disponível."
REGULAMENTO_REAL_1 = (
    "Válido para compras no site oficial do parceiro, mediante login com o "
    "CPF cadastrado no programa Esfera."
)
REGULAMENTO_REAL_2 = (
    "Promoção válida para clientes cadastrados no site oficial do parceiro "
    "entre 01/08 e 31/08/2026."
)


async def _seed_programa(db, nome="Esfera"):
    dominio = Dominio(nome="PROMOCOES")
    db.add(dominio)
    await db.flush()
    programa = Programa(dominio_id=dominio.id, nome=nome)
    db.add(programa)
    await db.flush()
    await db.commit()
    return programa


def _payload(regulamento_texto, **ajustes):
    base = dict(
        programa_nome="Esfera",
        parceiro_nome_bruto="Parceiro Esfera",
        titulo="Parceiro Esfera - 3 pontos por R$ 1",
        url_origem="https://esfera.com.vc/parceiro-esfera",
        pontuacao="3",
        unidade_pontuacao="pontos_por_real",
        origem_detalhe="coletor-esfera",
        regulamento_texto=regulamento_texto,
    )
    base.update(ajustes)
    return base


async def test_regulamento_real_substitui_placeholder_mas_nao_se_reescreve_depois(db, client):
    await _seed_programa(db)

    await client.post("/api/v1/promocoes/ingerir", json=_payload(PLACEHOLDER))
    promocao = (await db.execute(select(Promocao))).scalars().one()
    assert promocao.regulamento_texto == PLACEHOLDER

    # Segunda coleta chega com o regulamento genuíno: substitui o placeholder.
    await client.post("/api/v1/promocoes/ingerir", json=_payload(REGULAMENTO_REAL_1))
    promocao = (await db.execute(select(Promocao))).scalars().one()
    assert promocao.regulamento_texto == REGULAMENTO_REAL_1

    # Terceira coleta chega com outro texto genuíno: o que já está salvo já é
    # real, então não é reescrito à toa (era exatamente o que o bug fazia).
    await client.post("/api/v1/promocoes/ingerir", json=_payload(REGULAMENTO_REAL_2))
    promocao = (await db.execute(select(Promocao))).scalars().one()
    assert promocao.regulamento_texto == REGULAMENTO_REAL_1
