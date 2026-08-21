"""Montagem de URLs de busca do Garimpo Emissões (Azul).

Dois sistemas de busca, achado técnico de 20/08/2026 (HANDOFF seção 5):
- `azulpelomundo.voeazul.com.br`: malha de parceiros, +3.000 destinos.
- Site principal (`voeazul.com.br`): só malha própria da Azul (Brasil +
  Flórida/Lisboa/Paris).

Busca é sempre só-ida (decisão do usuário, 21/08 — ver domain/emissoes.py):
uma promoção de ida sozinha tem mais alcance de público e dá liberdade pro
usuário, e o preço da ida dentro de um pacote combinado pode ser mais
barato do que comprá-la sozinha, então a busca precisa ser só-ida de
verdade, não ida-e-volta com a volta descartada. Os dois padrões abaixo
foram revalidados nesse modo em 21/08/2026, contra buscas reais.

Em ambos os casos, a URL direta só funciona **depois** que a sessão já foi
aquecida por uma primeira busca via formulário — navegar direto pra cá sem
isso não retorna resultado (ver HANDOFF seção 5).
"""
from datetime import date


def url_azul_pelo_mundo(origem: str, destino: str, data_ida: date, classe: str) -> str:
    """URL de busca direta (só ida) no portal azulpelomundo.

    Capturada de verdade em 21/08/2026, depois de uma busca real GRU->LIS:
    https://azulpelomundo.voeazul.com.br/flights/OW/GRU/LIS/-/-/2026-08-25/-/1/0/0/0/0/ALL/F/ECONOMY/-/-/-/-/A/-
    """
    return (
        f"https://azulpelomundo.voeazul.com.br/flights/OW/{origem}/{destino}/-/-/"
        f"{data_ida.isoformat()}/-/1/0/0/0/0/ALL/F/{classe.upper()}/-/-/-/-/A/-"
    )


def url_site_principal(origem: str, destino: str, data_ida: date) -> str:
    """URL de busca direta (só ida) no site principal da Azul.

    Sem parâmetro de classe — achado real (20/08): o resultado já traz
    Economy e Business juntas no mesmo card, então classe é atributo do
    resultado, não entrada de busca (diferente do azulpelomundo).

    Capturada de verdade em 21/08/2026, depois de uma busca real GIG->MCO:
    https://www.voeazul.com.br/br/pt/home/selecao-voo?c[0].ds=GIG&c[0].std=08/22/2026&c[0].as=MCO&p[0].t=ADT&p[0].c=1&p[0].cp=false&f.dl=3&f.dr=3&cc=PTS
    """
    ida = data_ida.strftime("%m/%d/%Y")
    return (
        "https://www.voeazul.com.br/br/pt/home/selecao-voo?"
        f"c[0].ds={origem}&c[0].std={ida}&c[0].as={destino}&"
        "p[0].t=ADT&p[0].c=1&p[0].cp=false&f.dl=3&f.dr=3&cc=PTS"
    )
