"""Cache de uma execução do reprocessamento em lote.

Reclassificar todas as promoções relê, a cada uma, exatamente os mesmos
dados de comparação (o mercado do programa, o segmento, as configurações) —
mudam entre promoções só o parceiro e a própria oferta. Com o banco no
Neon, cada releitura atravessa a internet: em 24/09 uma recalibração de
1.165 promoções levou 32 min e gastou a maior parte dos 5 GB mensais de
transferência do plano grátis.

O cache vive só durante uma execução (é criado em `reclassificar_todas` e
descartado no fim), então nunca serve dado velho: nada que o motor lê
(promoções, vínculos, configurações) muda durante o próprio reprocessamento.
Sem cache (`cache=None`), tudo se comporta como antes.
"""
from dataclasses import dataclass, field


@dataclass
class CacheMotor:
    dados: dict = field(default_factory=dict)

    async def obter(self, chave, fabrica):
        """Devolve o valor guardado para a chave, ou o calcula uma única vez
        chamando `fabrica()` (uma função assíncrona sem argumentos).
        """
        if chave not in self.dados:
            self.dados[chave] = await fabrica()
        return self.dados[chave]

    async def obter_por_id(self, db, modelo, id_):
        """`db.get` memoizado. O mapa de identidade da sessão guarda os
        objetos com referência fraca — sem isto, cada `db.get` de uma
        categoria já lida vira uma nova ida ao banco.
        """
        return await self.obter(("get", modelo.__name__, id_), lambda: db.get(modelo, id_))
