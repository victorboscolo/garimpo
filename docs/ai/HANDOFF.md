# Handoff para Claude Code

> Revisado em 21/08/2026, ao fim de uma sessão de cinco dias. Os números aqui
> foram conferidos contra o banco na escrita, não reconstruídos de memória. A
> seção 12 lista as afirmações de handoffs anteriores que se provaram falsas —
> vale ler antes de confiar em qualquer documento mais antigo.

## 1. Resumo executivo

O **Garimpo Promoções** coleta, normaliza e analisa ofertas de pontuação de
programas de fidelidade (**Livelo e Esfera**, desde 17/08/2026), calcula uma
nota e categoria de atratividade por um motor de regras determinístico (não é
LLM) e expõe tudo para revisão humana antes de qualquer divulgação. Existe um
segundo produto planejado, **Garimpo Emissões** (passagens aéreas via milhas),
**com schema, endpoints, o parser dos dois sistemas de busca da Azul e o
catálogo de 107 rotas prontos (21/08), ainda sem orquestração nem dado
real coletado** — seção 5 tem o mapa completo do que é viável e o que não é.

**Estágio atual**: MVP funcional de ponta a ponta rodando localmente no Mac do
usuário, dois programas de fidelidade coletando em paralelo, automaticamente,
sem intervenção diária. Motor calibrado com dados reais, banco, API e painel
de revisão estão implementados e em uso. 72 commits, 108 testes automatizados
de backend (84 de lógica pura + 23 de integração API/banco + 1 smoke test de
migration) + 22 do coletor de Emissões + 43 coletor Livelo (41 + 2 do fix de
caixa do `codigo_externo`) + 9 coletor Esfera. Backup diário rodando de
verdade, o Painel de Saúde avisa no Telegram sozinho quando um job falha ou
atrasa, e o Garimpo Emissões (só Azul, seats.aero fechou pro Brasil) já sabe
interpretar preço real dos dois sistemas de busca da Azul.

**O que mudou na sessão de 17–21/08**, em dezessete frentes:

- **Esfera no ar e publicando**: segundo programa de fidelidade, coletado por
  uma API pública sem proteção alguma. 176 aprovadas, primeiro lote publicado
  no Telegram (49 mensagens no total, Livelo + Esfera).
- **Categoria canônica movida do slug para o parceiro**: curadoria manual real
  de 423 parceiros mostrou que um slug de origem largo ("casaedecoracao")
  reúne parceiros de natureza bem diferente — a decisão de categoria precisa
  viver no vínculo parceiro↔slug, não no slug. Migration 0008; 14 categorias,
  669 vínculos classificados, cobertura de 100%. Ver seção 5.
- **Mensagens reorganizadas**: nome do programa, tópicos rotulados
  (Pontuação, Validade, Cupom), regulamento truncado por tamanho. E um bug
  real corrigido: a detecção de "regulamento real" só reconhecia a frase da
  Livelo, escondendo o bloco de regulamento em **100% dos cards da Esfera**
  no painel mesmo quando o dado existia.
- **Garimpo Emissões investigado a fundo, sem código de produção**: testadas
  Smiles, LATAM Pass e Azul/TudoAzul diretamente, mais a API do seats.aero
  como alternativa. Resultado: só a Azul é viável por conta própria hoje;
  Smiles e LATAM estão fechadas. Mapa completo na seção 5.
- **Testes de integração contra API e banco reais** (Tarefa D): banco de teste
  `garimpo_test`, `pytest-asyncio`, isolamento por SAVEPOINT, 5 testes cobrindo
  ingestão de ponta a ponta, reclassificação em lote, fila de publicação com
  canal não configurado e a regressão do bug de regulamento da Esfera.
- **Histórico no painel** (Tarefa C): o card de detalhes agora mostra o
  histórico de reclassificações da nota e as ofertas anteriores do mesmo
  parceiro, carregados sob demanda ao abrir o card.
- **Aprovação individual avisa em vez de reclassificar** (Tarefa E): decisão
  tomada — a aba Publicar mostra um aviso quando há aprovação mais nova que a
  última reclassificação geral, com atalho para reprocessar.
- **Bug de identidade corrigido e duplicata fundida**: o `codigo_externo` da
  Livelo podia gravar em caixas diferentes pro mesmo parceiro entre uma coleta
  e outra, fazendo-o virar dois `Parceiro` no banco (achado real: "Bankei").
  Causa raiz corrigida no coletor; os dois registros já existentes foram
  fundidos.
- **Painel de Saúde**: cada job (coletor Livelo, coletor Esfera, recalibração,
  backup) registra o próprio resultado ao terminar; nova aba no painel mostra
  quem está OK, atrasado, falhou ou nunca rodou.
- **Backup real, pela primeira vez**: existia desde a arquitetura original mas
  nunca tinha sido agendado, e os destinos configurados nem existiam no disco.
  Agora roda diário via `launchd`, Postgres → Google Drive.
- **Painel de Saúde passou a avisar, não só mostrar** (19/08): FALHA dispara
  Telegram na hora; ATRASADA é checado a cada 6h. A primeira execução real
  agendada do backup falhou (`docker` fora do PATH do `launchd`) — o próprio
  painel pegou, corrigido no mesmo dia.
- **`pytest-asyncio` desatualizado no `requirements.txt`**: pinava uma versão
  incompatível com o `pytest` já pinado; só não quebrava porque o container
  rodando tinha uma instalação avulsa, nunca reconstruída. Corrigido; suíte
  inteira validada a partir de uma imagem reconstruída do zero.
- **Power Nap derrubou a coleta da Livelo** (20/08): o Painel de Saúde pegou
  de novo — terceira falha real que ele acusou desde que foi ao ar.
  Corrigido agendando um despertar de verdade (`pmset repeat wake`).
- **seats.aero fechado pro Brasil**: resposta definitiva, não "ainda não
  aprovado". Usuário decidiu seguir só com a Azul.
- **Garimpo Emissões: arquitetura inicial + achado do `azulpelomundo`**:
  schema e endpoints prontos; descoberto que a Azul tem dois sistemas de
  busca — o site principal (só malha própria) e o portal `azulpelomundo`
  (parceiros, protegido por Akamai Bot Manager). Matriz de rotas fechada
  com o usuário.
- **Coletor de Emissões: URL + parser prontos pros dois sistemas**, testados
  contra dado real: `azulpelomundo` via JSON (`GET /api/availability`),
  site principal via DOM renderizado (achado 21/08 — a rede não foi
  interceptável, mas o preço mora num `data-test-id` estável no HTML,
  mesmo princípio do fallback de texto da Livelo).
- **Emissões vira por perna, não por pacote, e a busca vira só-ida de
  verdade** (21/08, feedback do usuário depois de um teste manual de
  ponta a ponta): uma oferta de ida sozinha tem mais alcance de público e
  dá liberdade pro usuário. `data_volta`/`voo_direto` saíram do schema;
  entraram `paradas` (int, número de conexões) e `assentos_restantes`
  (migration 0011). Consequência técnica que o usuário também confirmou:
  como o preço da ida dentro de um pacote combinado pode ser mais barato
  que comprá-la sozinha, a busca em si precisou virar só-ida nos dois
  sistemas — revalidado empiricamente contra buscas reais (`/flights/OW/`
  no `azulpelomundo`, sem os parâmetros `c[1].*` no site principal). 22
  testes no coletor. Ver seção 5.
- **Catálogo de rotas populado** (21/08): 107 `RotaEmissao` carregadas
  (77 site principal + 30 azulpelomundo) a partir da matriz fechada com o
  usuário, via `scripts_backfill/seed_rotas_emissao.py`, idempotente. A
  linha de teste antiga (`OfertaEmissao` da era ida-e-volta, 511.980
  pontos, com `paradas`/`assentos_restantes` nulos) foi removida — não
  fazia sentido misturar com dado real daqui pra frente.

## 2. Escopo atual e limites

**Dentro do escopo:**
- Coleta de ofertas "ganhe pontos" da Livelo (listagem + página de regras das
  campanhas ativas) e da Esfera (API pública de parceiros).
- Motor de Análise V1 (6 critérios ponderados, determinístico), rodando por
  programa — cada um compara suas ofertas só contra as do próprio programa.
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
- Comparação entre parceiros dos dois programas (ex: "Renner rende mais na
  Livelo ou na Esfera agora?") — 52 parceiros já têm nome idêntico nos dois
  programas na base atual. A peça que faltaria (`Marca` agrupando vários
  `Parceiro`) já existe no modelo, mas não há curadoria de correspondência
  nem tela para isso. Registrado como possibilidade a pedido do usuário, não
  como tarefa.

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
| Controle de versão | IMPLEMENTADO | 45 commits, working tree limpo; `.gitignore` cobre `.env`, `venv/`, logs, `.pytest_cache` |
| Modelo de dados | IMPLEMENTADO | 18 tabelas, migrations 0001–0008 aplicadas |
| Motor de Análise V1 | IMPLEMENTADO | 6 pilares; comparativos por percentil, escopados por programa; base em cascata (família → segmento → mercado) |
| Coletor Livelo nativo (macOS) | IMPLEMENTADO | lê o JSON estruturado da listagem; parsing de texto como fallback; 41 testes |
| Coletor Livelo em Docker | ABANDONADO | bloqueado por anti-robô (HTTP 403); não usar |
| Coletor Esfera | IMPLEMENTADO | `coletor-esfera/`; API pública sem anti-robô nenhum, Python simples (`httpx`); 9 testes |
| Agendamento (`launchd`) | IMPLEMENTADO | Livelo 10:05, Esfera 10:20, recalibração semanal seg. 11h; só roda com o Mac ligado |
| API (FastAPI) | IMPLEMENTADO | listagem ordenada, aprovação/rejeição individual e em lote, ingestão, reclassificação |
| Painel admin | IMPLEMENTADO | triagem por nota, ações em lote, critérios do motor, regulamento e selos; fila de publicação com descarte; card de detalhes com histórico da nota e das ofertas anteriores do parceiro (sob demanda); aba Saúde com o status de cada job |
| Painel de Saúde | IMPLEMENTADO | tabela `execucoes` + `GET /api/v1/saude`; coletor Livelo, coletor Esfera, recalibração e backup registram o próprio resultado ao terminar (sucesso/falha, contadores, erro); situação OK/FALHA/ATRASADA/NUNCA_RODOU por job; **aviso ativo no Telegram (19/08)**: FALHA dispara na hora, ATRASADA é checado a cada 6h (`scripts/verificar_saude.sh`) |
| Backup | IMPLEMENTADO (18/08, corrigido 19/08) | diário via launchd (10:40), Postgres → Google Drive (camada de HD externo é opcional, só grava se já estiver montado); retenção de 30 backups na nuvem; sem criptografia (decisão, ver seção 5). Falhou na primeira execução agendada de verdade (`docker: command not found` — PATH do launchd não inclui `/usr/local/bin`); o próprio Painel de Saúde pegou, corrigido no mesmo dia |
| Testes automatizados | PARCIAL | 108 backend (84 de lógica pura + 23 de integração API/banco + 1 smoke test de `alembic upgrade head`) + 43 coletor Livelo + 9 coletor Esfera. Cobre os fluxos onde já apareceu bug real; não é cobertura exaustiva |
| Garimpo Emissões | EM CONSTRUÇÃO (21/08) | Schema por perna (`rotas_emissao`, `ofertas_emissao` com `paradas`/`assentos_restantes`, migration 0011) e endpoints prontos, sem motor. Coletor: URL + parser só-ida prontos pros dois sistemas da Azul (22 testes, contra dado real). Catálogo de rotas populado (107 linhas). Orquestração Playwright escrita (`coletor_emissoes_azul.py`) mas bloqueada por rate-limit no fim do dia 21/08, ainda não rodou com sucesso de ponta a ponta — retomar amanhã. Nenhuma oferta real coletada ainda. Ver seção 5 |
| Publicação (Telegram) | IMPLEMENTADO | fila com curadoria, prévia, envio em lote, descarte, diagnóstico e aviso de divergência; mensagem por tópicos, com nome do programa |
| Autenticação | PENDENTE | ver seção 8 |

**Dados no banco (18/08/2026):**

| | |
|---|---|
| Promoções | 561 — 380 aprovadas Livelo + 5 rejeitadas Livelo + 176 aprovadas Esfera, 0 pendentes |
| Parceiros | 422 (mesma marca em programas diferentes ainda vira `Parceiro` separado, seção 2 — a duplicata "Bankei" por `codigo_externo` em caixas diferentes foi fundida em 18/08, ver seção 5) |
| Categorias de origem / vínculos | 65 slugs / 669 vínculos, em 2 programas |
| Categorias canônicas | 15 (8 originais + 7 criadas na curadoria: Beleza, Infantil, Pet, Presentes, Seguros e Consórcios, Serviços, Varejo). **669 de 669 vínculos classificados — cobertura de 100%**, curadoria manual completa (seção 5) |
| Publicadas no Telegram | 49, todas AVANCADO (Livelo + Esfera). Canal PUBLICO segue sem ID configurado |

As faixas foram recalibradas junto com a mudança para percentil: como a nota
passou a medir posição no mercado, as faixas marcam posição também —
Excepcional é o topo 3%, Excelente o topo 12%, Boa é estar acima da mediana.
Manter os cortes antigos faria "Excelente" valer para um quarto do mercado.

**Limitação viva:** poucos parceiros por programa têm mais de uma oferta
aprovada, e por isso quase nenhuma classificação alcança confiança ALTA
(histórico próprio com 3+ campanhas). Isso vale ainda mais para a Esfera, que
começou do zero nesta sessão. A cascata por segmento existe justamente para o
motor não ficar refém disso.

## 4. Arquitetura e fluxo de dados

```
Coletor Livelo (macOS, fora do Docker, Chromium visível)
    → UMA requisição à listagem, e lê o JSON que a página embute:
      pontuação, parityBau (base), parityClub, separatorSlug ("Até"),
      promotion, datas com fuso, legalTerms (regulamento), nome e categorias
    → fallback: se o JSON não for encontrado, avisa e volta ao parsing do
      texto renderizado, que continua implementado

Coletor Esfera (macOS, fora do Docker por padrão operacional — não por
necessidade; a API não bloqueia nem dentro do Docker)
    → UMA requisição a uma API REST pública (coletor-esfera/esfera_api.py):
      pontuação, prefixo "até", unidade (real/dólar, em texto livre),
      regulamento e categorias da taxonomia "new_"
    → SEM pontuação fora de campanha nem datas de campanha — a Esfera não
      expõe campo limpo para isso (seção 5)
        ↓ (os dois coletores convergem aqui)
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

**Por que o coletor da Livelo roda fora do Docker:** ela bloqueia (403)
Chromium headless, tanto em container Linux quanto nativo no macOS. Só o
Chromium nativo com janela visível (`headless=False`) passa. Testado e
comprovado. **O coletor da Esfera não tem esse motivo** — roda fora do Docker
só para manter um único padrão de agendamento via `launchd` junto com o da
Livelo; poderia rodar dentro do Docker sem problema técnico.

**Motor de Análise V1** (`backend/application/motor/`): Histórico 25%,
Atratividade 25%, Amplitude 20%, Facilidade 10%, Exclusividade 10%,
Confiabilidade dos dados 10% — pesos e faixas configuráveis via `configuracoes`,
sem deploy. Todas as bases de comparação (`_mercado`, cascata do Histórico) são
filtradas por `programa_id`: a Esfera nunca é comparada contra a Livelo, nem
o contrário.

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

### A Esfera não tem anti-robô — e não tem campo limpo para tudo

Descoberto em 17/08/2026: `GET apigw.esfera.com.vc/bff-product/ehcs/products
?categoryId=esf02163` devolve os ~168 parceiros de "Lojas Parceiras" num único
request, sem cookie, sessão ou qualquer header especial — confirmado com
`curl` puro. Por isso o coletor (`coletor-esfera/`) é Python simples, sem
Playwright, ao contrário do da Livelo.

A API é rica (~200 campos por item), mas dois campos que a Livelo dá de
graça **não têm equivalente limpo** na Esfera:

- **Pontuação fora de campanha** (`pontuacao_base`, o `parityBau` da Livelo):
  só aparece em texto livre do regulamento ("O acúmulo padrão é de 2
  pontos..."), com redação que varia por parceiro. Um teste em 167 parceiros
  ativos achou esse padrão em só 36.
- **Datas de início/fim de campanha**: o campo dedicado (`esf_tempOfferInit`/
  `End`) está vazio (placeholder `"dd-mm-yyyy HH:MM"`) em 167 dos 168
  parceiros — só a data em prosa está preenchida, com formato inconsistente
  entre parceiros (a Casas Bahia aplica datas diferentes por categoria na
  mesma frase).

**Decisão**: os dois campos ficam `None` para a Esfera. Tentar extrair por
regex arriscaria inventar dado a partir de um padrão que só bate numa minoria
dos casos — na prática, mensagens sem "🗓 Validade" e sem "📉 fora da campanha"
para a Esfera, até que a fonte exponha (ou passe a preencher) algo confiável.

### Duas taxonomias de categoria em paralelo na Esfera — escolhida a "new\_"

Cada parceiro da Esfera carrega categorias de duas taxonomias simultâneas:
`esf_categorias_*` (a antiga, slugs como `esf02163`) e `new_categorias_*`/
`new*` (nomes como `newModaCalcadosAcessorios`), esta última parecendo ser
para onde a própria Esfera está migrando. Escolhida a `new_`: precisa
dialogar com as categorias da Livelo na camada canônica (`categorias`,
`categorias_origem.categoria_id`), e nomes legíveis se prestam mais a esse
agrupamento futuro do que os slugs numéricos da taxonomia antiga.

`_categorias()` em `coletor-esfera/esfera_api.py` descarta o contêiner
universal (`new02163`, presente nos 168 parceiros — equivalente ao "todos" da
Livelo) e mantém o resto sem julgar qual é canônica; isso é curadoria
posterior, como já era para a Livelo.

### Categoria canônica por parceiro, não por slug (18/08)

A curadoria manual de 423 parceiros (planilha preenchida pelo usuário,
423 linhas, aplicada em 18/08) revelou que `categorias_origem.categoria_id`
(a decisão da seção anterior) não sustenta a realidade: um slug de origem
largo como `casaedecoracao` (Livelo, 27 parceiros) reúne desde Electrolux até
Riachuelo, e a curadoria real distribuiu esse slug sozinho em **7 categorias
canônicas diferentes**, a depender do parceiro. Guardar a categoria no slug
faria a decisão de um parceiro vencer a de outro que só por acaso compartilha
o mesmo slug bruto.

Migration 0008 move o campo para `parceiro_categorias.categoria_id` — o
vínculo parceiro↔slug, não o slug sozinho. `categorias_origem.categoria_id`
não foi removido (fica como fallback de nível de slug, hoje sem uso — 0 de
65 preenchidos). A cascata de segmento em `motor/historico.py` resolve pela
categoria do parceiro quando existe, com fallback pro slug bruto quando não
há curadoria — comportamento antigo preservado onde não há dado novo.

Confirmado após aplicar: Midea (Livelo, slug `casaedecoracao`) agora compara
com o segmento "Eletrônicos" (32 ofertas), não mais com um segmento que
misturava eletrônico, casa, moda e mercado por acidente de slug.

### Arranque a frio de um programa novo — resolvido pelo fluxo existente, sem código novo

Sem histórico próprio nem mercado formado, os pilares Histórico e Atratividade
caem no neutro (50) para toda oferta de um programa recém-coletado — o mesmo
problema da Livelo em 14/08, agora por programa. Pedido do usuário: coletar e
classificar, mas **não publicar** até haver base real.

Não foi preciso nenhum mecanismo novo: publicação só alcança quem está
`APROVADA`, e aprovar continua sendo decisão humana no painel — a
`justificativa` de cada classificação já diz honestamente "sem base de
comparação disponível ainda" ou `confianca_historica: BAIXA`. O gate já
existia; só não tinha sido testado com um programa começando do zero.

### Mensagens: tópicos pré-determinados, nome do programa, regulamento truncado

Com dois programas publicando no mesmo canal, três ajustes em
`application/telegram/mensagens.py`:

1. **Nome do programa** passa a aparecer junto do parceiro (`Renner
   (Esfera)`) — antes só o link no fim da mensagem indicava a origem, e o
   usuário precisava disso *antes* de abrir a mensagem, não só ao clicar.
2. **Tópicos rotulados** substituem bullets soltos para o que já é dado
   limpo: 💰 Pontuação (junta valor atual, Clube e "fora da campanha" — são
   fatos sobre a mesma coisa), 🗓 Validade, 🎫 Cupom. **Escopo foi
   propositalmente deixado de fora**: não existe campo confiável para isso em
   nenhum dos dois programas, e rotular uma leitura que o dado não sustenta é
   pior que não ter o tópico — `test_escopo_nunca_e_rotulado` é guarda de
   regressão contra isso.
3. **Regulamento truncado por tamanho**, não por conteúdo: o maior regulamento
   real da Livelo tem 484 caracteres; a mediana da Esfera é 1106, com 166 dos
   167 parceiros passando de 500 — o texto ali é majoritariamente mecânica
   genérica do programa (esvaziar carrinho, CPF cadastrado, prazo de crédito),
   repetida em quase toda oferta. Acima de 500 caracteres, corta no último
   espaço e acrescenta "(regulamento completo no link abaixo)" — nunca julga
   *o quê* é útil, só limita *quanto* cabe na mensagem. O texto integral
   continua salvo no banco e a um clique, no link que toda mensagem já traz.

### Bug: detecção de "regulamento real" reconhecia só a frase da Livelo

`_tem_regulamento_real` (`ingestao_service.py`) e sua cópia em JS no painel
verificavam a presença da frase "campanha válida" — específica da Livelo —
para distinguir regulamento de verdade do placeholder que o coletor antigo
gravava ("Coletado do site oficial..."). A Esfera nunca usa essa frase: **0
dos 168 regulamentos reais dela contêm isso**. Efeito prático: o bloco de
regulamento em destaque **nunca aparecia em nenhum card da Esfera no
painel**, mesmo com regulamento completo salvo; e o backend reescrevia à toa
o campo em toda coleta duplicada da Esfera, achando que o dado salvo "não era
real".

Corrigido invertendo a lógica: só não é real quando bate o padrão do
placeholder antigo (`PADRAO_FRASE_DO_COLETOR`, já existia em
`condicoes.py`), não quando falta uma frase de uma fonte específica. Depois
do fix: bloco de regulamento passou a aparecer em 287 das 364 promoções da
Livelo (era 73) e nas 167 da Esfera (era 0).

### Aprovação individual: avisar, não reclassificar (18/08)

Pendência da seção 8 anterior, decidida pelo usuário: seguir a recomendação
de só avisar. `application/divergencia.py::aprovacoes_apos_ultima_reclassificacao`
compara o timestamp da aprovação mais recente (`promocoes.aprovada_em`) com o
da reclassificação mais recente (`max(classificacoes.processada_em)`) — se uma
aprovação avulsa é mais nova, ela ainda não influenciou a base de comparação
de mais ninguém. `GET /publicacoes/aviso-reclassificacao` expõe isso e a aba
Publicar mostra um aviso com botão "Reprocessar tudo agora", no mesmo padrão
já usado pro aviso de divergência.

### Bug: `codigo_externo` da Livelo podia gravar em caixas diferentes para o mesmo parceiro (18/08)

Causa raiz do "Bankei duplicado" (seção 8): o coletor da Livelo tem dois
caminhos que podem originar `codigo_externo` — o "id" do JSON estruturado
(`parceiros_json.py`) e o último segmento da URL do link (`_extrair_codigo_da_url`
em `coletor_livelo_nativo.py`). Os dois extraem o valor verbatim da própria
Livelo, sem normalizar; quando a própria Livelo serviu o código em caixas
diferentes num e noutro (`"ban"` vs `"BAN"`), a busca exata de `Parceiro` por
`codigo_externo` no `ingestao_service.py` não reconheceu que era o mesmo
parceiro, e criou um segundo registro.

Corrigido maiusculizando o código nos dois pontos de extração (não no
`ingestao_service.py`, que trata `codigo_externo` de forma genérica pros dois
programas): a caixa não tem significado semântico, só identifica, e os
próprios testes já documentavam o padrão maiúsculo ("BPK", "DCR") como
esperado. **Só vale pra Livelo** — a Esfera não foi tocada, porque os códigos
dela (`"e000100025"...`) são nativamente minúsculos e normalizar seria alterar
um dado que a fonte não trata como maiúsculo, o que violaria a regra de não
inventar/transformar dado.

Os dois registros duplicados de "Bankei" existentes no banco foram fundidos
manualmente (as 2 promoções passaram a apontar para o `Parceiro` com código
"BAN"; o duplicado com "ban" e sua `Marca` órfã foram removidos) — a correção
no coletor evita repetir, mas não desfaz o que já tinha sido gravado.

### Painel de Saúde: cada job se auto-reporta, em vez de o painel sondar (18/08)

Decisão de desenho: quem sabe se um job deu certo é o próprio job — o coletor
Livelo sabe se a coleta falhou, o backup sabe se a cópia pro Drive funcionou.
Por isso `POST /api/v1/execucoes` é chamado por quem executa, ao terminar
(sucesso ou falha), em vez do painel tentar inferir a saúde sondando cada
sistema de fora. Mais simples, e cada job já loga exatamente esses números
pro próprio arquivo de log — só passou a mandar pra API também.

`job` na tabela `execucoes` não é FK: o conjunto é pequeno e fixo
(`coletor_livelo`, `coletor_esfera`, `recalibracao`, `backup`), não um
cadastro que cresce. "Mais recente" usa `codigo` (BigInteger Identity), não
`created_at` — dentro de uma mesma transação Postgres, `now()` devolve
sempre o mesmo valor, o que fez duas execuções de teste na mesma transação
empatarem em `created_at` (achado real, testes/test_integracao_saude.py).

Janela de atraso por job (`JANELA_POR_JOB` em `application/saude_service.py`)
é "cadência esperada + folga larga" — os horários reais são só entendimento
informal (seção 6), então a folga evita falso alarme por uma execução um
pouco mais lenta que o normal.

Reportar nunca pode derrubar o próprio job: um coletor que falha ao registrar
a execução (ex: API fora do ar) só loga um aviso e segue — a ausência do
report é exatamente o sinal que o painel deveria mostrar como ATRASADA/FALHA,
travar o coletor por causa disso seria pior.

Escopo deliberadamente pequeno: aba nova na barra de tabs já existente, não
uma página inicial com menus — pra um painel de 1-2 pessoas que já sabe onde
cada coisa fica, uma segunda camada de navegação só duplicaria a barra.

### Backup: nunca tinha rodado (18/08)

Achado ao revisar robustez do sistema: `scripts/backup.sh` existia desde a
arquitetura original mas nunca foi agendado via `launchd` (ao contrário dos
coletores e da recalibração), e os dois destinos que o script assumia por
padrão (`/Volumes/BackupGarimpo`, `~/Google Drive/...`) não existiam no
disco. A única cópia dos dados vivia só no volume Docker de um único Mac.

Corrigido: Google Drive para computador instalado e logado nesta sessão; o
caminho real da pasta sincronizada é
`~/Library/CloudStorage/GoogleDrive-<email>/Meu Drive` (as versões atuais do
app não usam mais `~/Google Drive`). Backup agendado via `launchd` às 10:40
(depois das duas coletas), com retenção de 30 backups na nuvem.

A camada de HD externo (opcional) só grava se o ponto de montagem já existir
de verdade — o script nunca faz `mkdir -p` nele. Antes, um HD desconectado
não causava erro nenhum: `mkdir -p /Volumes/BackupGarimpo/postgres` cria
silenciosamente uma pasta comum no disco interno (já que `/Volumes/` é
gravável), dando a falsa impressão de que existe uma cópia fora da máquina
quando não existe nenhuma. Sem criptografia por ora — o banco não guarda
credencial nem dado pessoal de terceiros, decisão revisitável se isso for
para um servidor externo algum dia.

### Bug: testes mandavam Telegram de verdade (20/08)

Achado pelo próprio usuário — recebeu dois alertas reais no Telegram
("Coletor Livelo falhou: timeout na Livelo" e "Backup falhou: disco cheio")
que não correspondiam a nada real no Painel de Saúde nem nos logs. Causa:
dois testes em `test_integracao_saude.py`, escritos antes do aviso ativo
existir (Tarefa G), registravam uma `FALHA` de teste sem mockar
`cliente.enviar` — como o container roda com `TELEGRAM_BOT_TOKEN` e
`TELEGRAM_CANAL_ALERTA_ID` reais (do `.env`), toda rodada da suíte completa
disparava as duas mensagens de verdade. Não sujou o banco de produção (os
testes rodam contra `garimpo_test`, isolado) — só gerou ruído real no
Telegram, repetido a cada vez que a suíte rodou depois da Tarefa G.

Corrigido com uma fixture `autouse` em `conftest.py` que mocka
`cliente.enviar` como no-op pra **todo** teste por padrão, não só os dois
que causaram o problema — fecha essa classe de bug de vez. Testes que
querem inspecionar o envio (`test_integracao_alerta_saude.py`) continuam
podendo sobrescrever com seu próprio `monkeypatch`, validado que ainda
funciona.

### Power Nap derrubou a coleta da Livelo — o Painel de Saúde pegou de novo (20/08)

Terceiro bug real que o Painel de Saúde acusou (depois do PATH do backup em
19/08): a coleta da Livelo falhou às 10:20 de 20/08 com
`Page.goto: Timeout 30000ms exceeded`, mas o log mostrava a navegação
começando às 10:14:58 — um timeout de 30s não explica 5 minutos de
diferença entre início e erro. `pmset -g log` revelou a causa: o Mac não
estava desligado nem em sono profundo ininterrupto — ele entrava e saía de
**Power Nap (DarkWake)**, uma janela de manutenção breve (mDNS, Time
Machine, esse tipo de tarefa leve), não um despertar completo:

```
10:14:54  DarkWake (Power Nap) começa
10:14:56  Mac volta a dormir — só 2s de janela, no meio da navegação
10:20:03  próximo DarkWake — só aí o Playwright, com CPU de novo,
          termina de contar os 30s de timeout e desiste
```

O `launchd` tinha disparado o job da Livelo durante essa primeira janela
curta (recuperando a execução perdida das 10:05, como sempre fez), mas o
Chromium precisa de tempo contínuo pra carregar uma página de verdade — uma
janela de Power Nap não garante isso. A Esfera, no mesmo intervalo, rodou
sem problema: é uma requisição HTTP simples (sem navegador), cabe inteira
numa janela curta.

Corrigido agendando um despertar de verdade antes do horário da coleta:
`sudo pmset repeat wake MTWTFSS 09:55:00`, dado pelo usuário (não é algo
que eu possa rodar — exige privilégio de admin). Confirmado com
`pmset -g sched` mostrando `Repeating power events: wake at 9:55AM`, e
validado recoletando a Livelo manualmente — 10 criadas, 244 descartadas, 0
falhas.

### Painel de Saúde: aviso ativo no Telegram, e dois bugs reais achados no processo (19/08)

FALHA e ATRASADA não são a mesma coisa, e cada uma pede um mecanismo
diferente (`application/saude_service.py`):

- **FALHA é evento** — acontece no instante em que um job registra a
  execução via `POST /api/v1/execucoes`. `registrar_execucao` dispara o
  aviso ali mesmo, na hora.
- **ATRASADA é estado, não evento** — ninguém "avisa" que ficou atrasado,
  ele só fica assim conforme o tempo passa sem ninguém reportar. Só dá pra
  pegar isso com checagem periódica: `scripts/verificar_saude.sh`, via
  `launchd` a cada 6h (`StartInterval`, não horário de calendário — não
  importa a hora exata, só a regularidade), chama
  `POST /api/v1/saude/verificar-atrasados`.

**Sem deduplicação, de propósito**: enquanto o job continuar atrasado, o
alerta se repete a cada checagem (até 4x/dia). Um alarme que avisa uma vez e
depois se cala deixaria a falha esquecida até a próxima olhada manual — pra
um sistema de 1-2 pessoas, insistir é mais seguro que ficar quieto.

Canal novo, `ALERTA` (`TELEGRAM_CANAL_ALERTA_ID`), separado de PUBLICO e
AVANCADO — aviso operacional não é conteúdo que assinante deveria ver. É o
DM direto do usuário com o bot (`chat_id` obtido mandando uma mensagem pro
bot e consultando `getUpdates`), não um canal novo — mais simples pra quem
hoje é a única pessoa acompanhando operação.

**Dois bugs reais encontrados ao colocar isso no ar, nenhum relacionado ao
alerta em si**:

1. O backup, agendado desde 18/08, falhou na primeira execução real do
   `launchd` com `docker: command not found`. O `launchd` roda com um PATH
   mínimo (sem `/usr/local/bin`), diferente do shell interativo onde o
   script tinha sido testado à mão — por isso passou no teste manual e
   falhou no agendamento de verdade. Corrigido exportando o PATH no início
   do script; validado de novo simulando o ambiente do `launchd` (`env -i`
   com PATH mínimo), não só rodando no terminal normal. **O próprio Painel
   de Saúde foi quem acusou isso** — a razão de ele existir.
2. `requirements.txt` pinava `pytest-asyncio==0.24.0`, que exige
   `pytest<9` — incompatível com o `pytest==9.1.1` já pinado desde a Tarefa
   D. Um `docker compose build` limpo falhava com `ResolutionImpossible`;
   só não quebrava até aqui porque o container `backend` rodando tinha uma
   instalação avulsa de `pytest-asyncio`, nunca reconstruída desde que a
   Tarefa D foi implementada. Descoberto ao recriar o container pra pegar a
   variável nova do `.env` (`TELEGRAM_CANAL_ALERTA_ID`), o que apagou o
   estado avulso e expôs o conflito real. Corrigido fixando
   `pytest-asyncio==1.4.0`; suíte inteira (103 testes) validada a partir de
   uma imagem reconstruída do zero, não do container antigo.

### Testes de integração: banco de teste e a armadilha do event loop do pytest-asyncio (18/08)

`backend/tests/conftest.py` sobe um segundo banco (`garimpo_test`, mesmo
Postgres do docker-compose) e isola cada teste numa transação com SAVEPOINT
por baixo — necessário porque o próprio código de produção chama `db.commit()`
(ex: `ingerir_promocao_bruta`), e sem o savepoint um commit real encerraria a
transação de isolamento do teste.

Armadilha encontrada: o `pytest-asyncio` (modo `auto`) dá a cada teste um
event loop **novo**. Uma engine/conexão asyncpg criada como fixture de sessão
(escopo `session`) fica presa ao loop do primeiro teste que a usa, e o
segundo teste — rodando num loop diferente — recebe
`RuntimeError: ... attached to a different loop`. `NullPool` sozinho não
resolve, porque o problema não é reaproveitar conexão do pool: é a própria
fixture de banco (`db`, escopo função) sendo criada em um loop e usada em
outro quando o escopo da fixture e o do loop do teste não coincidem.

Solução: nada de fixture `session`-scoped para o schema. `Base.metadata.create_all()`
roda uma vez, fora do ciclo do pytest, com `asyncio.run()` direto na coleta do
`conftest.py` — um loop descartável, só para preparar o schema. Cada teste
então abre sua própria conexão (`NullPool`, sem pool persistente entre loops)
dentro do loop que o pytest-asyncio já criou pra ele. Vale registrar para não
repetir a investigação: o sintoma (`attached to a different loop`) não aponta
para a causa raiz de forma óbvia.

### Garimpo Emissões — investigação de viabilidade (Smiles, LATAM, Azul, seats.aero)

Nenhum código de produção foi escrito; isto documenta o que foi aprendido
testando as três companhias diretamente e uma alternativa comercial, pra não
repetir a investigação do zero numa sessão futura.

**O problema é estruturalmente diferente de Promoções.** Livelo e Esfera são
catálogo: uma lista relativamente estável, coletada 1x/dia. Busca de milhas é
consulta sob demanda — depende de origem, destino e data; não existe "lista
de hoje" pra baixar de manhã. Isso muda o modelo de coleta inteiro, não é só
"mais um programa".

| Programa | Situação | Detalhe |
|---|---|---|
| **Smiles (GOL)** | **Fechada, sem caminho técnico conhecido** | Akamai Bot Manager bloqueia até dentro de navegador real e visível — o mesmo truque que resolve a Livelo não resolve aqui. `curl` puro: HTTP 406. Dentro do navegador: erro de CORS + HTTP 452 na chamada de busca (`api-air-flightsearch-green.smiles.com.br`), reproduzido em sessão nova, sem carga acumulada de outros testes |
| **LATAM Pass** | **Fechada por autenticação, não por técnica** | Exige login pessoal antes de buscar com milhas — não é proteção anti-robô, é barreira de acesso deliberada. Decisão: não automatizar login em nome do usuário, mesmo com credencial fornecida por ele — contornaria a mesma premissa de nunca contornar controle de acesso (seção 2). API oficial de desenvolvedor (`developers.latam-pass.latam.com`) existe mas é pra parceiro comercial formal resgatar produto de catálogo pré-definido (ex: iPad, PlayStation), não busca de voo |
| **Azul/TudoAzul** | **Viável, testada e mapeada** | Busca funciona sem login. Protegida por Akamai na borda (bloqueia `curl` puro, HTTP 403), mas passa dentro de navegador real. Achado chave: **a primeira busca da sessão precisa vir de navegação normal** (carregar a home, passar pelo formulário) — depois disso, buscas por URL direta funcionam encadeadas. Teto observado: por volta de 10 buscas encadeadas por sessão aquecida (não é número fixo, variou entre testes); a partir daí, reaquecer (nova navegação normal) recupera **instantaneamente**, sem esperar. Trocar de rota no meio da sessão não piora nada — mesmo comportamento de só mudar data. Dado real coletado: preço em pontos varia até 3x pra mesma rota em poucos dias (VCP→MCO: 213k a 613k pontos) |

**Endpoints reais encontrados** (documentados, não implementados):
- Smiles: `api-air-flightsearch-green.smiles.com.br/v1/airlines/search`
- LATAM: `www.latamairlines.com/bff/web-products-searchbox/v1/calendar` (calendário de tarifa **em dinheiro**, não muda pra pontos mesmo com "usar milhas" marcado — não serve pra Emissões)
- Azul: `b2c-api.voeazul.com.br/tudoAzulReservationAvailability/api/tudoazul/reservation/availability/v6/availability`, e a entrega de resultado passa por um canal de "Listen" do Google Firestore (`firestore.googleapis.com/.../azul-storage-prd`), não uma API REST convencional

**Alternativa investigada: API do seats.aero.** Agregador comercial
(`seats.aero`) que já faz esse scraping em escala — cobre GOL Smiles e
Azul/TudoAzul, mas **confirmado que não cobre LATAM Pass** (nem ele, nem o
concorrente AwardFares — nenhuma ferramenta comercial do mercado resolveu
LATAM Pass ainda). Usar a API deles eliminaria toda a complexidade de sessão
da Azul e destravaria a Smiles, que não tem alternativa própria. Restrições
relevantes dos termos deles: atribuição visível obrigatória em qualquer
lugar que mostre o dado; uso automatizado só pra fins não-comerciais sem
permissão por escrito ("Commercial Purpose" é definido de forma ampla —
inclui afiliação com entidade que gera receita); voos além de 60 dias não
podem ser mostrados publicamente sem OAuth ou acordo comercial. Conta Pro do
usuário já existe, mas **não é elegível pra API automaticamente** — pedido
de elegibilidade enviado ao suporte deles em 18/08. **Resposta em 19/08:
negativa — a API não está disponível para o Brasil.** Não é "ainda não
aprovado", é um "não" definitivo por geografia; não faz sentido insistir ou
reenviar o pedido. Esse caminho está fechado.

**Achado de segurança/legal, não só técnico**: a Air Canada processa o
Seats.aero alegando que scraping automatizado de disponibilidade de prêmio é
fraude computacional (linguagem de CFAA); o Seats.aero se defende como
concorrência legítima. É litígio real e em andamento — motivo a mais pra não
construir scraping próprio de Smiles/LATAM como se fosse trivial, mesmo
quando tecnicamente possível.

**Monitoramento automático criado**: rotina mensal (`trig_01VNZZmfuWBgzaA6QcRU3BB7`,
todo dia 1º) verifica se seats.aero ou AwardFares passaram a suportar LATAM
Pass; só notifica se algo mudar. Continua valendo — é um eixo diferente
(suporte a LATAM Pass) do que fechou agora (disponibilidade da API pro
Brasil), não fica obsoleta por causa da resposta negativa.

**Onde isso deixa o Emissões (19/08)**: com o seats.aero fechado pro Brasil,
o único caminho que sobra é construir um coletor próprio, e só cobre a Azul
— Smiles continua bloqueada pelo Akamai e LATAM continua exigindo login
(seção 2, premissa de nunca contornar autenticação). Antes o plano era "se
o seats.aero aprovar, cobre Smiles+Azul de uma vez; se não, a Azul sozinha
já tem arquitetura mapeada". Agora não tem mais "se" — ou é Azul sozinha
(aquecer sessão, lotes de ~8 buscas, reaquecer, mapeado na tabela acima),
ou o Emissões fica em pausa. Decisão de produto em aberto, não tomada:
vale construir um coletor de Emissões que cobre só 1 de 3 programas?

**Decisão de produto pra quando (se) a coleta de Emissões avançar**: sem
nota automática por enquanto — o sistema não tem histórico suficiente pra
calibrar isso, e o usuário tem anos de experiência pessoal em milhas que vale
mais que qualquer heurística nova. Aprovação manual mostraria um texto padrão
("Excelente oportunidade"), sem expor a mecânica por trás — mesmo princípio
de sempre, nota é interna. Discutido também: separar sinal de "queda de
preço ao longo do tempo" (a mesma rota fica mais barata) do sinal de "valor
por milha" (preço em milhas vs. preço em dinheiro do mesmo voo) — são coisas
diferentes, o segundo exige também coletar o preço em dinheiro do mesmo voo,
não feito ainda.

### Garimpo Emissões — arquitetura inicial e o achado do `azulpelomundo` (20/08)

Com o seats.aero fechado pro Brasil (seção anterior) e a decisão do usuário
de seguir só com a Azul, dois avanços no mesmo dia: a matriz de rotas foi
fechada com o usuário, e a investigação técnica revelou que a Azul tem
**dois sistemas de busca diferentes**, não um.

**O site principal (`voeazul.com.br`)** só busca a malha **própria** da
Azul — confirmado por duas fontes: a página oficial de rotas diz
literalmente "mais de 150 destinos no Brasil, além dos internacionais para
Flórida, Lisboa e Paris", e um teste real (GRU→Londres) devolveu "não
temos voos disponíveis". As parcerias de companhia aérea que a Azul tem
(United, Air Canada, Copa, TAP, Emirates, Etihad, Turkish) são **só de
ganhar pontos** voando com elas — não existe resgatar milhas Azul num
voo delas por esse site.

**`azulpelomundo.voeazul.com.br`** é outro sistema, achado pelo usuário
(ele lembrava do nome) — cobre **"+3.000 destinos com Pontos Azul"**,
incluindo voos de parceiros de verdade (testado: GRU→JFK devolveu voo
vendido pela Avianca; GRU→Londres devolveu 10 opções, uma delas voo
direto). Achados técnicos:
- Protegido por **Akamai Bot Manager** (cookies `_abck`/`bm_*`) — mais
  forte que a proteção do site principal. Bare `curl` e replay dos cookies
  reais de uma sessão de navegador real **os dois devolvem 403** ("Access
  Denied" do Akamai) — precisa mesmo do fingerprint de navegador
  verdadeiro, não só dos cookies. Nunca vai dar pra chamar a API direto
  (como fazemos com a Esfera); todo o coletor de Emissões passa por
  automação de navegador.
- Endpoint real: `GET /api/availability?origin=...&destination=...&cabinCategory=...`.
- Mesmo truque de sessão do site principal funciona aqui: depois de uma
  primeira busca pelo formulário, dá pra navegar direto pra
  `/flights/RT/{origem}/{destino}/-/-/{data-ida}/{data-volta}/1/0/0/0/0/ALL/F/{classe}/-/-/-/-/A/-`
  e continuar recebendo resultado, sem re-passar pelo formulário. Testado
  6 buscas internacionais encadeadas seguidas (Londres, JFK, Madrid, Roma,
  Miami, Los Angeles) sem nenhum bloqueio — não fui além disso hoje, o
  teto real ainda não foi mapeado (o do site principal ficou em ~8-11).
- **Escopo é só internacional/parceiro**: testei uma rota doméstica
  (GRU→Salvador) nesse portal e quebrou (erro de JS, não bloqueio) —
  Nordeste/Sul/Minas Gerais continuam sendo busca no site principal.

**Matriz de rotas fechada com o usuário (20/08)**:
- Origens: GIG, SDU, GRU, CGH, VCP
- Cruzado SP↔RJ entre as 5 (site principal)
- Nordeste: SSA, REC, FOR, BPS, MCZ, NAT (site principal)
- Sul (proposta minha, aceita): POA, FLN, CWB (site principal)
- Minas Gerais (proposta minha, aceita): CNF — é também o hub internacional
  da própria Azul (site principal)
- Malha própria internacional: Flórida/MCO, Lisboa/LIS, Paris/**ORY** (não
  CDG — confirmado pelo usuário e batido com o teste real; site principal)
- Internacional via parceiro (`azulpelomundo`): Londres/LHR, Madrid/MAD,
  Roma/FCO, JFK, MIA, LAX. Usuário mencionou FLL como provável também —
  não testado ainda. Porto (OPO) também ficou pendente de teste.
- Classe: Econômica **e** Executiva
- Datas: 30 a 180 dias à frente, amostrado em ~6 pontos (não diário — o
  volume diário seria inviável, ver a conversa sobre cortar volume)
- Critério de preço: **só a oferta mais barata** por rota+data+classe
  (decisão do usuário, 19/08) — não guardar a lista inteira de voos
  retornada.

**Arquitetura implementada (20/08, ainda sem coletor)**: migration 0010,
`domain/emissoes.py` (`RotaEmissao` — catálogo curado, campo `fonte`
marca qual dos dois sistemas buscar; `OfertaEmissao` — imutável, uma linha
por coleta, é o que sustenta o histórico de preço), `application/emissoes_service.py`,
endpoints `POST /api/v1/emissoes/ofertas` (rejeita rota fora do catálogo
em vez de criar sozinho) e `GET /api/v1/emissoes/rotas`. 5 testes de
integração. **Reaproveita** o `Dominio` "EMISSOES" que o schema já previa,
e cria um `Programa` "Azul" novo sob ele — não usa `Promocao` (natureza de
dado diferente, ver docstring do módulo).

**Não feito ainda**: popular `rotas_emissao` com a matriz acima (os nomes
de campo exatos ficaram como "ver com calma depois"), o coletor de verdade
(Playwright, falando com os dois sistemas), e qualquer decisão de tela/
publicação — não faz sentido desenhar isso antes de ter dado fluindo.

### Garimpo Emissões — por perna, não por pacote, e busca só-ida de verdade (21/08)

Depois da arquitetura inicial (seção anterior), o usuário pediu pra fazer
**um caso só e verificar a exibição** antes de seguir — teste manual de
ponta a ponta com a rota GIG→MCO já validada: busca real no site
principal → parser do DOM → `POST /api/v1/emissoes/ofertas` → conferido
direto no banco. Funcionou (`OfertaEmissao` gravada com 511.980 pontos),
mas o teste era ida-e-volta, e foi olhando esse resultado que o usuário
deu quatro pontos de feedback que mudaram o modelo:

1. **Rastrear por perna, não por pacote ida+volta** — uma promoção de ida
   sozinha tem mais alcance de público e dá liberdade pro usuário não
   ficar preso a uma data de volta específica.
2. Pergunta sobre o significado de "AD" na operadora — é o código IATA da
   própria Azul (confirmado decodificando o `id` do card, que traz o
   itinerário completo em base64).
3. **Trocar `voo_direto` (booleano) por `paradas` (inteiro)** — direto
   vira só o caso `paradas == 0`, e a informação é estritamente maior.
4. **Gravar assentos restantes**, quando a fonte expõe — o site principal
   já tem esse dado no DOM (`data-leg-remaining-seats`), de graça.

O ponto 1 tinha uma consequência técnica que não era óbvia à primeira
vista, e foi levantada e confirmada com o usuário antes de implementar:
descartar a perna de volta de uma busca ida-e-volta **não é a mesma
coisa** que buscar só-ida de verdade, porque o preço da ida dentro de um
pacote combinado pode ser mais barato do que comprá-la sozinha. Então a
mudança de modelo também exigia mudar o modo de busca nos dois sistemas
— usuário confirmou as duas coisas juntas ("1. CONFIRMADO / 2.
CONFIRMADO").

**Schema (migration 0011)**: `OfertaEmissao` perdeu `data_volta` e
`voo_direto`, ganhou `paradas: int | None` e `assentos_restantes: int |
None`. Só existia 1 linha na tabela no momento da migration (o teste
manual acima) — sem dado de produção perdido. `application/emissoes_service.py`,
`api/v1/emissoes.py` e os testes de integração foram atualizados junto;
108 testes de backend passando.

**Busca só-ida revalidada empiricamente nos dois sistemas** (não bastava
supor o padrão a partir da versão ida-e-volta):

- `azulpelomundo`: `tripType=ONE_WAY` na URL
  (`/flights/OW/{origem}/{destino}/-/-/{data-ida}/-/1/0/0/0/0/ALL/F/{classe}/-/-/-/-/A/-`,
  confirmado via `window.location.href` numa busca real GRU→LIS). No JSON
  de resposta, `returnFlights` vem `null` e o `points.value` no nível do
  próprio voo já é o preço real da perna — ao contrário da versão
  ida-e-volta, onde esse campo era só o trecho de ida isolado e o preço
  combinado morava um nível mais fundo. A taxa em reais também sobe um
  nível, pra `recommendations[0].fee.total.value`. E um achado bônus:
  `connection` é o número de conexões de verdade (uma busca real GRU→HND
  trouxe `connection: 1` com `flightGroup` de duas pernas GRU→JFK→HND),
  não um booleano — vira `paradas` direto, sem conversão.
- Site principal: a URL só-ida larga os parâmetros `c[1].*` (perna de
  volta) por completo, mantendo o resto igual (confirmado numa busca real
  GIG→MCO). O DOM não muda — os mesmos anchors (`data-test-id`,
  `data-leg-remaining-seats`) continuam valendo, só que a página passa a
  ter uma seção em vez de duas. O número de paradas mora no texto do
  card, em dois formatos reais confirmados: `"1 conexão · Voo 4450"` (com
  conexão) e `"Voo 4043 Direto"` (sem conexão, sem número na frente,
  confirmado numa busca real VCP→CNF).

`urls.py`, `parsing.py`, `parsing_site_principal.py` e seus testes/fixtures
foram reescritos pra só-ida, sempre contra captura real (nunca JSON ou
HTML inventado) — 22 testes no coletor. Ver `coletor-emissoes-azul/README.md`
pro detalhe técnico completo.

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

**Livelo:** `https://www.livelo.com.br/juntar-pontos/todos-os-parceiros`
(público, sem login) e as páginas de regras dos parceiros com campanha ativa.
Uma única requisição, ~7 segundos — o JSON da listagem traz o regulamento de
praticamente todos os parceiros, inclusive dos que não têm campanha ativa.

**Esfera:** `https://apigw.esfera.com.vc/bff-product/ehcs/products
?categoryId=esf02163` (API pública, sem login, sem cookie). Uma única
requisição devolve os ~168 parceiros de "Lojas Parceiras" completos.

- Coleta 1x/dia — Livelo às 10:05, Esfera às 10:20 (15 min de folga, pra não
  disputar recursos no mesmo minuto) — e recalibração semanal às segundas 11h.
  Todas pelo `launchd`, que recupera execuções perdidas quando o Mac dorme. O
  agendador em container foi removido justamente por descartá-las: acumulava
  avisos de "run time was missed by 3:17:28" enquanto disparava o coletor
  bloqueado.
- **A CONFIRMAR**: os horários se baseiam num entendimento informal de quando
  cada programa atualiza; não há fonte oficial para nenhum dos dois.
- Livelo: uma navegação por página, sem paralelismo. Esfera: uma requisição
  HTTP só, sem navegador.
- **Nenhuma credencial, cookie de sessão ou bypass é usado em nenhum dos dois.**
  O sistema não implementa e não deve implementar contorno de CAPTCHA, rate
  limit ou controle de acesso. A Livelo exige navegador real, visível, nativo,
  para operar dentro do que um usuário humano faria; a Esfera nem isso exige,
  porque a própria fonte já expõe os dados sem proteção.
- Segredos ficam em `.env` (não versionado). `.env.example` tem só placeholders.

## 7. Convenções de desenvolvimento

**Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 async / Alembic / Pydantic v2;
PostgreSQL 16; coletor Livelo em Python 3.9 com Playwright; coletor Esfera em
Python 3.9 só com `httpx`; painel em HTML/CSS/JS vanilla; Docker Compose.

```
backend/
  api/v1/          # rotas e schemas
  application/     # ingestao_service.py, condicoes.py, divergencia.py,
                   #   publicacao_service.py, telegram/mensagens.py,
                   #   motor/ (pilares, historico, segmento, percentil, servico)
  infrastructure/  # db/ e telegram/cliente.py (só envia; lê o token do .env)
  domain/          # modelos SQLAlchemy
  migrations/      # Alembic (0001–0008)
  scripts_backfill/# backfills pontuais, com dry-run
  static/admin/    # painel
  tests/           # 78 de lógica pura + 8 de integração (conftest.py, banco garimpo_test)
coletor-nativo/    # coletor Livelo, roda fora do Docker (bloqueio anti-robô), venv próprio
  coletor_livelo_nativo.py # orquestra a coleta; fallback de texto
  parceiros_json.py        # lê o JSON estruturado da página (caminho principal)
  test_coletor_livelo.py + test_parceiros_json.py   # 41 testes
coletor-esfera/    # coletor Esfera, roda fora do Docker só por padrão operacional, venv próprio
  coletor_esfera.py # orquestra a coleta e envia pra API
  esfera_api.py      # busca e mapeia os campos da API pública da Esfera
  test_esfera_api.py # 9 testes
scripts/           # recalibrar.sh, backup.sh (Postgres -> Google Drive),
                   #   verificar_saude.sh (aviso de atraso) + plists do launchd
docs/GAR-1100/     # arquitetura (Cap. 3 a 7)
docs/ai/           # este handoff
```

**Comandos:**
```bash
docker compose up -d                                    # sobe tudo
docker compose exec backend alembic upgrade head        # migrations
docker compose exec backend python -m pytest tests/ -q  # testes do backend
cd coletor-nativo && ./venv/bin/python3 -m pytest -q
cd coletor-esfera && ./venv/bin/python3 -m pytest test_esfera_api.py -q
open http://localhost:8000/admin/                       # painel
cd coletor-nativo && ./venv/bin/python3 coletor_livelo_nativo.py   # coleta manual Livelo
cd coletor-esfera && ./venv/bin/python3 coletor_esfera.py          # coleta manual Esfera
launchctl start com.garimpo.coletor-livelo               # força a coleta Livelo
launchctl start com.garimpo.coletor-esfera               # força a coleta Esfera
./scripts/recalibrar.sh                                  # reprocessa tudo agora
```

**Testes:** a maior parte da suíte cobre **lógica pura** — parsing dos dois
coletores, faixas do motor, hash de dedup, regras de condição, montagem de
mensagem. Desde 18/08 há também 8 testes de **integração** (`tests/test_integracao_*.py`)
contra API e banco reais (`garimpo_test`, ver `tests/conftest.py`) — cobrem o
caminho request → serviço → ORM → banco que os testes de lógica pura não
alcançam. O painel continua validado manualmente no navegador.

**Atenção:** o `pytest` está no `requirements.txt`, mas se a imagem estiver
defasada ele some do container. `docker compose build backend` resolve.

**Commits:** mensagens em português, explicando o *porquê* e não só o *o quê*.

## 8. Pendências e riscos

| Item | Tipo | Impacto | Próximo passo |
|---|---|---|---|
| Sem autenticação | Segurança | Médio | Portas já restritas a `127.0.0.1`, o que fecha o acesso pela rede. Uma chave de API no `/ingerir` seria o próximo passo; JWT completo é desproporcional hoje |
| Aprovação individual não reclassifica | Consistência | Baixo | Decisão tomada (18/08): não reclassificar, só avisar. `GET /publicacoes/aviso-reclassificacao` compara a aprovação mais recente com a última reclassificação geral e a aba Publicar mostra um aviso com botão "Reprocessar tudo agora" quando há aprovação mais nova. Ver seção 5 |
| `aprovada_por` nulo | Auditoria | Baixo hoje | Depende de haver usuários; importa quando houver mais de um revisor |
| Poucos parceiros com histórico próprio | Limitação temporária | Médio | Vale para os dois programas, mais agudo na Esfera (começou do zero em 17/08); a cascata por segmento cobre enquanto amadurece |
| Esfera sem pontuação-base nem datas de campanha | Limitação de fonte | Médio | A API da Esfera não expõe campo limpo pra isso (seção 5); mensagens da Esfera não trazem "🗓 Validade" nem "📉 fora da campanha" até a fonte mudar |
| Coletor depende do Mac ligado | Operacional | Baixo (19/08, reforçado 20/08) | Vale pros dois coletores, recalibração e backup; se o Mac não ligar no horário, o Painel de Saúde avisa no Telegram — FALHA na hora, ATRASADA em até 6h. Ainda existe uma falha de ponta cega: se o Mac nunca ligar, nenhum job roda e nenhuma checagem de "atrasado" dispara sozinha. **Achado novo em 20/08**: mesmo com o Mac "ligado" no sentido de não estar totalmente desligado, o Power Nap (DarkWake) não é acordar de verdade — corrigido com `pmset repeat wake` às 09:55, ver seção 5 |
| Sem criptografia no backup | Segurança | Baixo | Decisão deliberada (18/08): o banco não guarda credencial nem dado pessoal de terceiros. Revisitar se for pra servidor externo |
| Backup sem teste de restauração | Operacional | Resolvido (19/08) | Restaurado de verdade num banco isolado (`garimpo_restauracao_teste`, apagado depois) a partir do backup real de 19/08 11:22 — schema criou limpo, contagem de todas as tabelas idêntica à produção, um registro comparado campo a campo (inclusive UUID) bateu exato. Banco de produção nunca foi tocado |
| Rejeitadas com classificação velha | Consistência | Baixo | `reclassificar-todas` pula REJEITADAS por desenho |
| Canal PUBLICO sem ID | Configuração | Baixo | Só o AVANCADO existe; a fila ignora canais não configurados |
| Comparação entre programas (mesma marca, Livelo vs Esfera) | Produto | Baixo | Registrada como possibilidade (seção 2), não como tarefa — falta decidir critério de correspondência entre `Parceiro`s |
| Horário de atualização dos programas | Premissa | Baixo (resolvido por ora, 19/08) | `created_at` não serve pra isso (só marca quando nós coletamos). Teste empírico único (recoleta às 11:45 de 19/08, ~1h30 depois do agendado): 0 novidades nas duas fontes — evidência de que a janela atual não perde nada, mas é 1 dia só. Ver seção 5 |
| "Bankei" duplicado (Livelo) | Qualidade de dado | Resolvido (18/08) | Era dois `Parceiro` pro mesmo negócio — `codigo_externo` gravado como "ban" numa coleta e "BAN" noutra. Causa raiz corrigida (seção 5); os dois registros foram fundidos no banco (as 2 promoções passaram para o `Parceiro` com código "BAN", o duplicado e sua `Marca` órfã foram removidos) |
| seats.aero — API não disponível pro Brasil | Bloqueio externo, fechado (19/08) | Baixo | Resposta definitiva do suporte: não é elegibilidade pendente, é indisponibilidade geográfica — não reenviar o pedido. Se o Emissões avançar, único caminho agora é coletor próprio da Azul (só ela, Smiles e LATAM seguem bloqueadas). Ver seção 5 |
| LATAM Pass sem suporte em nenhuma ferramenta do mercado | Limitação externa | Baixo | Nem seats.aero nem AwardFares cobrem; rotina mensal automática (seção 5) avisa se isso mudar — não precisa checagem manual |

## 9. Próximas tarefas recomendadas

### Tarefa A — Acompanhar a validação da Esfera
O primeiro lote da Esfera já foi publicado (49 mensagens no total, Livelo +
Esfera, todas AVANCADO). Ainda não há retorno registrado de quem valida
especificamente sobre a Esfera, do jeito que houve pra Livelo — vale
perguntar, é o insumo que falta pra saber se a régua está calibrada pro
segundo programa.

### Tarefa B — Garimpo Emissões, com a Azul — EM ANDAMENTO (decisão tomada 19-20/08)
seats.aero respondeu **não** (API indisponível pro Brasil, 19/08) — mata o
cenário que cobria Smiles+Azul de uma vez. Smiles (Akamai) e LATAM (login)
seguem sem caminho. Decisão do usuário (20/08): seguir só com a Azul, é o
que tem em mãos.

**Arquitetura inicial criada (20/08), depois revisada por perna (21/08)** —
ver seção 5 pro detalhe técnico completo. Tabelas `rotas_emissao`
(catálogo curado) e `ofertas_emissao` (só a mais barata por
rota+data+classe, imutável, agora com `paradas`/`assentos_restantes` em
vez de `data_volta`/`voo_direto` — migration 0011, decisão do usuário
depois de um teste manual de ponta a ponta), sem motor nem classificação
automática, endpoints `POST /api/v1/emissoes/ofertas` e
`GET /api/v1/emissoes/rotas`. 108 testes de backend no total.

**`coletor-emissoes-azul/` construído (20-21/08), busca sempre só-ida
desde 21/08**: `urls.py` + `test_urls.py` (7 testes) montam a URL de busca
direta pros dois sistemas, sempre em modo só-ida — validadas contra URLs
reais capturadas ao vivo, não reconstruídas de memória. Achado no
processo: o site principal **não tem parâmetro de classe** na busca
(Economy e Business vêm juntas no mesmo resultado), diferente do
`azulpelomundo` (que tem `cabinCategory`).

**Parser do `azulpelomundo` pronto** (`parsing.py` + `test_parsing.py`, 6
testes): extrai o voo de ida mais barato do JSON real de
`GET /api/availability?tripType=ONE_WAY`, testado contra recortes fiéis de
respostas capturadas ao vivo. Numa busca só-ida `returnFlights` vem `null`
e `points.value` no nível do próprio voo já é o preço real — sem a
armadilha que existia na versão ida-e-volta (não usada mais), onde esse
mesmo campo era só o trecho de ida isolado. `connection` é o número de
conexões de verdade (confirmado com uma resposta real de duas pernas),
não um booleano — vira `paradas` sem conversão.

**Site principal, parsing DESTRAVADO (21/08), busca só-ida confirmada (21/08)**:
confirmados os dois canais reais que ele usa — REST
(`b2c-api.voeazul.com.br/tudoAzulReservationAvailability/.../v6/availability`)
e um canal `Listen` do Firestore
(`firestore.googleapis.com/.../Listen/channel?database=projects%2Fazul-storage-prd%2F...`)
— mas nenhum dos dois foi interceptável com as ferramentas de rede
disponíveis (toda busca faz reload completo da página, a chamada acontece
cedo demais no carregamento). Contornado do mesmo jeito que a Livelo: **lendo
o DOM já renderizado**, não a rede.

Cada `.flight-card` tem `data-test-id="fare-price fare-price-with-points"`
com o preço real (o `.initial` no mesmo card é o preço riscado antes do
desconto — os dois aparecem juntos, não confundir) e
`data-leg-remaining-seats` com assentos restantes — sinal de escassez que o
`azulpelomundo` não dá. O `id` do card, decodificado em base64 URL-safe,
ainda traz o itinerário completo (voos, aeroportos, horários); registrado
mas não usado no parser por ora. A URL só-ida larga os parâmetros
`c[1].*` por completo (confirmado numa busca real GIG→MCO); o card não
muda, só a página passa a ter uma seção em vez de duas. O número de
paradas mora no texto do card, em dois formatos reais confirmados: "1
conexão · Voo 4450" e "Voo 4043 Direto" (sem número na frente, confirmado
numa busca real VCP→CNF). `parsing_site_principal.py`, 9 testes contra
`outerHTML` real (com conexão, indisponível e direto). Ver README do
coletor pro detalhe completo.

**Catálogo de rotas populado (21/08)**: `rotas_emissao` tinha 107 linhas
carregadas via `scripts_backfill/seed_rotas_emissao.py`. A interpretação
direcional da matriz (seção 5 tinha só a lista de cidades, não o desenho
exato) foi confirmada com o usuário antes de gravar: os 5 aeroportos-base
(GIG, SDU, GRU, CGH, VCP) buscam **só na direção pra fora** pros destinos
de Nordeste/Sul/MG/internacional (95 rotas — 65 site principal + 30
azulpelomundo), e **nos dois sentidos** entre si mesmos (RJ↔SP, tráfego
real nas duas direções — 12 rotas, site principal). FLL e OPO ficaram de
fora por ora (mencionados mas não testados). Script idempotente, roda de
novo sem duplicar se o catálogo mudar.

**Orquestração Playwright escrita (21/08), mas ainda não validada rodando de
verdade**: `coletor_emissoes_azul.py`, escopo pequeno de propósito (decisão
do usuário, 21/08 — "a ideia é começar a ver algo funcionando", não as 107
rotas de uma vez): `--limite N` rotas por fonte (padrão 2), lidas do
catálogo real via `GET /api/v1/emissoes/rotas`; uma classe (Economy) e uma
data só por rota (amostragem de datas fica pra depois). Cada peça da
automação foi validada ao vivo, manualmente, antes de virar código: seleção
de origem/destino por autocomplete (site principal usa `role=option`,
texto começa com o código; azulpelomundo usa `role=link`, texto contém
"(CÓDIGO)"), seleção de data no site principal via atributo
`data-date="YYYY-MM-DD"` nos botões do calendário (achado 21/08 — mais
estável que navegar por classe CSS, que é hash de styled-components e
muda a cada build), captura da resposta de rede do azulpelomundo via
`page.expect_response`.

**Bloqueado por rate-limit no fim do dia (21/08)**: ao rodar o script de
verdade (não mais só manualmente), os dois sistemas recusaram a sessão —
site principal devolveu uma página própria "Ops! Só um momento,
identificamos um comportamento incomum vindo do seu IP" (bloqueio brando,
por IP) e o azulpelomundo devolveu "Access Denied" direto do Akamai
(bloqueio forte). Não é bug no script: é o teto de requisições por IP que
já estava registrado ("~10 buscas por sessão" no site principal), e só os
testes manuais de hoje (várias buscas em GIG-MCO, VCP-CNF, GRU-HND,
GRU-LIS, REC-CNF, REC-LHR pelo navegador do Claude Code, mais duas
tentativas do script) já passaram bastante disso, tudo no mesmo IP deste
Mac. Dois pontos ficam em aberto pra próxima sessão:
1. Quanto tempo o bloqueio dura — não testado ainda, precisa esperar e
   tentar de novo.
2. Se o **script Playwright puro** (fora do navegador do Claude Code)
   passa pela proteção quando não está sob rate-limit — cada peça da
   automação foi validada manualmente pelo navegador do Claude Code, mas
   a primeira vez que o script isolado rodou de verdade já foi sob cota
   estourada, então essa validação específica (fingerprint de um
   Playwright "cru", sem o navegador do Claude Code) ainda não aconteceu.

**Ainda faltando, nessa ordem**:
1. Rodar `coletor_emissoes_azul.py --limite 1` de novo depois de um tempo
   de espera, pra separar o que é rate-limit de hoje do que seria um
   problema de verdade no script.
2. Se passar: aumentar `--limite` aos poucos, depois pensar em amostragem
   de datas, Business, e robustez/agendamento — nessa ordem, não tudo de
   uma vez.
3. Decisões de produto que seguem em aberto: como exibir isso pro usuário
   sem nota automática, e o desenho de tela (não existe rota B, não faz
   sentido pensar nisso antes do coletor existir).

### Tarefa C — Histórico na tela — CONCLUÍDA (18/08)
As duas seções combinadas foram implementadas no card de "Ver detalhes",
carregadas sob demanda ao expandir (não no carregamento da lista): histórico
de reclassificações da nota (`GET /promocoes/{id}/classificacoes`) e ofertas
anteriores do mesmo parceiro (`GET /promocoes?parceiro_id=X`, limitado a 15
com resumo do resto). Nenhum endpoint novo, nenhuma migration.

### Tarefa D — Teste de API e banco — CONCLUÍDA (18/08)
`garimpo_test` + `pytest-asyncio` + `backend/tests/conftest.py`, com
isolamento por SAVEPOINT. 5 testes cobrindo os fluxos onde já apareceu bug
real: ingestão (parceiro novo + duplicata), aprovação em lote reclassificando
quem ficou fora do lote, fila de publicação com canal não configurado, e a
regressão do bug de regulamento da Esfera. Detalhe técnico preservado na
seção 5 (armadilha do event loop do pytest-asyncio).

### Tarefa E — Decidir o gancho de reclassificação na aprovação individual — CONCLUÍDA (18/08)
Decisão: avisar em vez de reclassificar. Ver seção 5 (`aprovacoes_apos_ultima_reclassificacao`)
e o aviso na aba Publicar.

### Tarefa F — Identidade visual das mensagens (ideia, não iniciada)
Levantada pelo usuário em 18/08, inspirada num card visual de alerta de
milhas de outro grupo (formato "ALERTA PPV": rótulo do programa isolado no
topo, depois trecho/condições em campos rotulados — o mesmo princípio de
"bate o olho, já identifica" que a mensagem em texto do Garimpo já segue).
Duas frentes distintas, não confundir:
- **Livelo/Esfera** (produto atual, Telegram): criar uma identidade visual
  para as mensagens já publicadas hoje em texto.
- **Emissões** (produto futuro, ainda não construído — Tarefa B): pensar o
  formato de mensagem já nascendo pro WhatsApp, possivelmente com cards
  visuais desde o início.

Ainda sem decisão de design nem de implementação. Recomendação registrada na
conversa: caso vire projeto, começar por uma versão em texto com a mesma
estrutura (rótulo, campos) antes de investir num gerador de imagem — o
card visual tem custo de produção real (template + render dinâmico) que o
texto não tem, e vale confirmar que o formato visual realmente compensa antes
de construir o gerador.

### Tarefa G — Aviso ativo do Painel de Saúde — CONCLUÍDA (19/08)
FALHA dispara Telegram na hora; ATRASADA é checado a cada 6h
(`scripts/verificar_saude.sh`). Testado de ponta a ponta com uma falha real,
confirmado recebido pelo usuário. Detalhe técnico e os dois bugs achados no
processo (PATH do backup, `pytest-asyncio` incompatível) na seção 5.

### Tarefa H — Testar uma restauração de verdade do backup — CONCLUÍDA (19/08)
Restaurado num banco isolado e descartado depois (`garimpo_restauracao_teste`),
a partir do backup real do dia. Schema limpo, contagem de tabelas idêntica à
produção, um registro batido campo a campo (inclusive UUID). Banco de
produção nunca foi tocado durante o teste.

### Tarefa I — Horário real de atualização da Livelo e da Esfera — RESOLVIDA POR ORA (19/08)
A ideia original (olhar `promocoes.created_at` acumulado) era um beco sem
saída: esse campo só marca quando *nós* coletamos, nunca quando a fonte
atualiza — os dados confirmaram que ele só reflete os próprios horários
agendados (09h-10h Livelo, 10h-12h Esfera), nada além disso.
`data_inicio`/`data_fim` também não servem: guardam só o dia, sem hora, por
decisão deliberada (seção 5).

Teste empírico no lugar: recoletei as duas às 11:45 do dia 19/08, ~1h30
depois do horário agendado — 0 novidades nas duas (Livelo: 0 criadas, 254
descartadas; Esfera: 0 criadas, 163 descartadas). Não prova qual é o
horário exato de publicação, mas é evidência real de que a régua atual não
estava perdendo atualização nenhuma nessa janela, num dia. Decisão do
usuário: fica assim por ora — a folga de 30h no Painel de Saúde já cobre
bastante margem de erro sobre o horário real; se quiser mais confiança,
repetir o mesmo teste em outro horário do dia (ex: fim de tarde) é o
próximo passo natural, não feito ainda.

### Tarefa J — Terceiro programa de fidelidade — DESCARTADA (20/08)
Vale expandir a coleta pra um terceiro "ganhe pontos" (não é o Emissões,
que é milhas aéreas) além de Livelo e Esfera? **Decisão do usuário: não,
ignorar essa frente.** Não retomar sem pedido explícito novo.

**Candidatos testados e descartados (19/08)**: o usuário sugeriu Shopping
Smiles e o equivalente da Azul. Os dois foram checados de verdade
(`shoppingsmiles.com.br`, `shopping.azulfidelidade.com.br`) e **não servem**
— são marketplaces de resgate por produto (troca milhas por um item
catalogado no próprio site, tipo "Shopping Azul Fidelidade" com "Queima de
Estoque Asics"), modelo bem diferente do Livelo/Esfera (ganhar pontos
comprando normalmente numa loja parceira). Não existe, em nenhum dos dois,
um diretório de centenas de parceiros por taxa de acúmulo — o mais perto
disso na Smiles é uma lista pequena (~4-5) de parceiros de serviço
(Uber, combustível, conta digital). Candidatos ainda não testados:
Dotz e Iupp (Itaú), sugeridos por mim, mais parecidos em estrutura mas sem
investigação técnica nenhuma ainda.

## 10. Roteiro da próxima sessão

1. Ler este arquivo por completo.
2. Conferir o estado real antes de agir: `git log --oneline`, `git status`,
   `docker compose ps`, contagem por status/programa em `promocoes`. **Os
   números da seção 3 são de 20/08 e envelhecem a cada coleta diária.**
3. Conferir o Painel de Saúde (aba Saúde do painel, ou `GET /api/v1/saude`)
   antes de mais nada — se algo ficou atrasado ou falhou desde 20/08 sem
   que o Telegram avisasse (Mac desligado o tempo todo, por exemplo), é o
   primeiro sinal a olhar.
4. Emissões (Tarefa B), primeira coisa a tentar: `coletor_emissoes_azul.py`
   já existe e roda com `--limite N` rotas por fonte (padrão 2), mas a
   primeira execução de verdade no fim de 21/08 tomou rate-limit dos dois
   sistemas (site principal e azulpelomundo) — provavelmente esgotado
   pelo volume de testes manuais do próprio dia, não um bug de código
   (seção 5 tem o detalhe completo e o HTML real do bloqueio). Rodar
   `./venv/bin/python3 coletor_emissoes_azul.py --limite 1` de novo é o
   primeiro passo: se passar, o próximo é aumentar `--limite` aos poucos;
   se continuar bloqueado, precisa investigar quanto tempo o rate-limit
   dura.
5. Conferir se as coletas automáticas (10:05 Livelo, 10:20 Esfera) rodaram e
   quantos registros cada uma criou. Esperado: poucos por dia (dedup por
   hash); uma centena de repente indicaria hash invalidado (seção 5).
6. Perguntar ao usuário a prioridade antes de escolher tarefa.
7. Não alterar arquivos sem aprovação explícita.

## 11. Leitura prioritária

1. Este arquivo.
2. `backend/application/ingestao_service.py` — dedup, identidade do parceiro,
   exceção à imutabilidade. É o coração das regras, vale pros dois programas.
3. `backend/application/condicoes.py` — como se decide "condicionada" e o
   alcance no marketplace.
4. `backend/application/motor/pilares.py`, `servico.py` e `historico.py` — os
   6 critérios e a cascata de comparação, que agora resolve categoria por
   parceiro (18/08), não por slug.
5. `backend/application/telegram/mensagens.py` — tópicos, truncamento do
   regulamento, por que "Escopo" não existe como campo.
6. `coletor-nativo/coletor_livelo_nativo.py` — ler os comentários do topo antes
   de mexer; explicam por que ele vive fora do Docker.
7. `coletor-esfera/esfera_api.py` — ler o cabeçalho antes de mexer; explica o
   que a Esfera não expõe e por quê.
8. `backend/static/admin/index.html` — painel.
9. `docs/GAR-1100/GAR-1100-Cap3-Modelo-PostgreSQL-Fisico-Rev2.md` — schema
   físico de referência.
10. `docs/GAR-1100/GAR-1100-Cap4-Dicionario-de-Dados-V1.md` — significado campo
    a campo. **Atenção:** os capítulos 3 e 4 descrevem o schema original e não
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
- *"Coletor da Esfera — programa cadastrado no banco, sem coletor"* — verdade
  até 17/08/2026. A Esfera tinha vantagem que ninguém havia checado: API
  pública sem anti-robô algum, mais simples de coletar que a própria Livelo.

## 13. Sessão de 09/09 — calibragem do motor e reinvestigação de Emissões

> Este handoff ficou sem atualização entre 21/08 e 09/09 — os números da
> seção 3 (dados no banco, 18/08) e da seção 9 (roteiro, 21/08) estão
> desatualizados e não foram reconferidos nesta sessão. Não reutilizar sem
> checar contra o banco real primeiro.

### Seis correções reais no Motor de Análise, todas verificadas contra dado real

Casos concretos levantados pelo usuário (Magalu, Camicado, Carrefour)
motivaram seis mudanças no motor, todas com teste automatizado e conferidas
via recalibração + consulta direta ao banco:

1. **`segmento_varejo` amacia a penalidade de `marketplace_status=PARCIAL`**
   (`motor/pilares.py::pilar_amplitude`) — para um parceiro de varejo com
   catálogo próprio amplo, não valer no marketplace não reduz o alcance na
   prática. Só vale para PARCIAL; PROIBIDO continua penalidade cheia
   independente do segmento. `servico.py::_parceiro_e_varejo` resolve o
   segmento por `ParceiroCategoria` (curadoria por vínculo, mesma fonte da
   cascata de histórico) com fallback pra `Parceiro.categoria_id`.
2. **Penalidade de condição escala pelo tamanho do degrau** — antes a queda de
   nota era fixa independente de o piso condicionado ser próximo ou muito
   abaixo do valor anunciado; agora escala com `queda_relativa` (piso vs.
   anunciado).
3. **Amplitude não duplica penalidade quando marketplace já explica o "até"**
   — quando `marketplace_status` já é a razão do degrau condicionado (o "até"
   é justamente "vale menos fora do parceiro direto"), a mesma restrição não
   pode penalizar duas vezes.
4. **Histórico por família exige coerência, não só quantidade**
   (`motor/historico.py`) — `MINIMO_PARA_USAR_FAMILIA=2` sozinho não bastava:
   duas campanhas muito díspares (ex: 3 pontos e 40 pontos) não formam
   histórico coerente. Novo gate: `_coeficiente_variacao(valores) <=
   CV_MAXIMO_PARA_USAR_FAMILIA` (0.5, desvio padrão / média) — acima disso a
   cascata cai pro segmento, mesmo com amostra suficiente.
5. **`valor_comparavel(promocao)` como fonte única do "valor real pra
   comparação"** (`motor/percentil.py`, nova função) — caso real: Carrefour
   anunciou "7 pontos" (20/08) mas só valia na marca própria, 1 ponto no
   resto. Um 5 pontos incondicional perdia sem razão pra esse "7" que nunca
   foi o valor real da maioria das compras. Aplicado em `pilar_historico_com_base`,
   `pilar_atratividade`, `pilar_exclusividade`, na cascata de histórico
   (família/segmento/mercado) e no `_mercado()` do orquestrador — sempre que
   uma oferta condicionada entra numa base de comparação ou é ela mesma
   posicionada, usa o piso (`valor_condicionado_piso`), não o número anunciado.
6. **Bug de data no `montar_fila`** (`application/publicacao_service.py`) —
   achado do usuário (Carrefour, campanha de um dia só, aprovada e some da
   fila na própria meia-noite do dia em que ainda valia). `data_fim` guarda
   meia-noite do início do último dia válido, não o fim dele; filtro mudou de
   `data_fim >= agora` para `data_fim + timedelta(days=1) > agora`.

Migration 0012 + `scripts_backfill/backfill_0012.py` recalculam
`valor_condicionado_piso` para as condicionadas já existentes (backfill
precisou de `from domain import governanca  # noqa: F401` pra resolver a FK
de `promocoes.aprovada_por`, senão o `db.commit()` falhava com
`NoReferencedTableError`). Confirmado por consulta direta: `reclassificar_todas`
cobre PENDENTE **e** APROVADA, então as aprovações pendentes no dia já
refletem todas as correções acima. Suíte de backend em 140 testes passando
ao fim da sessão.

### Garimpo Emissões: retomada com Claude in Chrome — Smiles funciona manualmente, automação ainda não

Objetivo do usuário: reavaliar Smiles, LATAM e os dois sistemas da Azul
(site principal e `azulpelomundo`) agora que o Chrome com a extensão Claude
está instalado — sem nunca inserir login/senha em nome dele (login manual
fica sempre com o usuário; combinado explicitamente pro caso da Smiles e
adiado pro da LATAM).

**LATAM**: confirma o que já estava registrado na seção 5 — busca com
milhas exige login antes de qualquer resultado. Não foi contornado; o
usuário planeja testar pessoalmente, logando manualmente, em sessão futura.

**Smiles — achado novo, contradiz parcialmente o handoff anterior**: a
seção 5 registrava Smiles como "fechada, sem caminho técnico conhecido"
(Akamai bloqueia até em navegador real e visível). O teste de hoje
**qualifica** essa afirmação: o usuário conseguiu acessar e buscar voos
manualmente pelo Chrome real dele (GIG→MCO e GIG→REC, preços reais
carregados), mas a primeira busca de uma sessão trava num spinner
("Aguarde enquanto buscamos os melhores voos...") que só se resolve com
refresh manual da página — às vezes uma vez, às vezes nem precisa,
aparentemente dependendo de quanto histórico/uso aquele perfil de navegador
já acumulou.

Reproduzido de forma controlada: um script Playwright novo (perfil sem
histórico nenhum) reproduziu o mesmo spinner e travou; `page.reload()`
automatizado **não** resolveu no mesmo teste, ao contrário do refresh manual
do usuário. Hipótese em teste agora (não confirmada): o que destrava não é
"a mesma sessão", é reputação/histórico acumulado do perfil de navegador —
cookies, uso real, tempo de existência. Ação em andamento: criado um perfil
Chrome real dedicado e persistente (`launch_persistent_context` com
`channel="chrome"`, diretório
`coletor-emissoes-azul/perfil-smiles-dedicado/`, **não** o perfil pessoal do
usuário), que ele está usando manualmente nos próximos dias pra "amadurecer"
antes de testar o coletor automatizado nele. Ainda sem resultado — a
primeira tentativa, feita minutos depois de criado, travou igual (esperado,
perfil zerado).

Ferramentas empíricas descobertas nesse teste manual (não commitadas, só em
script de rascunho), úteis se a automação avançar: origem via
`get_by_placeholder('Origem')` (não `get_by_text`, é input); destino via
`#inp_flightDestination_1` (placeholder ambíguo colide com campo de hotéis);
banner de cookies precisa ser aceito duas vezes (reaparece depois da seleção
de destino); seleção de dia do calendário precisa filtrar por posição
(`bounding_box`) porque o mesmo texto do dia também bate num slider-dot não
relacionado do carrossel.

**Azul (os dois sistemas)**: `--limite 1` do `coletor_emissoes_azul.py`
rodado de verdade hoje, nas duas fontes — os dois deram timeout de 30s
esperando o formulário aparecer. Confirmado via navegador que não é bug de
seletor: o site principal devolve a página de rate-limit própria ("Ops! Só
um momento... IP: 189.29.149.17") e o `azulpelomundo` devolve "Access
Denied" do Akamai puro. **O bloqueio de 21/08 persiste até hoje** — mais de
duas semanas depois, não é questão de horas, é bloqueio de vários dias no
mínimo. Duração exata e critério de liberação seguem desconhecidos.

**Achado sobre o próprio Claude in Chrome**: a ferramenta tem bloqueio
próprio, a nível de tool, para navegar a `smiles.com.br` e `voeazul.com.br`
("Navigation to this domain is not allowed") — diferente do caso da LATAM,
que só pede permissão. Reproduzido em abas novas e grupos de abas novos, não
é artefato de sessão velha. Não impediu a investigação (o usuário navegou
manualmente e compartilhou screenshots/diagnóstico de rede), mas significa
que esse tool não serve para automatizar Smiles/Azul mesmo que o bloqueio de
IP se resolva — só serve para o usuário mesmo dirigir e a IA observar.

### Pendências abertas desta sessão

- Decidir se/quando testar a Azul de novo (esperar mais / trocar de rede /
  pausar essa frente) — não decidido.
- Deixar o perfil Chrome dedicado da Smiles amadurecer com uso real antes de
  testar o coletor automatizado nele.
- LATAM: usuário ainda vai testar pessoalmente com login manual — não feito.
- Reconferir os números da seção 3 (estão de 18/08) e o roteiro da seção 9
  (de 21/08) contra o banco real — não feito nesta sessão, o foco foi
  calibragem + Emissões, não uma auditoria de números.
- Nada da investigação de Emissões de hoje foi commitada — só existe neste
  handoff e em scripts de rascunho fora do controle de versão.
