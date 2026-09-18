FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Nenhum navegador é instalado aqui: os coletores que dependem de Playwright/
# SeleniumBase rodam fora do Docker, nas próprias máquinas (ver
# coletor-nativo/, coletor-esfera/, coletor-emissoes-azul/) — a API que este
# container serve nunca abre um navegador. `backend/coletores/` é um coletor
# antigo, abandonado (bloqueado por anti-robô, ver HANDOFF.md), que ninguém
# importa; instalar Chromium pra ele só inchava a imagem e deixava a build
# mais lenta, o que pesa de verdade num build grátis no Render.

COPY . .

EXPOSE 8000

# Render (e a maioria dos PaaS) definem a porta via $PORT em vez de uma fixa;
# localmente (docker-compose, sem PORT definida) cai no 8000 de sempre.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]