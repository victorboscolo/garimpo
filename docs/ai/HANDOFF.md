# Handoff para Claude Code

## 1. Resumo executivo

O **Garimpo Promoções** é um sistema que coleta, normaliza e analisa ofertas de pontuação de programas de fidelidade (inicialmente Livelo e Esfera), calculando uma nota e categoria de atratividade para cada oferta via um motor de regras próprio (não é um LLM), e expondo os resultados para revisão humana antes de qualquer divulgação. Existe um segundo produto planejado, **Garimpo Emissões** (passagens aéreas via milhas), fora do escopo atual, mas cuja arquitetura já foi parcialmente antecipada.

**Estágio atual**: MVP funcional de ponta a ponta rodando localmente no Mac do usuário — coleta real (Livelo), motor de classificação, banco de dados, API e um painel administrativo simples estão implementados e foram validados com dados reais (249 promoções coletadas e classificadas). O projeto ainda **não usa controle de versão Git** (todo o código foi transferido via zip/Finder durante a sessão anterior) — isso deve ser corrigido na primeira sessão do Claude Code.

**Resultado esperado da próxima fase**: (a) inicializar Git no repositório; (b) completar as melhorias pendentes no painel admin (listadas na seção 9); (c) avaliar autenticação básica antes de qualquer exposição além de localhost.

## 2. Escopo atual e limites

**Dentro do escopo (MVP — Garimpo Promoções):**
- Coleta de ofertas "ganhe pontos" da Livelo (parceiro + programa + pontuação).
- Motor de Análise V1 (regras determinísticas, 6 critérios ponderados — não é IA/LLM).
- Fila de revisão humana obrigatória (nenhuma publicação automática sem aprovação).
- Painel administrativo mínimo para aprovar/rejeitar.

**Fora do escopo atual (adiado, não excluído):**
- Garimpo Emissões (passagens aéreas) — ver `docs/GAR-1100/GAR-1100-Cap8-Notas-Futuro-Emissoes.md`.
- Publicação automática (Telegram) — desenhada na documentação, **não implementada**.
- Autenticação/autorização de usuários — endpoints hoje são públicos (uso local apenas).
- Coletor da Esfera — programa está cadastrado no banco, mas não existe coletor implementado para ele.

**Premissas que precisam ser preservadas:**
- O sistema nunca contorna CAPTCHA, autenticação ou controles de acesso de terceiros (ver seção 6).
- Promoções são **imutáveis**: uma mudança real de oferta cria um novo registro, nunca sobrescreve o anterior (preservação de histórico).
- Toda publicação passa por aprovação humana — decisão de produto explícita, não é limitação técnica temporária.

## 3. Estado atual do projeto

| Componente | Status | O que já existe | O que falta | Arquivos/documentos relacionados |
|---|---|---|---|---|
| Modelo de dados (schema) | IMPLEMENTADO | 16 tabelas, migrations Alembic aplicadas, seed inicial | — | `docs/GAR-1100/GAR-1100-Cap3-Modelo-PostgreSQL-Fisico-Rev2.md`, `backend/migrations/versions/`, `backend/domain/*.py` |
| Motor de Análise V1 | IMPLEMENTADO | 6 pilares, pesos/faixas configuráveis, testado com dados reais | Calibração real (depende de haver histórico aprovado) | `backend/application/motor/` |
| Coletor Livelo (Docker, headless) | ABANDONADO | Implementação existe no código (`backend/coletores/livelo/`) | Bloqueado por proteção anti-robô (HTTP 403); não usar em produção | Ver seção 5 (decisão técnica) |
| Coletor Livelo nativo (macOS) | IMPLEMENTADO | Roda fora do Docker, headless=False, validado com 249 promoções reais | Não captura variante "Clube Livelo"; sem tratamento de erro robusto para mudanças no site | `coletor-nativo/coletor_livelo_nativo.py` |
| Agendamento automático | IMPLEMENTADO | `launchd` diário às 10:05 configurado e testado | Só roda com o Mac ligado e logado — sem monitoramento de falha | `coletor-nativo/com.garimpo.coletor-livelo.plist` |
| API (FastAPI) | IMPLEMENTADO | Endpoints de listagem, aprovação, rejeição, ingestão, reclassificação (individual e em massa) | Autenticação; endpoint de rejeição em massa (só aprovação em massa existe) | `backend/api/v1/promocoes.py`, `classificacoes.py` |
| Painel admin (HTML) | IMPLEMENTADO (parcial) | Listagem por status, aprovação/rejeição individual e em massa (aprovar), histórico de notas expansível | Ordenação por pontuação, exibição dos critérios do motor, rejeição em massa, mais campos informativos (restrições, clube, cupom) — ver seção 9 | `backend/static/admin/index.html` |
| Publicação (Telegram) | PLANEJADO | Tabela `publicacoes` existe no schema | Toda a integração com a API do Telegram | `docs/GAR-1100/GAR-1100-Cap6-Endpoints-e-Coletores.md` |
| Autenticação | PLANEJADO | Tabelas `usuarios`/`perfis` existem | JWT, proteção de rotas | `docs/GAR-1100/GAR-1100-Cap2` (referenciado, não presente neste handoff) |
| Coletor Esfera | PENDENTE | Programa cadastrado no banco (seed) | Nenhum código de coleta | — |
| Garimpo Emissões | EM ESTUDO | Notas de arquitetura registradas | Tudo | `docs/GAR-1100/GAR-1100-Cap8-Notas-Futuro-Emissoes.md` |
| Testes automatizados | PENDENTE | Pasta `backend/tests/` existe, vazia | Tudo | — |
| Controle de versão (Git) | PENDENTE | Nenhum repositório Git inicializado até o momento deste handoff | `git init`, primeiro commit, `.gitignore` | — |

## 4. Arquitetura e fluxo de dados

**Arquitetura implementada (protótipo real, não só planejada):**

```
Coletor nativo (macOS, fora do Docker)
    → Playwright com Chromium visível (headless=False)
    → navega até a Livelo, extrai texto via regex
    → POST http://localhost:8000/api/v1/promocoes/ingerir (HTTP)
        ↓
Backend FastAPI (dentro do Docker)
    → application/ingestao_service.py:
        - calcula hash de dedup
        - resolve/cria Parceiro (cadastro automático na 1ª ocorrência)
        - cria registro em `promocoes` (status=PENDENTE)
        - aciona application/motor/servico.py → grava `classificacoes`
        ↓
PostgreSQL (Docker, dados persistidos)
        ↓
Painel admin (static/admin/index.html, servido pelo próprio FastAPI)
    → humano aprova ou rejeita
```

**Por que o coletor roda fora do Docker (decisão importante):** o site da Livelo bloqueia (HTTP 403) o Chromium headless, tanto rodando dentro de um container Linux quanto nativamente no macOS. Só o Chromium **nativo do macOS rodando com janela visível** (`headless=False`) passa pela proteção. Isso não é um capricho — foi testado e comprovado nesta sessão. Ver seção 5 para o histórico completo de tentativas.

**Entidades principais do banco** (`backend/domain/*.py`, schema completo em `docs/GAR-1100/GAR-1100-Cap3-Modelo-PostgreSQL-Fisico-Rev2.md`):
- `dominios` → PROMOCOES (ativo) / EMISSOES (reservado, inativo).
- `marcas` → `parceiros` (1:N) → `promocoes` (parceiro_id, programa_id).
- `programas` → seed inicial: Livelo, Esfera.
- `classificacoes`, `arquivos`, `publicacoes` usam referência **polimórfica** (`entidade_tipo` + `entidade_id`, sem FK nativa) para já suportar tanto `PROMOCAO` quanto o futuro `EMISSAO` sem redesenho de schema.
- `configuracoes` implementa hierarquia de parametrização **GLOBAL → DOMÍNIO → PROGRAMA → PARCEIRO** (colunas nullable + resolução pelo mais específico) — usado pelo motor para pesos, faixas de classificação, limiar de histórico suficiente e peso temporal.

**Motor de Análise V1** (`backend/application/motor/`): 6 critérios independentes (Histórico 25%, Atratividade 25%, Amplitude 20%, Facilidade 10%, Exclusividade 10%, Confiabilidade dos dados 10% — pesos configuráveis via `configuracoes`), nota final = média ponderada, categoria resolvida por faixas configuráveis (padrão: Excepcional 90-100 / Excelente 75-89 / Boa 55-74 / Comum 35-54 / Pouco atrativa 0-34). Distinção importante preservada no código: `confianca_historica` (ALTA/MEDIA/BAIXA, baseada em volume de histórico aprovado) é conceitualmente **diferente** de `confiabilidade_dados` (0-100, completude dos dados da campanha específica) — não confundir os dois ao alterar o motor.

**Limitação observada em produção:** como nenhuma promoção foi aprovada ainda (todas as 251 coletadas seguem PENDENTE), o motor não tem histórico aprovado para comparar — por isso praticamente todas as notas hoje giram em torno de 55-67 (valor neutro nos critérios comparativos). Isso é esperado, não é bug. Existe um endpoint `POST /api/v1/promocoes/reclassificar-todas` para reprocessar tudo depois que houver aprovações reais.

## 5. Decisões técnicas e de negócio

| Decisão | Justificativa | Alternativa rejeitada | Impacto |
|---|---|---|---|
| Coletor Livelo roda nativo no macOS, não no Docker | Site bloqueia (403) Chromium headless em container Linux ARM64 e também headless nativo no Mac; só `headless=False` nativo passa | Chromium headless com user-agent/headers disfarçados (testado, falhou); `playwright-stealth` (abandonado — dependência `pkg_resources` incompatível); Chrome real via canal `channel="chrome"` (indisponível para Linux ARM64; download falhou no macOS por motivo não investigado a fundo) | Arquitetura tem uma exceção ao padrão "tudo em Docker": esse coletor depende do Mac estar ligado e logado |
| Nome do parceiro extraído da URL, não do texto do card | Inspeção real do DOM mostrou que o texto visível do card **não contém** o nome do parceiro (isso só aparecia em uma ferramenta de leitura de página usada para inspeção inicial, que sintetizava texto a partir de atributos `alt` de imagem — não é texto real do DOM) | Regex sobre texto do card com prefixo "Logo Nome" (baseado em inspeção indireta, não no DOM real — não funcionou) | Extração por URL é mais robusta a mudanças de estilo visual do site |
| Cadastro automático de Parceiro/Marca na 1ª ocorrência | Pré-cadastrar ~250 parceiros manualmente antes do MVP não é viável | Descartar promoção quando parceiro não cadastrado (comportamento original, gerava 0 promoções criadas em teste real) | Marca é criada 1:1 com o parceiro como ponto de partida; requer curadoria manual futura para agrupar marcas/definir categoria |
| `classificacoes`/`arquivos`/`publicacoes` com referência polimórfica (`entidade_tipo`+`entidade_id`, sem FK nativa) | Preparar essas 3 tabelas para servirem também ao futuro Garimpo Emissões sem redesenho de schema | FK direta para `promocoes.id` | Integridade referencial dessas colunas precisa ser validada em código de aplicação (não há garantia do banco) |
| Motor V1 com 6 critérios fixos e pesos configuráveis (não hardcoded) | Permite calibração via `configuracoes` sem deploy de código | Pesos fixos no código | Qualquer ajuste de peso é uma operação de dados, não de código |
| Painel admin: HTML/JS simples servido pelo próprio FastAPI (`StaticFiles`), sem framework | Ferramenta interna, uso por 1-2 pessoas, prioridade em simplicidade de deploy | React/Vue com build separado | Sem sistema de componentes; qualquer nova feature de UI é edição direta do HTML |
| `codigo` (BigInteger sequencial) usa `sqlalchemy.Identity()` explícito no ORM, não só `autoincrement=True` | Sem isso, o ORM assíncrono envia `NULL` explícito no INSERT e o Postgres rejeita (constraint NOT NULL) mesmo a coluna sendo IDENTITY no schema | `autoincrement=True` sozinho (causou `NotNullViolationError` em produção) | Qualquer nova tabela com coluna `codigo` sequencial precisa repetir esse padrão |
| Base da imagem Docker do backend é `python:3.12-slim-bookworm`, não `python:3.12-slim` | A tag genérica `slim` migrou para Debian `trixie`, cujo repositório não tem os pacotes que o Playwright espera (`ttf-ubuntu-font-family` etc.) | `python:3.12-slim` (build falhava no `playwright install --with-deps`) | Fixar a tag evita quebra silenciosa em rebuilds futuros |

## 6. Fontes, coleta e conformidade

**Fonte de dados atual:** `https://www.livelo.com.br/juntar-pontos/todos-os-parceiros` (página pública de listagem de parceiros).

**Premissas de coleta:**
- Coleta roda 1x/dia (10:05, alguns minutos após a Livelo costumar atualizar às 10h — informação dada pelo usuário, **A CONFIRMAR**: não há fonte oficial documentada para esse horário de atualização, foi um entendimento informal repassado na conversa).
- Sem paralelismo agressivo: uma navegação por execução, sem múltiplas requisições simultâneas.
- **Nenhuma credencial, cookie de sessão ou mecanismo de bypass de autenticação é usado** — a página coletada é pública, sem login.
- O sistema **não implementa e não deve implementar** contorno de CAPTCHA, rate limit ou qualquer controle de acesso. A solução adotada (navegador real, visível, nativo) opera dentro do que um usuário humano comum faria ao abrir a página no navegador — não há manipulação de protocolo, injeção de headers falsos além de identificação de navegador padrão, nem exploração de falha de segurança.
- Variáveis de ambiente sensíveis (senha do Postgres, JWT secret, tokens de bot) ficam em `.env` (não versionado — ver `.env.example` para os nomes esperados). Nenhum valor real está no código ou nesta documentação.

**Limitação de dados conhecida:** a variante "Clube Livelo" (pontuação diferenciada para assinantes do clube) não é capturada pelo coletor atual — não apareceu no texto visível dos cards da página de listagem durante a inspeção real feita nesta sessão. Pegar esse dado exigiria visitar a página de detalhe de cada parceiro (não implementado). **A CONFIRMAR**: se esse dado é prioritário, avaliar coleta em duas etapas (listagem + detalhe) ou aceitar a limitação por ora.

## 7. Convenções de desenvolvimento

**Stack:**
- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0 (async, `asyncpg`), Alembic, Pydantic v2.
- Banco: PostgreSQL 16 (container Docker).
- Coletor nativo: Python 3.9 (versão do Apple Command Line Tools, **A CONFIRMAR** se deve ser atualizado para uma versão mais recente), Playwright, `httpx`.
- Painel admin: HTML/CSS/JS vanilla, sem framework nem build step.
- Orquestração: Docker Compose (serviços `postgres`, `backend`, `scheduler`).

**Estrutura de pastas** (raiz do projeto, hoje em `~/Garimpo/garimpo-promocoes-v2` no Mac do usuário — **A CONFIRMAR**: nome da pasta tem sufixo `-v2` por causa de uma migração feita durante a sessão anterior; existem pastas antigas não utilizadas em `~/Garimpo` — `garimpo-promocoes` e `Old - 0808` — candidatas a limpeza, mas não confirmadas como seguras para apagar):

```
docker-compose.yml
.env.example
backend/
  api/            # rotas FastAPI (v1/promocoes.py, v1/classificacoes.py)
  application/    # regras de orquestração (motor/, ingestao_service.py, configuracoes_service.py, validators.py)
  domain/         # modelos SQLAlchemy (cadastros.py, promocoes.py, motor.py, governanca.py)
  infrastructure/ # conexão com banco (db/base.py, db/session.py)
  coletores/      # coletor Livelo Docker (abandonado), pipeline.py, scheduler.py
  migrations/     # Alembic
  static/admin/   # painel HTML
  tests/          # vazio
coletor-nativo/   # roda fora do Docker — venv próprio
  coletor_livelo_nativo.py
  requirements.txt
  rodar_coletor.sh
  com.garimpo.coletor-livelo.plist
docs/GAR-1100/    # documentação de arquitetura e decisões (Cap. 3 a 8)
docs/ai/          # este handoff
scripts/backup.sh
```

**Comandos principais:**
```bash
# Subir tudo
docker compose up -d postgres
docker compose run --rm backend alembic upgrade head   # só na 1ª vez / novas migrations
docker compose up -d --build backend scheduler

# Painel admin
open http://localhost:8000/admin/

# Coletor nativo (manual)
cd coletor-nativo && source venv/bin/activate && python3 coletor_livelo_nativo.py

# Coletor nativo (forçar execução do agendamento sem esperar o horário)
launchctl start com.garimpo.coletor-livelo
```

**Lint/testes:** nenhuma ferramenta configurada até o momento (`PENDENTE`). Nenhuma convenção de commit definida (Git ainda não inicializado).

## 8. Pendências, riscos e dúvidas em aberto

| Item | Tipo | Impacto | Informação disponível | Próxima validação necessária |
|---|---|---|---|---|
| Repositório sem Git | Risco | Alto — sem histórico de mudanças, sem rollback | Nenhuma | Inicializar Git, criar `.gitignore` (excluir `.env`, `venv/`, `__pycache__`, `*.log`, `diagnostico.png`) |
| Endpoint `/promocoes/ingerir` sem autenticação | Risco de segurança | Médio (hoje só acessível via localhost) | Comentário `TODO` no código | Definir mecanismo de autenticação antes de expor além de localhost |
| Coletor nativo depende do Mac ligado/logado | Risco operacional | Médio — coleta diária pode falhar silenciosamente | Documentado no `README.md` do coletor-nativo | Definir se isso é aceitável a longo prazo ou se precisa migrar para outra estratégia (ex: máquina sempre ligada) |
| Nenhuma promoção aprovada ainda | Limitação temporária | Alto para a qualidade do motor | Confirmado nesta sessão (251 pendentes, 0 aprovadas) | Aprovar um lote inicial e rodar `/reclassificar-todas` para validar se as notas passam a refletir histórico real |
| Variante "Clube Livelo" não capturada | Lacuna de dados | Médio, dependendo da prioridade de negócio | Confirmado via inspeção real do DOM | Decidir se vale coletar via página de detalhe |
| Pasta do projeto com sufixo `-v2` e pastas antigas não utilizadas em `~/Garimpo` | Organização | Baixo | Mencionado na sessão anterior, não limpo | Confirmar com o usuário se pode reorganizar/renomear |
| Python 3.9 no ambiente nativo do coletor | Compatibilidade | Baixo (já contornado com `from __future__ import annotations`) | Confirmado nesta sessão | Avaliar se vale migrar para Python mais recente |
| Horário de atualização da Livelo (10h) | Premissa de negócio | Baixo | Informação repassada pelo usuário, sem fonte oficial | Observar empiricamente ao longo de alguns dias se o horário de agendamento (10:05) está bem calibrado |

## 9. Próximas tarefas recomendadas

### Tarefa 1 — Inicializar Git e organizar o repositório
**Objetivo:** ter controle de versão real antes de qualquer nova alteração.
**Escopo:** `git init`, `.gitignore` adequado (excluir `.env`, `venv/`, `__pycache__`, `*.log`, `diagnostico.png`, `node_modules` se houver), primeiro commit com o estado atual, confirmar com o usuário o nome definitivo da pasta do projeto.
**Arquivos envolvidos:** raiz do repositório.
**Critério de aceite:** `git log` mostra pelo menos um commit; `git status` limpo; segredos confirmadamente fora do controle de versão.
**Testes esperados:** nenhum automatizado; verificação manual de que `.env` não aparece em `git status`.
**Riscos:** nenhum arquivo sensível deve ser commitado por engano — revisar `git diff --cached` antes do primeiro commit.

### Tarefa 2 — Completar as melhorias pendentes do painel admin
**Objetivo:** tornar a revisão diária de ~250 promoções viável e mais informativa (pedido explícito do usuário, não implementado antes da migração para Claude Code).
**Escopo:**
1. Ordenar a listagem por `pontuacao` decrescente.
2. Exibir os critérios/subnotas do motor (`criterios_avaliados`) na tela, não só a nota final e a justificativa — provavelmente como um painel expansível, seguindo o mesmo padrão já usado para "Ver histórico de notas".
3. Adicionar rejeição em massa: endpoint `POST /api/v1/promocoes/rejeitar-lote` (análogo ao `aprovar-lote` já existente) + botão "Rejeitar selecionadas" na barra de seleção.
4. Exibir mais campos no card: `regulamento_texto`/`regulamento_resumo`, `marketplace_status`, `abrangencia`, `restricoes`, `requer_clube`+`qual_clube`, `requer_cupom`+`cupom`, `disponibilidade` — hoje esses campos existem no banco e no schema `PromocaoIngerirIn`, mas não estão em `PromocaoOut` nem na tela.
**Arquivos possivelmente envolvidos:** `backend/api/v1/schemas.py` (adicionar campos a `PromocaoOut`), `backend/api/v1/promocoes.py` (novo endpoint de rejeição em massa), `backend/static/admin/index.html`.
**Critério de aceite:** as 4 melhorias funcionando no painel visual, testadas manualmente contra dados reais já no banco.
**Testes esperados:** nenhum automatizado ainda; validação manual no navegador.
**Riscos:** ao adicionar campos a `PromocaoOut`, garantir que os relacionamentos SQLAlchemy (`lazy="joined"`) continuem evitando N+1 queries.

### Tarefa 3 — Primeira rodada real de aprovações e validação do reprocessamento
**Objetivo:** sair do estado "0 promoções aprovadas" e validar que o motor de fato melhora com histórico real.
**Escopo:** revisar e aprovar um lote representativo de promoções pendentes (usando as ferramentas de aprovação em massa), depois rodar `POST /api/v1/promocoes/reclassificar-todas` e comparar as notas antes/depois usando o histórico de classificações já implementado.
**Arquivos possivelmente envolvidos:** nenhum código novo necessariamente — pode ser só operação via painel admin. Se o comportamento não for o esperado, revisar `backend/application/motor/historico.py` e `servico.py`.
**Critério de aceite:** promoções da mesma família (parceiro+programa) recebem notas visivelmente diferentes conforme a pontuação se compara ao histórico aprovado (não mais todas em ~55-67).
**Testes esperados:** validação manual comparando `criterios_avaliados.historico` antes e depois do reprocessamento.
**Riscos:** nenhum técnico direto; risco de negócio é aprovar promoções de baixa qualidade só para gerar histórico — vale avisar o usuário desse trade-off.

## 10. Roteiro da primeira sessão no Claude Code

1. Ler este arquivo (`docs/ai/HANDOFF.md`) por completo antes de qualquer ação.
2. Mapear o repositório: confirmar estrutura de pastas real vs. a descrita na seção 7, identificar se Git já foi inicializado (situação pode ter mudado desde a escrita deste handoff), rodar `docker compose ps` para ver o que está no ar, verificar se `coletor-nativo/venv` existe e está funcional.
3. Comparar a documentação em `docs/GAR-1100/` com o código real em `backend/` — sinalizar qualquer divergência encontrada (o código pode ter evoluído além do que está documentado, ou vice-versa).
4. Apontar explicitamente quaisquer lacunas ou inconsistências encontradas, incluindo status desatualizado neste handoff se algo já tiver mudado.
5. Propor um plano concreto para a Tarefa 1 (Git) ou a tarefa que o usuário priorizar, com passos claros.
6. **Não alterar nenhum arquivo até receber aprovação explícita do usuário** — inclusive não rodar `git init` ou criar `.gitignore` sem confirmação, mesmo sendo a tarefa recomendada com maior prioridade.

## 11. Documentos e arquivos para leitura prioritária

1. `docs/ai/HANDOFF.md` — este arquivo; ponto de entrada obrigatório.
2. `docs/GAR-1100/GAR-1100-Cap3-Modelo-PostgreSQL-Fisico-Rev2.md` — schema completo do banco, DDL de referência.
3. `docs/GAR-1100/GAR-1100-Cap4-Dicionario-de-Dados-V1.md` — significado campo a campo das tabelas mais sensíveis (`promocoes`, `classificacoes`, `configuracoes`).
4. `backend/domain/*.py` — modelos SQLAlchemy reais (fonte da verdade do schema em código, comparar com o Cap. 3).
5. `backend/application/motor/servico.py` e `pilares.py` — lógica do Motor de Análise V1, núcleo de negócio do sistema.
6. `backend/application/ingestao_service.py` — regra central de ingestão (dedup, cadastro automático de parceiro, acionamento do motor).
7. `coletor-nativo/coletor_livelo_nativo.py` — coletor real em produção; ler os comentários no topo do arquivo antes de qualquer alteração, explicam por que ele existe fora do Docker.
8. `backend/static/admin/index.html` — painel administrativo; ponto de partida para a Tarefa 2.
9. `docs/GAR-1100/GAR-1100-Cap8-Notas-Futuro-Emissoes.md` — contexto para não tomar decisões que dificultem o futuro Garimpo Emissões.
10. `docker-compose.yml` e `backend/Dockerfile` — antes de qualquer mudança de infraestrutura, notar o comentário sobre a tag `bookworm` (seção 5 deste handoff explica o porquê).