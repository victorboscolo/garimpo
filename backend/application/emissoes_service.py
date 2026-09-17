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


async def listar_ofertas_atuais(db, programa_nome: str | None = None) -> list[dict]:
    """A leitura pro painel: não o histórico inteiro, só o retrato de agora
    — a oferta mais recente de cada rota, separada em direto/com-parada
    (decisão do usuário, 17/09: as duas categorias continuam distintas
    aqui, não é escolhida uma única "a melhor de todas").

    Uma linha por (rota, categoria direto/com-parada) que já teve alguma
    coleta; rota sem nenhuma oferta ainda não aparece.
    """
    from sqlalchemy import select

    from domain.cadastros import Programa
    from domain.emissoes import OfertaEmissao, RotaEmissao

    stmt = (
        select(OfertaEmissao, RotaEmissao, Programa)
        .join(RotaEmissao, RotaEmissao.id == OfertaEmissao.rota_id)
        .join(Programa, Programa.id == RotaEmissao.programa_id)
        .order_by(OfertaEmissao.created_at.desc())
    )
    if programa_nome:
        stmt = stmt.filter(Programa.nome == programa_nome)

    linhas = (await db.execute(stmt)).all()

    vistos: set[tuple] = set()
    atuais: list[dict] = []
    for oferta, rota, programa in linhas:
        categoria = "DIRETO" if oferta.paradas == 0 else "COM_PARADA"
        chave = (rota.id, categoria)
        if chave in vistos:
            continue
        vistos.add(chave)
        atuais.append({
            "programa_nome": programa.nome,
            "origem": rota.origem,
            "destino": rota.destino,
            "fonte": rota.fonte,
            "categoria": categoria,
            "classe": oferta.classe,
            "data_ida": oferta.data_ida,
            "pontos": oferta.pontos,
            "duracao_texto": oferta.duracao_texto,
            "companhia_operadora": oferta.companhia_operadora,
            "paradas": oferta.paradas,
            "assentos_restantes": oferta.assentos_restantes,
            "coletado_em": oferta.created_at,
        })

    return atuais
