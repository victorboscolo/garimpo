# Handoff para Claude Code

> Revisado ao fim da sessão de 14/08/2026, que alterou substancialmente o
> sistema — coletor v3, comparação por segmento, pilares por percentil e
> publicação no Telegram. Os números aqui foram conferidos contra o banco na
> escrita, não reconstruídos de memória. A seção 12 lista as afirmações do
> handoff anterior que se provaram falsas — vale ler antes de confiar em
> qualquer documento mais antigo.

## 1. Resumo executivo

O **Garimpo Promoções** coleta, normaliza e analisa ofertas de pontuação de
programas de fidelidade (hoje só Livelo), calcula uma nota e categoria de
atratividade por um motor de regras determinístico (não é LLM) e expõe tudo
para revisão humana antes de qualquer divulgação. Existe um segundo produto
planejado, **Garimpo Emissões** (passagens aéreas via milhas), fora do escopo
atual, mas cuja arquitetura já foi antecipada nas tabelas polimórficas
(`classificacoes`, `arquivos` e `publicacoes` usam `entidade_tipo` +
`entidade_id` sem FK nativa, para servirem aos dois domínios).

**Estágio atual**: MVP funcional de ponta a ponta rodando localmente no Mac do
usuário. Coleta real diária, motor calibrado com dados reais, banco, API e
painel de revisão estão implementados e em uso. O repositório tem controle de
versão (33 commits) e 105 testes automatizados.

**O que mudou na sessão de 14/08**, em quatro frentes:

- **Coleta**: a listagem embute um JSON estruturado com tudo tipado. Trocar o
  regex por ele reduziu a coleta de ~3 minutos e ~50 navegações para **7
  segundos e uma requisição**, e trouxe dados que o texto renderizado nunca
  expôs — a pontuação fora de campanha e as categorias do parceiro.
- **Motor**: as notas eram todas 60,00. Hoje o motor diferencia, declara contra
  o que comparou cada oferta e pontua por **posição na distribuição** em vez de
  razão com a média, o que eliminou a saturação no topo.
- **Painel**: virou ferramenta de triagem — ordenado por nota, com ações em
  lote, critérios do motor e as condições da oferta visíveis.
- **Publicação**: o Telegram saiu do papel. Fila com curadoria humana, prévia da
  mensagem antes do envio e aviso quando o publicado deixa de valer.

## 2. Escopo atual e limites

**Dentro do escopo:**
- Coleta de ofertas "ganhe pontos" da Livelo (listagem + página de regras das
  campanhas ativas).
- Motor de Análise V1 (6 critérios ponderados, determinístico).
- Fila de revisão humana obrigatória — nenhuma publicação sem aprovação.
- Painel administrativo de triagem.

**Fora do escopo atual (adiado, não excluído):**
- Garimpo Emissões — o handoff anterior citava um `Cap8` de notas de
  arquitetura que **não existe no repositório** (há apenas Cap. 3 a 7).
- Publicação **automática** — a arquitetura prevê `modo: AUTOMATICO` em
  `configuracoes`, mas o disparo na aprovação não foi implementado a pedido do
  usuário: enquanto o motor amadurece, cada lote passa por curadoria. Configurar
  AUTOMATICO hoje registra um aviso e se comporta como MANUAL.
- Autenticação — endpoints são públicos; ver seção 8.
- Coletor da Esfera — programa cadastrado no banco, sem coletor.

**Premissas que precisam ser preservadas:**
- O sistema nunca contorna CAPTCHA, autenticação ou controle de acesso (seção 6).
- Promoções são **imutáveis no conteúdo**: mudança real de oferta cria registro
  novo, nunca sobrescreve. Há **uma exceção estreita e deliberada**, documentada
  na seção 5.
- Toda publicação passa por aprovação humana — decisão de produto.
- **Não se inventa dado.** Ver seção 5, é a regra de negócio mais reforçada pelo
  usuário ao longo da sessão.

## 3. Estado atual

| Componente | Status | Observação |
|---|---|---|
| Controle de versão | IMPLEMENTADO | 33 commits; `.gitignore` cobre `.env`, `venv/`, logs, `.pytest_cache` |
| Modelo de dados | IMPLEMENTADO | 18 tabelas, migrations 0001–0007 aplicadas |
| Motor de Análise V1 | IMPLEMENTADO | 6 pilares; comparativos por percentil; base em cascata (família → segmento → mercado) |
| Coletor Livelo nativo (macOS) | IMPLEMENTADO | lê o JSON estruturado da listagem; parsing de texto como fallback; 41 testes |
| Coletor Livelo em Docker | ABANDONADO | bloqueado por anti-robô (HTTP 403); não usar |
| Agendamento (`launchd`) | IMPLEMENTADO | coleta diária 10:05 e recalibração semanal seg. 11h; só roda com o Mac ligado |
| API (FastAPI) | IMPLEMENTADO | listagem ordenada, aprovação/rejeição individual e em lote, ingestão, reclassificação |
| Painel admin | IMPLEMENTADO | triagem por nota, ações em lote, critérios do motor, regulamento e selos |
| Testes automatizados | PARCIAL | 64 backend + 41 coletor, todos de lógica pura; nada de API/banco |
| Publicação (Telegram) | IMPLEMENTADO | fila com curadoria, prévia, envio em lote, diagnóstico e aviso de divergência |
| Autenticação | PENDENTE | ver seção 8 |
| Coletor Esfera | PENDENTE | nenhum código |

**Dados no banco (14/08/2026):**

| | |
|---|---|
| Promoções | 339 — 336 aprovadas, 3 rejeitadas, 0 pendentes |
| Parceiros | 255, praticamente todos com nome de exibição |
| Categorias de origem / vínculos | 37 / 500 |
| Publicadas no Telegram | 2 |

**Distribuição das notas:** Pouco atrativa 84, Comum 103, Boa 113, Excelente 28,
Excepcional 11. Antes desta sessão, **todas as notas eram 60,00**.

As faixas foram recalibradas junto com a mudança para percentil: como a nota
passou a medir posição no mercado, as faixas marcam posição também —
Excepcional é o topo 3%, Excelente o topo 12%, Boa é estar acima da mediana.
Manter os cortes antigos faria "Excelente" valer para um quarto do mercado.

**Base de comparação:** 281 classificações usam segmento (confiança MEDIA) e 58
caem no mercado (BAIXA). A justificativa de cada uma diz explicitamente contra o
que a oferta foi comparada e quanto do programa ela supera.

**Limitação viva:** só 26 dos 255 parceiros têm mais de uma oferta aprovada, e
por isso quase nenhuma classificação alcança confiança ALTA (histórico próprio
com 3+ campanhas). Como o coletor traz ~15 ofertas novas por dia distribuídas
entre 255 parceiros, cada um muda a oferta a cada duas ou três semanas — o
histórico próprio amadurece em meses. A cascata por segmento existe justamente
para o motor não ficar refém disso.

## 4. Arquitetura e fluxo de dados

```
Coletor nativo (macOS, fora do Docker, Chromium visível)
    → UMA requisição à listagem, e lê o JSON que a página embute:
      pontuação, parityBau (base), parityClub, separatorSlug ("Até"),
      promotion, datas com fuso, legalTerms (regulamento), nome e categorias
    → fallback: se o JSON não for encontrado, avisa e volta ao parsing do
      texto renderizado, que continua implementado
    → POST http://localhost:8000/api/v1/promocoes/ingerir
        ↓
Backend FastAPI (Docker)
    → application/ingestao_service.py:
        - calcula hash de dedup (ver aviso na seção 5)
        - resolve/cria Parceiro por (nome + código da variante)
        - sincroniza as categorias do parceiro (categorias_origem, N:N)
        - deriva valor_condicionado e marketplace_status (application/condicoes.py)
        - cria `promocoes` (status=PENDENTE) e aciona o motor
        - se for duplicata, complementa dados de campanha faltantes
        ↓
PostgreSQL (Docker, porta exposta só em 127.0.0.1)
        ↓
Painel (static/admin/index.html, servido pelo próprio FastAPI)
    → humano aprova ou rejeita, individualmente ou em lote
        ↓
application/publicacao_service.py
    → monta a fila: aprovadas, acima do limiar do canal, não vencidas e
      ainda não enviadas. A fila é derivada, nunca materializada
    → application/telegram/mensagens.py monta o texto por canal
    → infrastructure/telegram/cliente.py envia; cada tentativa vira uma
      linha em `publicacoes` (ENVIADO ou FALHA com o motivo)
```

**Por que o coletor roda fora do Docker:** a Livelo bloqueia (403) Chromium
headless, tanto em container Linux quanto nativo no macOS. Só o Chromium nativo
com janela visível (`headless=False`) passa. Testado e comprovado.

**Motor de Análise V1** (`backend/application/motor/`): Histórico 25%,
Atratividade 25%, Amplitude 20%, Facilidade 10%, Exclusividade 10%,
Confiabilidade dos dados 10% — pesos e faixas configuráveis via `configuracoes`,
sem deploy.

**Base de comparação em cascata** (`motor/historico.py`, `motor/segmento.py`):
o pilar Histórico tenta, nessa ordem, o histórico do próprio parceiro, depois o
segmento, depois o mercado. No segmento vale a categoria mais específica com
amostra suficiente, e o desempate entre iguais é alfabético de propósito — sem
critério estável a nota mudaria sozinha de um dia para o outro. A Exclusividade
**não** usa a cascata: "é o maior que este parceiro já ofereceu" é afirmação
sobre o parceiro, e trocá-la por "o maior do segmento" diria outra coisa. Distinção a preservar: `confianca_historica` (ALTA/MEDIA/BAIXA, por
volume de histórico aprovado) é **diferente** de `confiabilidade_dados` (0-100,
completude dos dados da campanha).

## 5. Decisões técnicas e de negócio

### Regra de negócio mais importante: não inventar dado

Reforçada três vezes pelo usuário na sessão, em contextos diferentes:

1. Uma taxa fixa de câmbio (1 USD = 5 BRL) foi proposta para ordenar ofertas de
   unidades diferentes e depois **descartada por ele**, mesmo servindo só à
   ordenação e não sendo gravada. Preferiu-se ordenar pela nota do motor, que é
   calculada a partir de dados reais.
2. O card da Livelo rotula uma segunda pontuação do Olympikus como "Clube",
   mas o regulamento diz "exclusivo para primeira compra". Decisão: **o
   regulamento é a fonte autoritativa**; sem menção no texto, não se afirma.
3. Uma variante do Beach Park estava nomeada com o termo que o usuário havia
   informado ("Hotéis") e a Livelo dizia "Hospedagens". Decisão dele: *"vamos
   seguir o que diz o Livelo, ele é a fonte da verdade"* — a fonte prevalece
   inclusive sobre o que ele mesmo descreveu.

Corolário aplicado no código: quando o dado não é observável, o campo fica
**nulo**, nunca preenchido por dedução. É por isso que `marketplace_status` fica
nulo nas ofertas cujo regulamento nunca foi lido, em vez de "PERMITIDO".

### A listagem embute um JSON estruturado

Descoberto em 14/08/2026 e hoje é o caminho principal do coletor
(`coletor-nativo/parceiros_json.py`). A página traz um objeto por parceiro com
os dados já tipados, o que dispensou tanto o regex sobre texto renderizado
quanto a visita a ~50 páginas de regras por coleta.

Dois campos só existem ali: `parityBau`, a pontuação fora de campanha — a Liga
Vitória Consórcio anuncia "até 100" e volta a 1 —, e `categories`, a
classificação do parceiro.

Duas armadilhas encontradas ao integrar, ambas ligadas ao hash:

- `parityClub` vem preenchido nos 253 parceiros, quase sempre igual à pontuação
  normal. Como o campo entra no hash, gravá-lo em todos teria mudado o hash da
  base inteira. Só é registrado quando é **maior** que a pontuação normal — 20
  casos, não 253.
- `parceiro_nome_bruto` continua vindo do slug da URL, e **não** do `name` do
  JSON, pelo mesmo motivo: participa da identidade e do hash.

É estrutura interna do site e pode mudar sem aviso, por isso o parsing de texto
segue implementado como fallback.

### Pilares comparativos por percentil

A curva original era `pontuação ÷ referência × 50`, com teto em 100 — o dobro da
referência já era nota máxima. Como as médias de segmento ficam entre 2 e 3
pontos e a de mercado em 5,5, o teto caía entre 4 e 11, enquanto o mercado
oferece 20, 40 e 100 pontos. O motor ficava cego justamente no topo, que é onde
as decisões de publicação acontecem: 38 classificações empatadas em 100 no pilar
Histórico e 33 no de Atratividade, com uma oferta de 12 pontos valendo o mesmo
que uma de 40.

A nota passa a ser a posição na distribuição de referência. Empates dividem a
posição, o que importa porque a mediana do mercado é 2 pontos e metade das
ofertas empata nesse valor.

O ganho decisivo é ser **autocalibrante**: se todas as ofertas dobrarem, ninguém
muda de posição e portanto ninguém muda de categoria. Com a curva anterior, uma
inflação geral do mercado passaria despercebida.

### Amostra mínima antes de usar o histórico próprio

Uma única oferta anterior não é histórico, é coincidência: a Riachuelo passou de
3 para 7 pontos e o pilar devolvia 100, afirmando "o dobro do normal" a partir
de uma observação só. 95 classificações estavam nessa situação, 29 delas como
Excelente ou Excepcional. Abaixo de duas observações a cascata cai no segmento.

Registrado como limite honesto: isso **não** resolve o caso da Riachuelo. O
usuário sabe que ela costuma chegar a 10 pontos; o sistema viu duas ofertas.
Nenhuma mudança de curva substitui observação — só tempo de coleta.

### ⚠️ O hash de deduplicação

`calcular_hash` (`application/ingestao_service.py`) define se uma oferta
coletada é "a mesma de ontem" (descartada) ou mudança real (registro novo).
Entram nele: programa, nome do parceiro, código da variante, pontuação, marca de
teto, pontuação de clube, unidade, clube e cupom.

**Alterar essa fórmula invalida todos os hashes gravados.** A coleta seguinte
trataria as ~250 ofertas existentes como novas e duplicaria o histórico já
revisado à mão. Qualquer mudança exige um script que recalcule
`promocoes.hash_promocao` **usando a própria função** — ver
`backend/scripts_backfill/backfill_0003.py` e `0004.py`, que fazem exatamente
isso e foram verificados simulando o envio do coletor.

Campos derivados ou de contexto ficam **fora** do hash de propósito:
`regulamento_texto`, datas, `pontuacao_anterior`, `em_promocao`,
`valor_condicionado`, `marketplace_status`. Eles descrevem a oferta, não a
definem.

### Exceção à imutabilidade

`_completar_dados_da_campanha` preenche, numa promoção já existente, campos de
campanha que só passamos a coletar depois. É deliberado e estreito: sem isso as
campanhas já gravadas nunca receberiam seu regulamento, porque o hash não muda e
a promoção seria descartada como duplicata. **Só preenche o que está vazio** e
nunca toca no conteúdo da oferta.

### Outras decisões

| Decisão | Justificativa |
|---|---|
| Identidade do parceiro = nome + `codigo_externo` da URL | `beach-park/BPK` (Hospedagens) e `/BHP` (Ingressos) são ofertas distintas; sem o código, o motor usava o histórico de uma como se fosse da outra |
| `nome_exibicao` separado de `nome` | `nome` entra no hash e na identidade; renomear ali faria a coleta seguinte não reconhecer o parceiro. O `nome_exibicao` **sincroniza** com o `alt` da logo, então renomear à mão no banco não se sustenta |
| Pontuação "Até X" é gravada como X | Decisão de produto do usuário: o valor anunciado é o que se apresenta, por causa do apelo de marketing. O que muda é `pontuacao_e_teto` marcar que é limite e o motor descontar a confiabilidade |
| `valor_condicionado` compara o valor exibido com a escada do regulamento | Sem palavra-chave e sem fator arbitrário: se o número exibido é o degrau de cima e há um degrau abaixo, é condicionado. Se já é o piso (caso comum das ofertas com Clube), não é |
| Detalhe só dos cards com selo "Promoção" | ~50 páginas (~3 min) em vez de 248 (~12 min), e é onde o regulamento existe |
| Lote tolera falha parcial | Uma promoção que saiu de PENDENTE entre o carregamento e o clique é ignorada e reportada, em vez de derrubar o lote |
| Painel em HTML/JS puro, sem framework | Ferramenta interna para 1-2 pessoas; simplicidade de deploy |
| `codigo` BigInteger usa `Identity()` explícito | Sem isso o ORM assíncrono envia NULL no INSERT e o Postgres rejeita |
| Imagem Docker fixada em `python:3.12-slim-bookworm` | A tag genérica `slim` migrou para Debian trixie, que não tem os pacotes que o Playwright espera |

## 6. Fontes, coleta e conformidade

**Fonte:** `https://www.livelo.com.br/juntar-pontos/todos-os-parceiros` (público,
sem login) e as páginas de regras dos parceiros com campanha ativa.

- Coleta 1x/dia às 10:05, e recalibração semanal às segundas 11h — ambas pelo
  `launchd`, que recupera execuções perdidas quando o Mac dorme. O agendador em
  container foi removido justamente por descartá-las: acumulava avisos de "run
  time was missed by 3:17:28" enquanto disparava o coletor bloqueado.
- **A CONFIRMAR**: o horário da coleta se baseia num entendimento informal de que
  a Livelo atualiza às 10h; não há fonte oficial.
- Uma navegação por página, sem paralelismo. A visita ao detalhe acrescenta ~50
  navegações sequenciais.
- **Nenhuma credencial, cookie de sessão ou bypass é usado.** O sistema não
  implementa e não deve implementar contorno de CAPTCHA, rate limit ou controle
  de acesso. A solução (navegador real, visível, nativo) opera dentro do que um
  usuário humano faria ao abrir a página.
- Segredos ficam em `.env` (não versionado). `.env.example` tem só placeholders.

**Coleta hoje:** uma única requisição, ~7 segundos. O JSON da listagem traz o
regulamento de praticamente todos os parceiros, inclusive dos que não têm
campanha ativa — o que revelou exigências de cupom antes invisíveis (Havaianas,
Época Cosméticos). A visita a páginas de detalhe deixou de ser necessária.

## 7. Convenções de desenvolvimento

**Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 async / Alembic / Pydantic v2;
PostgreSQL 16; coletor em Python 3.9 com Playwright; painel em HTML/CSS/JS
vanilla; Docker Compose.

```
backend/
  api/v1/          # rotas e schemas
  application/     # ingestao_service.py, condicoes.py, divergencia.py,
                   #   publicacao_service.py, telegram/mensagens.py,
                   #   motor/ (pilares, historico, segmento, percentil, servico)
  infrastructure/  # db/ e telegram/cliente.py (só envia; lê o token do .env)
  domain/          # modelos SQLAlchemy
  infrastructure/  # conexão com o banco
  migrations/      # Alembic (0001–0007)
  scripts_backfill/# backfills pontuais, com dry-run
  static/admin/    # painel
  tests/           # 64 testes de lógica pura
coletor-nativo/    # roda fora do Docker, venv próprio
  coletor_livelo_nativo.py # orquestra a coleta; fallback de texto
  parceiros_json.py        # lê o JSON estruturado da página (caminho principal)
  test_coletor_livelo.py + test_parceiros_json.py   # 41 testes
scripts/           # recalibrar.sh + plist do launchd, backup.sh
docs/GAR-1100/     # arquitetura (Cap. 3 a 7)
docs/ai/           # este handoff
```

**Comandos:**
```bash
docker compose up -d                                    # sobe tudo
docker compose exec backend alembic upgrade head        # migrations
docker compose exec backend python -m pytest tests/ -q  # testes do backend
cd coletor-nativo && ./venv/bin/python3 -m pytest test_coletor_livelo.py -q
open http://localhost:8000/admin/                       # painel
cd coletor-nativo && ./venv/bin/python3 coletor_livelo_nativo.py   # coleta manual
launchctl start com.garimpo.coletor-livelo              # força a coleta
./scripts/recalibrar.sh                                 # reprocessa tudo agora
```

**Testes:** a suíte cobre **lógica pura** — parsing do coletor, faixas do motor,
hash de dedup, regras de condição. Não há teste de API nem de banco; isso
exigiria pytest-asyncio e um banco de teste, e nunca foi montado. O painel é
validado manualmente no navegador.

**Atenção:** o `pytest` está no `requirements.txt`, mas se a imagem estiver
defasada ele some do container. `docker compose build backend` resolve.

**Commits:** mensagens em português, explicando o *porquê* e não só o *o quê*.

## 8. Pendências e riscos

| Item | Tipo | Impacto | Próximo passo |
|---|---|---|---|
| Sem autenticação | Segurança | Médio | Portas já restritas a `127.0.0.1`, o que fecha o acesso pela rede. Uma chave de API no `/ingerir` seria o próximo passo; JWT completo é desproporcional hoje |
| `aprovada_por` nulo nas 275 | Auditoria | Baixo hoje | Depende de haver usuários; importa quando houver mais de um revisor |
| Poucos parceiros com histórico próprio | Limitação temporária | Médio | 26 de 255; a cascata por segmento cobre o resto enquanto amadurece |
| Agrupamento canônico vazio | Curadoria | Baixo | `categorias_origem.categoria_id` nulo nos 37 slugs; preencher reduz os agrupadores sem recoletar |
| Coletor depende do Mac ligado | Operacional | Médio | Coleta diária pode falhar em silêncio; não há monitoramento |
| Sem teste de API/banco | Qualidade | Médio | Vários bugs desta sessão (MissingGreenlet, MultipleResultsFound, fuso na validade, canal não configurado bloqueando o lote) só apareceram em execução real |
| Rejeitadas com classificação velha | Consistência | Baixo | `reclassificar-todas` pula REJEITADAS por desenho; 2 registros mantêm categoria de antes da recalibração |
| Canal PUBLICO sem ID | Configuração | Baixo | Só o AVANCADO existe; a fila ignora canais não configurados |
| Categorias de parceiro vazias | Lacuna | Médio | 8 categorias cadastradas, 0 dos 249 parceiros classificado. Impede comparação por segmento |
| Horário de atualização da Livelo | Premissa | Baixo | Observar empiricamente |

## 9. Próximas tarefas recomendadas

### Tarefa A — Histórico na tela (desenho aprovado, não implementado)
Duas seções novas dentro do "Ver detalhes" que já existe, carregadas **sob
demanda** ao expandir o card, para não voltar a fazer centenas de requisições no
carregamento:
- **Histórico da nota desta promoção** — como a avaliação evoluiu. Endpoint
  `GET /promocoes/{id}/classificacoes` já existe.
- **Histórico de ofertas deste parceiro** — como a oferta mudou ao longo dos
  dias. `GET /promocoes?parceiro_id=X` já existe.

Não precisa de endpoint novo nem migration — é trabalho só de tela.

### Tarefa B — Calibrar com o retorno dos validadores
A publicação está pronta e as duas primeiras mensagens foram enviadas a um canal
de validadores — pessoas de uma agência de viagens, que vão criticar tanto a
oferta quanto a avaliação. O retorno delas é o insumo que falta para calibrar:
pesos, faixas e o texto das mensagens são todos dados em `configuracoes` ou
strings, ajustáveis sem deploy.

### Tarefa C — Teste de API e banco
As três falhas mais caras desta sessão passaram por toda a suíte de lógica pura
e só apareceram rodando o coletor de verdade. Montar pytest-asyncio com banco de
teste fecharia essa lacuna.

## 10. Roteiro da próxima sessão

1. Ler este arquivo por completo.
2. Conferir o estado real antes de agir: `git log --oneline`, `docker compose ps`,
   contagem por status em `promocoes`. **Os números da seção 3 são de 14/08 e
   envelhecem a cada coleta diária.**
3. Conferir se a coleta automática das 10:05 rodou e quantos registros criou. O
   esperado é ~15/dia; centenas indicariam que o hash foi invalidado (seção 5).
4. Perguntar ao usuário a prioridade antes de escolher tarefa.
5. Não alterar arquivos sem aprovação explícita.

## 11. Leitura prioritária

1. Este arquivo.
2. `backend/application/ingestao_service.py` — dedup, identidade do parceiro,
   exceção à imutabilidade. É o coração das regras.
3. `backend/application/condicoes.py` — como se decide "condicionada" e o
   alcance no marketplace.
4. `backend/application/motor/pilares.py` e `servico.py` — os 6 critérios.
5. `coletor-nativo/coletor_livelo_nativo.py` — ler os comentários do topo antes
   de mexer; explicam por que ele vive fora do Docker.
6. `backend/static/admin/index.html` — painel.
7. `docs/GAR-1100/GAR-1100-Cap3-Modelo-PostgreSQL-Fisico-Rev2.md` — schema
   físico de referência.
8. `docs/GAR-1100/GAR-1100-Cap4-Dicionario-de-Dados-V1.md` — significado campo a
   campo. **Atenção:** os capítulos 3 e 4 descrevem o schema original e não
   incluem as colunas adicionadas pelas migrations 0003 a 0006; a fonte da
   verdade do schema é `backend/domain/*.py`.

## 12. Afirmações do handoff anterior que se provaram falsas

Registradas para que ninguém as reutilize:

- *"Aprovação em massa já existe, falta a rejeição"* — **nenhuma das duas
  existia**. Ambas foram implementadas em 14/08.
- *"Histórico de notas expansível já implementado"* — não existia, e ainda não
  existe. O desenho está na Tarefa A.
- *"251 pendentes, 0 aprovadas"* — desatualizado já na abertura da sessão.
- *"O nome do parceiro só aparece numa ferramenta que sintetiza texto a partir
  de atributos `alt` — não é texto real do DOM"* — **conclusão errada**. O `alt`
  é dado real do DOM e está presente nos 248 cards; é a única fonte que nomeia
  as variantes (Liga Vitória Consórcio, Hero Seguro Viagem).
- *"Endpoints hoje só acessíveis via localhost"* — era falso. O
  `docker-compose.yml` publicava em todas as interfaces, deixando API e banco
  alcançáveis por qualquer aparelho da rede. Corrigido em 14/08.
- Referência a `docs/GAR-1100/GAR-1100-Cap8-Notas-Futuro-Emissoes.md` — o
  arquivo **não existe**; o diretório tem apenas os capítulos 3 a 7. As notas de
  arquitetura do Garimpo Emissões, se existirem, estão fora deste repositório.
