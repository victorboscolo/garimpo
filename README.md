# Garimpo Promoções

Sistema de coleta e análise de promoções de acúmulo de pontos (Livelo, Esfera e futuros parceiros), com motor de análise próprio baseado em histórico.

Documentação completa de arquitetura e decisões: `docs/GAR-1100/` (Capítulos 2 a 7).

## Setup local (primeira execução)

Segue o checklist do GAR-1100 Capítulo 7.

```bash
# 1. Configurar variáveis de ambiente
cp .env.example .env
# edite .env com senhas/tokens reais

# 2. Subir o banco primeiro
docker compose up -d postgres

# 3. Aplicar migrations (schema + seed inicial)
docker compose run --rm backend alembic upgrade head

# 4. Subir API e agendador
docker compose up -d backend scheduler

# 5. Verificar que a API está no ar
curl http://localhost:8000/health
```

A documentação interativa da API fica em `http://localhost:8000/docs` (Swagger, gerado automaticamente pelo FastAPI).

## Estrutura

```
backend/
  api/            # rotas FastAPI (camada de apresentação)
  application/    # regras de orquestração (ex.: resolução de configuracoes)
  domain/         # modelos SQLAlchemy / entidades
  infrastructure/ # conexão com banco, integrações externas
  coletores/      # coletores por programa (Playwright) + scheduler
  migrations/     # Alembic
scripts/
  backup.sh       # backup em 3 camadas (Cap. 7)
docs/GAR-1100/    # documentação de arquitetura e decisões
```

## Status

Esqueleto inicial gerado a partir da auditoria e modelagem técnica (GAR-1100 Cap. 3 a 7). Pendências marcadas com `TODO` no código:

- Seletores reais do coletor Livelo (`coletores/livelo/coletor_livelo.py`)
- Resolução de parceiro via `parceiro_aliases` no pipeline
- Serviço de Classificação (Motor V1 — 6 pilares) ainda não implementado
- Integração real com Telegram (2 canais)
- Autenticação JWT nas rotas (esqueleto de endpoints ainda sem proteção)
