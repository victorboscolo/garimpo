# Handoff para Claude Code

> Revisado em 18/08/2026, ao fim de uma sessão de dois dias. Os números aqui
> foram conferidos contra o banco na escrita, não reconstruídos de memória. A
> seção 12 lista as afirmações de handoffs anteriores que se provaram falsas —
> vale ler antes de confiar em qualquer documento mais antigo.

## 1. Resumo executivo

O **Garimpo Promoções** coleta, normaliza e analisa ofertas de pontuação de
programas de fidelidade (**Livelo e Esfera**, desde 17/08/2026), calcula uma
nota e categoria de atratividade por um motor de regras determinístico (não é
LLM) e expõe tudo para revisão humana antes de qualquer divulgação. Existe um
segundo produto planejado, **Garimpo Emissões** (passagens aéreas via milhas),
**investigado nesta sessão mas ainda fora do escopo de implementação** — seção
5 tem o mapa completo do que é viável e o que não é.

**Estágio atual**: MVP funcional de ponta a ponta rodando localmente no Mac do
usuário, dois programas de fidelidade coletando em paralelo, automaticamente,
sem intervenção diária. Motor calibrado com dados reais, banco, API e painel
de revisão estão implementados e em uso. 50 commits, 97 testes automatizados
(backend, 84 de lógica pura + 12 de integração API/banco + 1 smoke test de
migration) + 43 coletor Livelo (41 + 2 do fix de caixa do `codigo_externo`) +
9 coletor Esfera. Backup diário rodando de verdade pela primeira vez, e um
Painel de Saúde mostra se cada job (coleta, recalibração, backup) está em dia.

**O que mudou na sessão de 17–18/08**, em dez frentes:

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
| Painel de Saúde | IMPLEMENTADO | tabela `execucoes` + `GET /api/v1/saude`; coletor Livelo, coletor Esfera, recalibração e backup registram o próprio resultado ao terminar (sucesso/falha, contadores, erro); situação OK/FALHA/ATRASADA/NUNCA_RODOU por job |
| Backup | IMPLEMENTADO (18/08) | diário via launchd (10:40), Postgres → Google Drive (camada de HD externo é opcional, só grava se já estiver montado); retenção de 30 backups na nuvem; sem criptografia (decisão, ver seção 5) |
| Testes automatizados | PARCIAL | 97 backend (84 de lógica pura + 12 de integração API/banco + 1 smoke test de `alembic upgrade head`) + 43 coletor Livelo + 9 coletor Esfera. Cobre os fluxos onde já apareceu bug real; não é cobertura exaustiva |
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
de elegibilidade enviado ao suporte deles em 18/08, resposta pendente.

**Achado de segurança/legal, não só técnico**: a Air Canada processa o
Seats.aero alegando que scraping automatizado de disponibilidade de prêmio é
fraude computacional (linguagem de CFAA); o Seats.aero se defende como
concorrência legítima. É litígio real e em andamento — motivo a mais pra não
construir scraping próprio de Smiles/LATAM como se fosse trivial, mesmo
quando tecnicamente possível.

**Monitoramento automático criado**: rotina mensal (`trig_01VNZZmfuWBgzaA6QcRU3BB7`,
todo dia 1º) verifica se seats.aero ou AwardFares passaram a suportar LATAM
Pass; só notifica se algo mudar.

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
scripts/           # recalibrar.sh, backup.sh (Postgres -> Google Drive) + plists do launchd
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
| Coletor depende do Mac ligado | Operacional | Médio | Vale pros dois coletores, recalibração e backup; se o Mac não ligar no horário, a aba Saúde do painel mostra ATRASADA depois de ~30h (semanal + folga pra recalibração), mas ainda depende de alguém abrir o painel — nenhum alerta ativo (push/Telegram) existe ainda |
| Sem criptografia no backup | Segurança | Baixo | Decisão deliberada (18/08): o banco não guarda credencial nem dado pessoal de terceiros. Revisitar se for pra servidor externo |
| Backup sem teste de restauração | Operacional | Médio | O backup roda e o dump é válido (testado com `gunzip -t`), mas nunca foi restaurado de fato num banco vazio — a prova real de um backup é conseguir restaurá-lo |
| Rejeitadas com classificação velha | Consistência | Baixo | `reclassificar-todas` pula REJEITADAS por desenho |
| Canal PUBLICO sem ID | Configuração | Baixo | Só o AVANCADO existe; a fila ignora canais não configurados |
| Comparação entre programas (mesma marca, Livelo vs Esfera) | Produto | Baixo | Registrada como possibilidade (seção 2), não como tarefa — falta decidir critério de correspondência entre `Parceiro`s |
| Horário de atualização dos programas | Premissa | Baixo | Observar empiricamente, pros dois |
| "Bankei" duplicado (Livelo) | Qualidade de dado | Resolvido (18/08) | Era dois `Parceiro` pro mesmo negócio — `codigo_externo` gravado como "ban" numa coleta e "BAN" noutra. Causa raiz corrigida (seção 5); os dois registros foram fundidos no banco (as 2 promoções passaram para o `Parceiro` com código "BAN", o duplicado e sua `Marca` órfã foram removidos) |
| seats.aero — elegibilidade de API pendente | Bloqueio externo | Médio | Pedido enviado em 18/08 (conta Pro já existe, mas API não é automática); cobriria Smiles + Azul de uma vez se aprovado. Ver seção 5 |
| LATAM Pass sem suporte em nenhuma ferramenta do mercado | Limitação externa | Baixo | Nem seats.aero nem AwardFares cobrem; rotina mensal automática (seção 5) avisa se isso mudar — não precisa checagem manual |

## 9. Próximas tarefas recomendadas

### Tarefa A — Acompanhar a validação da Esfera
O primeiro lote da Esfera já foi publicado (49 mensagens no total, Livelo +
Esfera, todas AVANCADO). Ainda não há retorno registrado de quem valida
especificamente sobre a Esfera, do jeito que houve pra Livelo — vale
perguntar, é o insumo que falta pra saber se a régua está calibrada pro
segundo programa.

### Tarefa B — Retomar Garimpo Emissões quando o seats.aero responder
Investigação completa na seção 5. Se a API for aprovada: cobre Smiles e Azul
de uma vez, elimina a complexidade de sessão que a Azul exige sozinha —
tratar como caminho principal, guardando o que foi aprendido sobre a Azul
como plano B. Se não for aprovada, ou demorar: a Azul sozinha já tem
arquitetura mapeada (aquecer sessão, lotes de ~8 buscas, reaquecer) pra
começar um coletor próprio. Duas decisões de produto ainda em aberto antes de
qualquer código: como guardar histórico de preço ao longo do tempo (pra
sinal de "queda de preço") e como exibir isso pro usuário sem nota
automática (seção 5).

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

## 10. Roteiro da próxima sessão

1. Ler este arquivo por completo.
2. Conferir o estado real antes de agir: `git log --oneline`, `git status`,
   `docker compose ps`, contagem por status/programa em `promocoes`. **Os
   números da seção 3 são de 18/08 e envelhecem a cada coleta diária.**
3. Checar se o seats.aero respondeu o pedido de elegibilidade de API (seção
   5) — muda o próximo passo de Emissões inteiro.
4. Conferir se as coletas automáticas (10:05 Livelo, 10:20 Esfera) rodaram e
   quantos registros cada uma criou. Esperado: poucos por dia (dedup por
   hash); uma centena de repente indicaria hash invalidado (seção 5).
5. Perguntar ao usuário a prioridade antes de escolher tarefa.
6. Não alterar arquivos sem aprovação explícita.

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
