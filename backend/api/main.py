from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from api.dependencies import exigir_acesso
from api.v1 import auth, classificacoes, emissoes, promocoes, publicacoes, saude

app = FastAPI(
    title="Garimpo Promoções — API",
    version="0.1.0",
    description="Painel administrativo e API do Garimpo Promoções (MVP).",
)

# /auth é a única rota pública — login precisa ser alcançável sem sessão.
# As demais exigem `exigir_acesso` (cookie de sessão do painel OU chave de
# API dos coletores/scripts, ver api/dependencies.py): endpoints com os dois
# tipos de chamador (ex: POST /promocoes/ingerir é só coletor, GET
# /promocoes é painel e também scripts/recalibrar.sh) ficam cobertos pelo
# mesmo dependency, sem precisar separar rota por rota.
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(
    promocoes.router, prefix="/api/v1/promocoes", tags=["promocoes"],
    dependencies=[Depends(exigir_acesso)],
)
app.include_router(
    classificacoes.router, prefix="/api/v1/promocoes", tags=["classificacoes"],
    dependencies=[Depends(exigir_acesso)],
)
app.include_router(
    publicacoes.router, prefix="/api/v1/publicacoes", tags=["publicacoes"],
    dependencies=[Depends(exigir_acesso)],
)
app.include_router(
    saude.router, prefix="/api/v1", tags=["saude"],
    dependencies=[Depends(exigir_acesso)],
)
app.include_router(
    emissoes.router, prefix="/api/v1/emissoes", tags=["emissoes"],
    dependencies=[Depends(exigir_acesso)],
)

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
