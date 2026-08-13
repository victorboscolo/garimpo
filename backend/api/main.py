from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.v1 import classificacoes, promocoes

app = FastAPI(
    title="Garimpo Promoções — API",
    version="0.1.0",
    description="Painel administrativo e API do Garimpo Promoções (MVP).",
)

app.include_router(promocoes.router, prefix="/api/v1/promocoes", tags=["promocoes"])
app.include_router(classificacoes.router, prefix="/api/v1/promocoes", tags=["classificacoes"])

# Painel visual simples de revisão — http://localhost:8000/admin/
app.mount("/admin", StaticFiles(directory="static/admin", html=True), name="admin")


@app.get("/health")
async def health():
    return {"status": "ok"}
