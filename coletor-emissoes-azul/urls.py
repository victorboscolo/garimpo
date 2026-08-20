"""Montagem de URLs de busca do Garimpo Emissões (Azul).

Dois sistemas de busca, achado técnico de 20/08/2026 (HANDOFF seção 5):
- `azulpelomundo.voeazul.com.br`: malha de parceiros, +3.000 destinos.
  Padrão de URL abaixo validado empiricamente no mesmo dia.
- Site principal (`voeazul.com.br`): só malha própria da Azul (Brasil +
  Flórida/Lisboa/Paris). Precisa ser revalidado nesta sessão antes de
  ganhar uma função aqui — não codificar de memória de investigação
  anterior sem conferir de novo.

Em ambos os casos, a URL direta só funciona **depois** que a sessão já foi
aquecida por uma primeira busca via formulário — navegar direto pra cá
sem isso não retorna resultado (ver HANDOFF seção 5).
"""
from datetime import date


def url_azul_pelo_mundo(
    origem: str, destino: str, data_ida: date, data_volta: date, classe: str,
) -> str:
    """URL de busca direta (ida e volta) no portal azulpelomundo.

    Só ida e volta está validado — o formato pra somente-ida não foi
    testado ainda, por isso `data_volta` é obrigatória aqui.
    """
    return (
        f"https://azulpelomundo.voeazul.com.br/flights/RT/{origem}/{destino}/-/-/"
        f"{data_ida.isoformat()}/{data_volta.isoformat()}/1/0/0/0/0/ALL/F/{classe.upper()}/-/-/-/-/A/-"
    )


def url_site_principal(origem: str, destino: str, data_ida: date, data_volta: date) -> str:
    """URL de busca direta (ida e volta) no site principal da Azul.

    Sem parâmetro de classe — achado real (20/08): o resultado já traz
    Economy e Business juntas no mesmo card, então classe é atributo do
    resultado, não entrada de busca (diferente do azulpelomundo).
    """
    ida = data_ida.strftime("%m/%d/%Y")
    volta = data_volta.strftime("%m/%d/%Y")
    return (
        "https://www.voeazul.com.br/br/pt/home/selecao-voo?"
        f"c[0].ds={origem}&c[0].std={ida}&c[0].as={destino}&"
        f"c[1].ds={destino}&c[1].std={volta}&c[1].as={origem}&"
        "p[0].t=ADT&p[0].c=1&p[0].cp=false&f.dl=3&f.dr=3&cc=PTS"
    )
