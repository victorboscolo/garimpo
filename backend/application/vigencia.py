"""Define quando uma promoção ainda vale, pra não duplicar a mesma regra
em mais de um lugar — já rendeu um bug real quando vivia só embutida em
`publicacao_service.py` (ver `montar_fila`, achado do usuário em 09/09).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import ColumnElement, or_

from domain.promocoes import Promocao


def filtro_vigente() -> ColumnElement[bool]:
    """Sem `data_fim`, a promoção nunca expira (são as taxas estáveis do
    parceiro, tipo o "BAU" da Livelo — descartá-las por falta de data
    eliminaria metade das boas ofertas). Com `data_fim`, ele guarda a
    meia-noite do início do último dia válido, não o fim dele — soma um
    dia antes de comparar, senão a campanha sai da fila na própria
    meia-noite do dia em que ainda vale.
    """
    agora = datetime.now(timezone.utc)
    return or_(Promocao.data_fim.is_(None), Promocao.data_fim + timedelta(days=1) > agora)
