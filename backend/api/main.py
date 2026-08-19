from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from api.v1 import classificacoes, promocoes, publicacoes, saude

app = FastAPI(
    title="Garimpo Promoções — API",
    version="0.1.0",
    description="Painel administrativo e API do Garimpo Promoções (MVP).",
)

app.include_router(promocoes.router, prefix="/api/v1/promocoes", tags=["promocoes"])
app.include_router(classificacoes.router, prefix="/api/v1/promocoes", tags=["classificacoes"])
app.include_router(publicacoes.router, prefix="/api/v1/publicacoes", tags=["publicacoes"])
app.include_router(saude.router, prefix="/api/v1", tags=["saude"])

class PainelSemCache(StaticFiles):
    """Serve o painel sempre revalidando com o servidor.

    O painel é um arquivo único editado com frequência, e o navegador guardava
    a versão anterior: mudanças apareciam só depois de recarregar ignorando o
    cache, o que dava a impressão de funcionalidade quebrada quando ela existia
    e estava no ar. `no-cache` não impede o cache — obriga a perguntar se mudou,
    o que num arquivo servido de localhost custa nada.
    """

    def file_response(self, *args, **kwargs) -> Response:
        resposta = super().file_response(*args, **kwargs)
        resposta.headers["Cache-Control"] = "no-cache, must-revalidate"
        return resposta


# Painel visual simples de revisão — http://localhost:8000/admin/
app.mount("/admin", PainelSemCache(directory="static/admin", html=True), name="admin")


@app.get("/health")
async def health():
    return {"status": "ok"}
