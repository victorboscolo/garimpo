# GAR-1100 — Capítulo 7
# PLANO DE IMPLANTAÇÃO LOCAL (MAC) — GARIMPO PROMOÇÕES (MVP)
**Versão:** 1.0
**Status:** Em construção
**Pré-requisitos:** Cap. 2 (Arquitetura Backend) · Cap. 3 Rev. 2 · Cap. 4 · Cap. 5 · Cap. 6
**Base:** Decisões Arquiteturais 063 e 064 (já aprovadas) — "desenvolver uma vez, implantar em qualquer lugar", tudo em containers, zero configuração específica de máquina.

---

## 1. Estrutura de diretórios do repositório

```
garimpo-promocoes/
├── docker-compose.yml
├── .env.example              # nunca commitar o .env real
├── backend/
│   ├── api/                  # rotas FastAPI (Cap. 6)
│   ├── application/          # casos de uso / services
│   ├── domain/                # entidades e regras de negócio
│   ├── infrastructure/        # repositórios, ORM, integrações externas
│   ├── coletores/             # módulo de coleta (Cap. 6)
│   ├── migrations/            # Alembic (Cap. 5)
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── docs/
│   └── GAR-1100/              # esta série de documentos
└── scripts/
    ├── backup.sh
    └── restore.sh
```

## 2. `docker-compose.yml` — componentes

| Serviço | Imagem base | Observação |
|---|---|---|
| `postgres` | `postgres:16` | Volume nomeado, nunca bind mount direto em pasta do usuário — mantém portabilidade |
| `backend` | build local (`backend/Dockerfile`) | FastAPI + Uvicorn, expõe API e painel admin |
| `scheduler` | mesma imagem do `backend` | Processo separado rodando `coletores/scheduler.py` — isolado para que uma falha no agendador não derrube a API |

Todas as credenciais (senha do Postgres, token do bot do Telegram, JWT secret) vêm de `.env` — nunca hardcoded, conforme Decisão 063.

## 3. Variáveis de ambiente essenciais

```
DATABASE_URL=postgresql://garimpo:***@postgres:5432/garimpo
JWT_SECRET=***
TELEGRAM_BOT_TOKEN=***
TELEGRAM_CANAL_PUBLICO_ID=***
TELEGRAM_CANAL_AVANCADO_ID=***
AMBIENTE=local          # local | producao — usado só para logs/observabilidade, nunca para alterar lógica de negócio
```

## 4. Estratégia de backup em camadas (Decisão Arquitetural 067 — já aprovada)

| Camada | O quê | Onde | Frequência |
|---|---|---|---|
| 1 — Produção | Dados vivos | Volume Docker no Mac | Contínuo |
| 2 — Backup local | Dump do Postgres + `.env` (sem segredos versionados) + arquivos de `arquivos` | HD externo dedicado | Diário (banco), a cada alteração (configurações) |
| 3 — Backup externo | Cópia criptografada do dump | Google Drive / OneDrive / Dropbox | Diário |

`scripts/backup.sh` roda via agendador do próprio macOS (`launchd`, preferível a cron no Mac) e grava um registro de status que alimenta o cartão "🟢 Backup" do futuro Painel de Saúde. Verificação semanal automática confirma que o backup mais recente restaura corretamente (não só que o arquivo existe).

## 5. Checklist de primeira execução ponta a ponta

1. `docker compose up -d postgres` — sobe o banco isolado primeiro.
2. `docker compose run backend alembic upgrade head` — aplica todas as migrations do Cap. 5, incluindo seed inicial (domínios, perfis, programas, `configuracoes`).
3. `docker compose up -d backend scheduler` — sobe API e agendador.
4. Login admin (`/auth/login`) com usuário criado manualmente no seed.
5. Rodar `coletor_livelo` manualmente uma vez (fora do agendamento) para validar o pipeline completo: coleta → hash/dedup → classificação → aparece em `/promocoes/pendentes`.
6. Aprovar uma promoção de teste → confirmar que `publicacoes` gera registro e a mensagem chega nos dois canais do Telegram (público e avançado).
7. Rodar `scripts/backup.sh` manualmente uma vez → confirmar dump gerado e cópia nas 3 camadas.
8. Só então ativar o agendamento automático do `scheduler`.

## 6. Portabilidade para nuvem (Fase 2 — quando chegar a hora)

Conforme Decisão 064, a migração deve alterar **apenas** onde o `docker-compose.yml` roda — não o conteúdo dele. Pontos a validar nesse momento (não implementar agora, só deixar registrado para não esquecer):

- Trocar volume local do Postgres por serviço gerenciado (RDS, Supabase, etc.) — só muda `DATABASE_URL`.
- Backup em nuvem passa a ser a camada primária de recuperação, HD externo pode virar redundância opcional.
- `AMBIENTE=producao` habilita logs mais verbosos/alertas, sem mudar regra de negócio nenhuma — mesma aplicação, mesmo comportamento.

---

## Status geral da modelagem técnica

Com este capítulo, a sequência GAR-1100 (Capítulos 2 a 7) cobre: arquitetura de código, schema físico, dicionário de dados, migrations/seed, endpoints/coletores e implantação local — o suficiente para começar a escrever código com uma base de decisões coerente e rastreável.
