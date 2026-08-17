# Handoff para Claude Code

> Revisado em 17/08/2026, ao fim da sessão que trouxe o segundo programa
> (Esfera) ao ar. Os números aqui foram conferidos contra o banco na escrita,
> não reconstruídos de memória. A seção 12 lista as afirmações de handoffs
> anteriores que se provaram falsas — vale ler antes de confiar em qualquer
> documento mais antigo.

## 1. Resumo executivo

O **Garimpo Promoções** coleta, normaliza e analisa ofertas de pontuação de
programas de fidelidade (**Livelo e Esfera**, desde 17/08/2026), calcula uma
nota e categoria de atratividade por um motor de regras determinístico (não é
LLM) e expõe tudo para revisão humana antes de qualquer divulgação. Existe um
segundo produto planejado, **Garimpo Emissões** (passagens aéreas via milhas),
fora do escopo atual, mas cuja arquitetura já foi antecipada nas tabelas
polimórficas (`classificacoes`, `arquivos` e `publicacoes` usam `entidade_tipo`
+ `entidade_id` sem FK nativa, para servirem aos dois domínios).

**Estágio atual**: MVP funcional de ponta a ponta rodando localmente no Mac do
usuário, agora com dois programas de fidelidade coletando em paralelo. Coleta
real diária de ambos, motor calibrado com dados reais, banco, API e painel de
revisão estão implementados e em uso. O repositório tem controle de versão (36
commits — **mais o trabalho desta sessão, ainda não commitado**: veja
`git status`) e 122 testes automatizados.

**O que mudou na sessão de 17/08**, em três frentes:

- **Esfera no ar**: segundo programa de fidelidade, coletado por uma API
  pública que a própria Esfera expõe sem proteção alguma — nem cookie, nem
  anti-robô, nem sessão. Ao contrário da Livelo, o coletor é Python simples
  (`httpx`, sem Playwright). 168 parceiros coletados, classificados e já
  aprovados pelo usuário; nenhum publicado ainda, o que é esperado (seção 5).
- **Mensagens reorganizadas**: o nome do programa agora aparece (essencial com
  dois programas no mesmo canal), os fatos viraram tópicos rotulados
  (Pontuação, Validade, Cupom), e o regulamento — que na Esfera chega a 10x
  maior que na Livelo — é truncado por tamanho quando passa de 500 caracteres,
  sempre com o link completo logo abaixo.
- **Fila de publicação**: ganhou descarte explícito (paralelo a
  aprovar/rejeitar) e reprocessamento automático das classificações ao fim da
  aprovação em lote, para a fila nunca publicar nota desatualizada.

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
| Controle de versão | IMPLEMENTADO | 36 commits; trabalho desta sessão ainda não commitado (`git status`); `.gitignore` cobre `.env`, `venv/`, logs, `.pytest_cache` |
| Modelo de dados | IMPLEMENTADO | 18 tabelas, migrations 0001–0007 aplicadas |
| Motor de Análise V1 | IMPLEMENTADO | 6 pilares; comparativos por percentil, escopados por programa; base em cascata (família → segmento → mercado) |
| Coletor Livelo nativo (macOS) | IMPLEMENTADO | lê o JSON estruturado da listagem; parsing de texto como fallback; 41 testes |
| Coletor Livelo em Docker | ABANDONADO | bloqueado por anti-robô (HTTP 403); não usar |
| Coletor Esfera | IMPLEMENTADO | `coletor-esfera/`; API pública sem anti-robô nenhum, Python simples (`httpx`); 9 testes |
| Agendamento (`launchd`) | IMPLEMENTADO | Livelo 10:05, Esfera 10:20, recalibração semanal seg. 11h; só roda com o Mac ligado |
| API (FastAPI) | IMPLEMENTADO | listagem ordenada, aprovação/rejeição individual e em lote, ingestão, reclassificação |
| Painel admin | IMPLEMENTADO | triagem por nota, ações em lote, critérios do motor, regulamento e selos; fila de publicação com descarte |
| Testes automatizados | PARCIAL | 72 backend + 41 coletor Livelo + 9 coletor Esfera, todos de lógica pura; nada de API/banco |
| Publicação (Telegram) | IMPLEMENTADO | fila com curadoria, prévia, envio em lote, descarte, diagnóstico e aviso de divergência; mensagem por tópicos, com nome do programa |
| Autenticação | PENDENTE | ver seção 8 |

**Dados no banco (17/08/2026):**

| | |
|---|---|
| Promoções | 537 — 533 aprovadas (365 Livelo + 168 Esfera), 4 rejeitadas, 0 pendentes |
| Parceiros | 423 (255 Livelo + 168 Esfera — mesma marca em programas diferentes ainda vira `Parceiro` separado, seção 2) |
| Categorias de origem / vínculos | 65 / 669, em 2 programas |
| Publicadas no Telegram | 40, todas AVANCADO. **Nenhuma da Esfera ainda** — esperado, ver seção 5 |

**Distribuição das notas (Esfera, recém-aprovada):** Pouco atrativa 58, Comum
58, Boa 47, Excelente 4, Excepcional 1 — já diferenciando, não mais achatada em
50/65 como no primeiro dia (seção 5).

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
  migrations/      # Alembic (0001–0007)
  scripts_backfill/# backfills pontuais, com dry-run
  static/admin/    # painel
  tests/           # 72 testes de lógica pura
coletor-nativo/    # coletor Livelo, roda fora do Docker (bloqueio anti-robô), venv próprio
  coletor_livelo_nativo.py # orquestra a coleta; fallback de texto
  parceiros_json.py        # lê o JSON estruturado da página (caminho principal)
  test_coletor_livelo.py + test_parceiros_json.py   # 41 testes
coletor-esfera/    # coletor Esfera, roda fora do Docker só por padrão operacional, venv próprio
  coletor_esfera.py # orquestra a coleta e envia pra API
  esfera_api.py      # busca e mapeia os campos da API pública da Esfera
  test_esfera_api.py # 9 testes
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
cd coletor-esfera && ./venv/bin/python3 -m pytest test_esfera_api.py -q
open http://localhost:8000/admin/                       # painel
cd coletor-nativo && ./venv/bin/python3 coletor_livelo_nativo.py   # coleta manual Livelo
cd coletor-esfera && ./venv/bin/python3 coletor_esfera.py          # coleta manual Esfera
launchctl start com.garimpo.coletor-livelo               # força a coleta Livelo
launchctl start com.garimpo.coletor-esfera               # força a coleta Esfera
./scripts/recalibrar.sh                                  # reprocessa tudo agora
```

**Testes:** a suíte cobre **lógica pura** — parsing dos dois coletores, faixas
do motor, hash de dedup, regras de condição, montagem de mensagem. Não há
teste de API nem de banco; isso exigiria pytest-asyncio e um banco de teste, e
nunca foi montado. O painel é validado manualmente no navegador.

**Atenção:** o `pytest` está no `requirements.txt`, mas se a imagem estiver
defasada ele some do container. `docker compose build backend` resolve.

**Commits:** mensagens em português, explicando o *porquê* e não só o *o quê*.

## 8. Pendências e riscos

| Item | Tipo | Impacto | Próximo passo |
|---|---|---|---|
| Sem autenticação | Segurança | Médio | Portas já restritas a `127.0.0.1`, o que fecha o acesso pela rede. Uma chave de API no `/ingerir` seria o próximo passo; JWT completo é desproporcional hoje |
| Aprovação individual não reclassifica | Consistência | Médio | Só `aprovar-lote` chama `reclassificar_todas`; aprovar uma por uma deixa a fila com nota potencialmente desatualizada até a próxima recalibração ou lote. Decisão em aberto, perguntada ao usuário e ainda sem resposta: reclassificar a cada aprovação individual (mais correto, mais lento) ou só avisar na aba Publicar quando houver aprovação mais recente que a última classificação |
| `aprovada_por` nulo | Auditoria | Baixo hoje | Depende de haver usuários; importa quando houver mais de um revisor |
| Poucos parceiros com histórico próprio | Limitação temporária | Médio | Vale para os dois programas, mais agudo na Esfera (começou do zero em 17/08); a cascata por segmento cobre enquanto amadurece |
| Agrupamento canônico vazio | Curadoria | Baixo | `categorias_origem.categoria_id` nulo nos 65 slugs (2 programas); preencher reduz os agrupadores sem recoletar |
| Esfera sem pontuação-base nem datas de campanha | Limitação de fonte | Médio | A API da Esfera não expõe campo limpo pra isso (seção 5); mensagens da Esfera não trazem "🗓 Validade" nem "📉 fora da campanha" até a fonte mudar |
| Coletor depende do Mac ligado | Operacional | Médio | Vale pros dois coletores agora, não só a Livelo; coleta diária pode falhar em silêncio, não há monitoramento |
| Sem teste de API/banco | Qualidade | Médio | Vários bugs de sessões anteriores (MissingGreenlet, MultipleResultsFound, fuso na validade, canal não configurado bloqueando o lote) só apareceram em execução real |
| Rejeitadas com classificação velha | Consistência | Baixo | `reclassificar-todas` pula REJEITADAS por desenho |
| Canal PUBLICO sem ID | Configuração | Baixo | Só o AVANCADO existe; a fila ignora canais não configurados |
| Comparação entre programas (mesma marca, Livelo vs Esfera) | Produto | Baixo | Registrada como possibilidade (seção 2), não como tarefa — falta decidir critério de correspondência entre `Parceiro`s |
| Horário de atualização dos programas | Premissa | Baixo | Observar empiricamente, pros dois |

## 9. Próximas tarefas recomendadas

### Tarefa A — Acompanhar a validação da Esfera
168 parceiros da Esfera foram coletados, classificados e aprovados nesta
sessão, mas **nada foi publicado ainda** — decisão deliberada do usuário
("coletar e classificar, não publicar ainda"). Publicar o primeiro lote e
recolher o retorno de quem valida é o próximo passo natural, no ritmo que o
usuário decidir.

### Tarefa B — Histórico na tela (desenho aprovado, não implementado)
Duas seções novas dentro do "Ver detalhes" que já existe, carregadas **sob
demanda** ao expandir o card, para não voltar a fazer centenas de requisições no
carregamento:
- **Histórico da nota desta promoção** — como a avaliação evoluiu. Endpoint
  `GET /promocoes/{id}/classificacoes` já existe.
- **Histórico de ofertas deste parceiro** — como a oferta mudou ao longo dos
  dias. `GET /promocoes?parceiro_id=X` já existe.

Não precisa de endpoint novo nem migration — é trabalho só de tela.

### Tarefa C — Teste de API e banco
Várias falhas caras de sessões anteriores passaram por toda a suíte de lógica
pura e só apareceram rodando o sistema de verdade. Montar pytest-asyncio com
banco de teste fecharia essa lacuna.

### Tarefa D — Decidir o gancho de reclassificação na aprovação individual
Ver a pendência na seção 8. Pergunta feita ao usuário, sem resposta ainda —
não escolher um caminho sem essa confirmação.

## 10. Roteiro da próxima sessão

1. Ler este arquivo por completo.
2. Conferir o estado real antes de agir: `git log --oneline`, `git status`
   (**há trabalho desta sessão ainda não commitado**), `docker compose ps`,
   contagem por status/programa em `promocoes`. **Os números da seção 3 são de
   17/08 e envelhecem a cada coleta diária.**
3. Conferir se as coletas automáticas (10:05 Livelo, 10:20 Esfera) rodaram e
   quantos registros cada uma criou. Esperado: poucos por dia (dedup por
   hash); uma centena de repente indicaria hash invalidado (seção 5).
4. Perguntar ao usuário a prioridade antes de escolher tarefa.
5. Não alterar arquivos sem aprovação explícita.

## 11. Leitura prioritária

1. Este arquivo.
2. `backend/application/ingestao_service.py` — dedup, identidade do parceiro,
   exceção à imutabilidade. É o coração das regras, vale pros dois programas.
3. `backend/application/condicoes.py` — como se decide "condicionada" e o
   alcance no marketplace.
4. `backend/application/motor/pilares.py` e `servico.py` — os 6 critérios.
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
