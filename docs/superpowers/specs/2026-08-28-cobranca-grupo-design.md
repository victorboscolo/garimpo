# Cobrança do grupo — desenho técnico

> Spec de um subsistema novo: controle de acesso ao(s) grupo(s) do Telegram
> vinculado a pagamento via Hotmart. Não existe fluxo equivalente hoje no
> código — `infrastructure/telegram/cliente.py` só publica mensagem
> (`sendMessage`) em canal, nenhuma linha mexe em quem é membro de nada.

## 1. Contexto e motivação

O Garimpo hoje distribui alertas de promoção só de graça, em canais do
Telegram (`AVANCADO` e `PUBLICO`, ver `application/publicacao_service.py`),
sem nenhum controle de quem tem acesso a quê além do limiar de qualidade da
oferta. A ideia é monetizar isso, com variações de conteúdo/acesso por
nível — o ponto de partida da conversa foram quatro ideias (Grupo Gratuito,
Grupo Gratuito temporário atrelado a venda de consultoria, Grupo Pago
Básico, Grupo Pago Avançado), mas o número exato e o que diferencia cada
nível **não estão fechados** (ver seção 9). Esta spec cobre o **mecanismo**
de amarrar pagamento a acesso no Telegram — não depende de saber quantos
níveis existirão pra funcionar.

Um eixo de diferenciação de conteúdo já foi discutido e vale registrar
aqui como motivação, mesmo não fazendo parte do mecanismo desta spec: o
grupo gratuito teria um **teto diário configurável** de ofertas
Excelente/Excepcional (proposta: 2/dia), com aviso de que existem mais; o
grupo pago veria o tratamento completo, sem teto. Isso é extensão de
`deve_publicar`/`publicacao_service.py` (quantidade, não só qualidade
mínima) — mudança pequena, mas separada do que está desenhado abaixo, e
não detalhada a esse nível de profundidade nesta spec.

## 2. Decisão de abordagem: construir em casa

Três caminhos considerados: (A) tudo próprio — webhook, chamadas ao Bot API
do Telegram, tabela de membership, job de expiração; (B) ferramenta pronta
de mercado que já faz a ponte Hotmart↔Telegram; (C) híbrido, ferramenta
pronta só pra parte de pagamento↔acesso, backend próprio só pra decidir
conteúdo por canal.

**Decisão: (A).** Determinante: **sem caixa para qualquer investimento**
agora — isso tira B/C da mesa, já que a parte que teria custo é
especificamente a mensalidade da ferramenta terceira (o Hotmart e o Bot
API do Telegram são gratuitos de usar em qualquer um dos três caminhos).
Consistente com o padrão do resto do projeto (coletor próprio da Azul em
vez de agregador pago, motor próprio em vez de SaaS de score): as partes
"chatas" de A (chargeback, borda de reembolso parcial) serão descobertas
na prática, não vêm testadas por terceiro — trade-off aceito.

## 3. Princípio de desenho: flexível para um futuro Portal

Discussão paralela: pode existir no futuro um "Portal" com vários módulos
pagos (Alertas do Garimpo sendo um deles, um módulo de planejamento
financeiro sendo outro, ainda ideia da esposa do usuário, não iniciado).
Decisão do usuário (28/08): seguir com o Telegram agora, mas desenhar de
forma que a cobrança possa migrar pra um módulo do Portal depois **sem
reescrever o núcleo**.

Isso se traduz em separar **entitlement** (quem tem direito a quê — não
muda com o canal) de **enforcement** (como isso é aplicado de fato — hoje
é só Telegram):

- **`Assinatura`** — comprador (por e-mail, o que o Hotmart dá e o que uma
  conta de portal também usaria) + produto/módulo + status + data de
  expiração. Agnóstico de canal. O webhook do Hotmart e o job de
  expiração mexem só aqui.
- **`AcessoTelegram`** — liga uma `Assinatura` a um `telegram_user_id` e a
  um grupo/canal específico. É a peça de aplicação — só ela sabe que o
  mecanismo de hoje é Telegram.

Se um dia a cobrança virar (também, ou em vez de) portal, o que muda é só
isso: aparece um `AcessoPortal` ao lado (ou no lugar) de `AcessoTelegram`.
`Assinatura` — o núcleo de "quem pagou o quê até quando" — não muda uma
linha.

## 4. Arquitetura geral

Quatro peças novas, seguindo padrões que já existem no backend:

1. **Endpoint de webhook** (`POST /api/v1/assinaturas/webhook-hotmart`) —
   recebe o evento do Hotmart, decide o que fazer.
2. **Cliente Telegram estendido** — `infrastructure/telegram/cliente.py`
   ganha `criar_link_convite` (`createChatInviteLink`, `member_limit=1`),
   `banir_membro`/`desbanir_membro` (`banChatMember`/`unbanChatMember`),
   ao lado do `enviar` que já existe.
3. **Modelos novos** (`domain/assinaturas.py`) — `Assinatura` e
   `AcessoTelegram`, seção 3.
4. **Job diário de reconciliação** — não é só expiração por data; varre
   toda `Assinatura` que devia estar banida (expirada OU cancelada) e
   ainda não tem o `AcessoTelegram` correspondente banido. Reaproveita o
   padrão `launchd` que já toca backup e recalibração (`scripts/`, não
   `scripts_backfill/` — é tarefa recorrente, não um backfill de uma vez).

**Infraestrutura nova necessária — exposição pública**: o backend hoje só
escuta em `127.0.0.1`, de propósito (proteção atual contra não ter
autenticação, ver HANDOFF seção 8). O Hotmart precisa alcançar um endereço
público pra entregar o webhook. Solução proposta: **Cloudflare Tunnel**
(plano gratuito real, não trial) expondo só a rota
`/api/v1/assinaturas/webhook-hotmart` num endereço HTTPS público, sem abrir
porta no roteador nem expor o resto do backend. O endpoint valida o Hottok
(token que o Hotmart envia) antes de processar qualquer coisa — um POST sem
Hottok válido é recusado, não processado.

Mapeamento produto-Hotmart → grupo-Telegram: um dict em código, mesmo
padrão do `VARIAVEL_DE_CANAL` que já existe em `cliente.py` — não a
hierarquia de `configuracoes` do motor (feita pra pesos/faixas que mudam
com frequência; aqui são poucos grupos, cadastro raro).

## 5. Fluxo, do início ao fim

1. Cliente compra no Hotmart → Hotmart chama o webhook (via túnel).
2. Endpoint valida o Hottok, identifica produto e comprador (e-mail),
   grava/atualiza `Assinatura` (status ATIVA) — upsert idempotente pela
   `transaction_id` do Hotmart (Hotmart reenvia em retry; nunca duplica).
3. Service chama `criar_link_convite` no grupo mapeado pro produto
   (`member_limit=1`) e devolve o link — entregue pelo Hotmart na página
   de obrigado/e-mail (o link "junto ao produto").
4. Comprador clica, entra no grupo. O Telegram, por padrão, exige que a
   pessoa **aceite** ser adicionada — não dá pra forçar entrada silenciosa
   (nem um bot consegue adicionar proativamente, limitação do próprio
   Telegram). Um caminho manual/exceção existe em paralelo: o usuário
   (dono) adiciona alguém direto pela própria conta, sem checar Hotmart —
   caso raro, tratado à mão, não faz parte do fluxo automático.
5. O backend descobre a entrada via **polling periódico** do Bot API
   (`getUpdates`, `chat_member`) — seção 6, não em tempo real.
6. Reembolso/cancelamento → novo webhook do Hotmart → `Assinatura` vira
   CANCELADA → service tenta banir na hora; se não tiver
   `AcessoTelegram` ainda (pessoa não entrou, ou polling não capturou),
   fica pendente pro job de reconciliação (seção 4/7).
7. Job diário → varre `Assinatura`s expiradas por data OU canceladas sem
   ban efetivo → `banir_membro` + `desbanir_membro` (a sequência banir-e-
   desbanir remove agora e permite reentrada numa compra futura, em vez de
   banir permanentemente).

## 6. Descoberta de entrada no grupo: polling, não webhook do Telegram

Duas formas de saber que alguém entrou (Telegram só oferece essas duas,
pra qualquer atualização — `chat_member` ou `chat_join_request`):

- **Webhook do Telegram** (`setWebhook`) — tempo real, mas precisa de
  HTTPS público (reaproveitaria o túnel do Hotmart), e soma uma segunda
  rota exposta pra proteger.
- **Polling** (`getUpdates`) — o backend pergunta periodicamente, sem
  exposição nenhuma (mesmo princípio de qualquer chamada de saída que os
  coletores já fazem). Não precisa de long-polling com processo vivo:
  short-poll (`timeout=0`) rodando a cada poucos minutos via `launchd`.

**Decisão: polling.** O projeto inteiro até hoje é feito de scripts
periódicos, não processos vivos — não existe daemon 24h em lugar nenhum do
Garimpo — e evita abrir uma segunda rota pública só pra essa finalidade.
Custo aceito: um atraso de alguns minutos entre a entrada real e o
registro do `AcessoTelegram`, sem problema porque nada crítico depende
desse instante (a pessoa já está dentro; só estamos documentando pra
quando precisar remover depois). Precisa persistir o cursor (`offset` do
Telegram) entre execuções, pra não reprocessar nem perder atualização.

## 7. Tratamento de erro

O job de reconciliação (seção 4) é a rede de segurança de quase tudo que
pode falhar no meio do caminho — mesmo espírito de "estado é derivado, não
guardado" que já existe em `montar_fila` (fila de publicação):

- **Hottok inválido** → 401, não processa, só loga.
- **Produto do Hotmart não mapeado pra nenhum grupo** → loga e ignora, não
  inventa grupo (mesmo princípio do `RotaEmissao` rejeitando rota fora do
  catálogo).
- **Hotmart reenvia o mesmo evento** → upsert idempotente por
  `transaction_id`, nunca duplica `Assinatura`.
- **`criar_link_convite` falha** (Telegram fora do ar, bot perdeu
  permissão) → cliente pagou e ficou sem link — grave o bastante pra
  avisar ativamente (canal ALERTA, igual o Painel de Saúde já faz), não só
  logar.
- **Ban falha, ou reembolso chega sem `telegram_user_id` capturado ainda**
  → cai no job de reconciliação diário, que não filtra só por data de
  expiração, filtra por "devia estar banido e não está".

## 8. Teste

Mesma disciplina do coletor de Emissões — nada de formato de API
inventado:

- **Lógica pura**: validação de Hottok, resolução produto→grupo,
  idempotência do upsert, "quem deve ser removido hoje" (a query de
  reconciliação). Testável sem rede, sem banco.
- **Integração** (banco de teste, padrão `test_integracao_*.py`): POST do
  webhook cria/atualiza `Assinatura` certo; reenvio não duplica.
- **Chamadas reais ao Bot API** (`createChatInviteLink`, `banChatMember`,
  `getUpdates`): antes de escrever qualquer parsing ou chamada real, capturar
  a resposta de verdade primeiro (mesmo processo usado pro site principal
  da Azul) — não assumir formato de memória da documentação do Telegram.

## 9. Decisões de produto ainda em aberto (fora do mecanismo)

Estas não bloqueiam a implementação do mecanismo acima, mas precisam ser
resolvidas antes de configurar produtos/grupos de verdade:

- **Número e nome dos níveis**: as quatro ideias originais (Gratuito,
  Gratuito temporário/consultoria, Pago Básico, Pago Avançado) não estão
  fechadas — o usuário foi explícito: "esse modelo de negócio ainda não
  está muito claro na minha cabeça". O mecanismo é parametrizado por
  produto→grupo justamente pra não depender dessa resposta agora.
- **Diferenciação de conteúdo por nível** (o teto de ofertas do grupo
  gratuito, seção 1) — decisão tomada em conversa, não implementada nem
  desenhada a nível de componente nesta spec.
- **Migração de audiência existente**: não é um problema — confirmado
  (28/08) que tudo que roda hoje no canal AVANCADO é manual, sem
  automação a desligar.
- **Relação com o Portal futuro** (seção 3): esta spec cobre só o
  Telegram; quando/se o Portal existir, é uma spec própria, que reaproveita
  `Assinatura` sem alterá-la.
