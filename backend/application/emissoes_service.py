"""Ingestão de ofertas do Garimpo Emissões: preço em milhas por rota (uma
perna, só ida), data e classe, sempre a mais barata encontrada numa coleta
(decisão do usuário, 19/08 — buscar traz várias opções de horário/conexão,
o sinal que importa é "qual o menor preço hoje"; 21/08 — por perna, não por
pacote ida+volta, pra ter mais alcance de público e dar liberdade pro
usuário).

Sem motor, sem dedup por hash: cada coleta é um retrato do preço agora, e o
histórico completo — não só a observação mais recente — é o que sustenta o
futuro sinal de queda de preço ao longo do tempo.

`RotaEmissao` é catálogo curado à mão (seção 5 do HANDOFF tem a lista e o
critério); este serviço nunca cria rota nova a partir do que o coletor
manda, só resolve pra uma já cadastrada — uma rota fora do catálogo é
descartada, não adicionada por conta própria.
"""
from datetime import date
from decimal import Decimal


async def resolver_rota(db, programa_nome: str, origem: str, destino: str):
    from sqlalchemy import select

    from domain.cadastros import Programa
    from domain.emissoes import RotaEmissao

    programa = (await db.execute(
        select(Programa).filter_by(nome=programa_nome)
    )).scalar_one_or_none()
    if programa is None:
        return None

    return (await db.execute(
        select(RotaEmissao).filter_by(programa_id=programa.id, origem=origem, destino=destino, ativa=True)
    )).scalar_one_or_none()


async def registrar_oferta(
    db, rota_id, data_ida: date, classe: str, pontos: int,
    taxa_reais: Decimal | None = None, companhia_operadora: str | None = None,
    paradas: int | None = None, assentos_restantes: int | None = None,
    duracao_texto: str | None = None,
):
    """Registra a oferta mais barata de uma perna (só ida — decisão do
    usuário, 21/08). Não recebe data_volta: uma oferta de volta é outro
    registro, na rota oposta.

    Pode ser chamado mais de uma vez pela mesma coleta (rota+data+classe)
    quando o coletor separa "mais barata direto" de "mais barata com
    parada" (decisão do usuário, 17/09) — cada chamada é uma linha
    imutável própria, diferenciada pelo próprio `paradas` que ela grava.
    """
    from domain.emissoes import OfertaEmissao

    oferta = OfertaEmissao(
        rota_id=rota_id, data_ida=data_ida, classe=classe, pontos=pontos,
        taxa_reais=taxa_reais, companhia_operadora=companhia_operadora,
        paradas=paradas, assentos_restantes=assentos_restantes,
        duracao_texto=duracao_texto,
    )
    db.add(oferta)
    await db.commit()
    await db.refresh(oferta)
    return oferta


async def listar_rotas_ativas(db, programa_nome: str | None = None):
    from sqlalchemy import select

    from domain.cadastros import Programa
    from domain.emissoes import RotaEmissao

    stmt = select(RotaEmissao).filter_by(ativa=True)
    if programa_nome:
        programa = (await db.execute(
            select(Programa).filter_by(nome=programa_nome)
        )).scalar_one_or_none()
        if programa is None:
            return []
        stmt = stmt.filter_by(programa_id=programa.id)

    return list((await db.execute(stmt)).scalars().all())
