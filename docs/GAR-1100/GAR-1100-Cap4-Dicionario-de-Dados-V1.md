# GAR-1100 — Capítulo 4
# DICIONÁRIO DE DADOS — GARIMPO PROMOÇÕES (MVP)
**Versão:** 1.0
**Status:** Em construção
**Pré-requisito:** GAR-1100 Cap. 3 (Rev. 2) — Modelo PostgreSQL Físico

Este capítulo detalha campo a campo as três tabelas mais sensíveis do schema: `promocoes` (a entidade central), `classificacoes` (saída do motor) e `configuracoes` (parâmetros calibráveis). As demais tabelas (`marcas`, `parceiros`, `categorias`, `usuarios` etc.) têm campos autoexplicativos e não são detalhadas aqui.

Legenda de **Origem**: `COLETOR` (robô de coleta) · `IA` (motor/extração automática) · `ADMIN` (preenchido/editado por humano no painel) · `SISTEMA` (gerado automaticamente pelo backend).

---

## Tabela `promocoes`

| Campo | Tipo | Obrigatório | Origem | Regra / Validação |
|---|---|---|---|---|
| `id` | UUID | Sim | SISTEMA | Gerado no insert. Nunca exposto ao usuário final. |
| `codigo` | BIGSERIAL | Sim | SISTEMA | Sequencial, uso administrativo/depuração. |
| `codigo_amigavel` | VARCHAR(50) | Sim | SISTEMA | Formato `{PROGRAMA}-{PARCEIRO}-{AAAAMMDD}-{SEQ}`, ex.: `LIV-MAG-20260714-001`. Gerado no momento da primeira coleta. |
| `programa_id` | UUID (FK) | Sim | COLETOR | Deve existir em `programas` e estar `ativo = TRUE`. |
| `parceiro_id` | UUID (FK) | Sim | COLETOR / IA | Resolvido via `parceiro_aliases` quando o nome coletado não bate exatamente com `parceiros.nome`. Se não houver match, cai em fila de revisão manual (não cria parceiro novo automaticamente). |
| `titulo` | VARCHAR(300) | Sim | COLETOR | Texto bruto coletado, sem processamento. |
| `descricao` | TEXT | Não | COLETOR | Texto complementar da página de origem, se existir. |
| `url_origem` | TEXT | Sim | COLETOR | Link oficial — é a fonte da verdade em caso de dúvida. |
| `regulamento_texto` | TEXT | Não | COLETOR | Texto completo capturado no momento da coleta (preservação de evidência mesmo que a página mude depois). |
| `regulamento_resumo` | TEXT | Não | IA | Gerado a partir de `regulamento_texto`. Sempre deve ser possível voltar ao texto completo — nunca substitui `regulamento_texto`. |
| `data_inicio` | TIMESTAMPTZ | Não | COLETOR | Nulo quando a promoção não informa data de início explícita. |
| `data_fim` | TIMESTAMPTZ | Não | COLETOR | Idem para data de término. |
| `pontuacao` | NUMERIC(10,2) | Sim | COLETOR | Valor numérico da oferta (ex.: pontos por real). |
| `unidade_pontuacao` | VARCHAR(50) | Sim | COLETOR | Ex.: `"pontos_por_real"`, `"percentual_bonus"`. Necessário para o motor comparar corretamente ofertas de formatos diferentes. |
| `requer_clube` | BOOLEAN | Sim | COLETOR/IA | Default `FALSE`. |
| `qual_clube` | VARCHAR(100) | Não | COLETOR/IA | Preenchido apenas se `requer_clube = TRUE`. |
| `requer_cupom` | BOOLEAN | Sim | COLETOR/IA | Default `FALSE`. |
| `cupom` | VARCHAR(100) | Não | COLETOR/IA | Preenchido apenas se `requer_cupom = TRUE`. |
| `marketplace_status` | VARCHAR(20) | Não | IA | Enum: `PERMITIDO` \| `PROIBIDO` \| `PARCIAL`. Nulo quando não aplicável ao parceiro. |
| `abrangencia` | TEXT | Não | IA | Descrição textual do alcance no catálogo (ex.: "todo o catálogo", "apenas linha eletrônicos"). Alimenta o pilar **Amplitude** do motor. |
| `restricoes` | TEXT | Não | IA | Condições adicionais não cobertas pelos campos estruturados acima. |
| `disponibilidade` | VARCHAR(20) | Sim | IA | Enum: `PUBLICA` \| `RESTRITA` \| `PERSONALIZADA`. Default `PUBLICA`. Determina a mensagem de acesso mostrada antes da análise. |
| `status` | VARCHAR(20) | Sim | SISTEMA/ADMIN | Enum: `RASCUNHO` → `PENDENTE` → (`APROVADA` \| `REJEITADA`) → `PUBLICADA` → `ARQUIVADA`. Transições controladas pela aplicação, nunca por update livre. |
| `motivo_rejeicao` | TEXT | Não | ADMIN | Obrigatório preencher quando `status = REJEITADA` (validação de aplicação, não de banco). Alimenta o feedback estruturado do motor. |
| `parametros_utilizados` | JSONB | Sim (após classificação) | SISTEMA | Snapshot dos pesos/faixas vigentes em `configuracoes` no momento da análise — garante que reprocessamentos futuros sejam auditáveis e comparáveis. |
| `origem` | VARCHAR(50) | Sim | SISTEMA | Enum: `MANUAL` \| `COLETOR` \| `IMPORTACAO`. |
| `origem_detalhe` | VARCHAR(100) | Não | SISTEMA | Ex.: `COLETOR_LIVELO`, `COLETOR_ESFERA`, `OPERADOR`. Usado para diagnosticar falhas por fonte. |
| `hash_promocao` | VARCHAR(128) | Sim | SISTEMA | Hash calculado sobre os campos relevantes (parceiro+programa+pontuação+datas+condições) para detectar duplicidade/mudança real — é o que decide se uma nova coleta gera novo registro. |
| `criada_por` | UUID (FK) | Não | SISTEMA | Nulo quando `origem = COLETOR`; preenchido quando `origem = MANUAL`. |
| `aprovada_por` | UUID (FK) | Não | ADMIN | Preenchido no momento da aprovação/rejeição. |
| `aprovada_em` | TIMESTAMPTZ | Não | SISTEMA | Timestamp da decisão do admin. |
| `created_at` | TIMESTAMPTZ | Sim | SISTEMA | Default `now()`. |

**Regra de imutabilidade:** nenhum campo de `promocoes` é editável após a criação, com uma única exceção operacional: `status`, `motivo_rejeicao`, `aprovada_por`, `aprovada_em` (o ciclo de vida de validação). Qualquer mudança de conteúdo real (pontuação, datas, condições) gera um **novo registro**, nunca um update dos campos de conteúdo.

---

## Tabela `classificacoes`

| Campo | Tipo | Obrigatório | Origem | Regra / Validação |
|---|---|---|---|---|
| `id` | UUID | Sim | SISTEMA | — |
| `codigo` | BIGSERIAL | Sim | SISTEMA | — |
| `entidade_tipo` | VARCHAR(20) | Sim | SISTEMA | `PROMOCAO` no MVP; `EMISSAO` reservado para o futuro. |
| `entidade_id` | UUID | Sim | SISTEMA | Deve existir na tabela correspondente ao `entidade_tipo` — validado em código (RN-013), não por FK nativa. |
| `versao_motor` | VARCHAR(50) | Sim | SISTEMA | Ex.: `"v1.0"`. Necessário para comparar resultados entre versões do motor. |
| `nota` | NUMERIC(5,2) | Sim | IA | Resultado da média ponderada dos 6 pilares. Faixa 0–100. |
| `categoria` | VARCHAR(50) | Sim | IA | Derivada de `nota` via `configuracoes.faixas_classificacao` — nunca hardcoded no código. |
| `criterios_avaliados` | JSONB | Sim | IA | `{historico, amplitude, facilidade, exclusividade, atratividade, confiabilidade_dados}` — cada um 0–100. Uso interno (auditoria/calibração), não exibido ao usuário comum. |
| `confianca_historica` | VARCHAR(20) | Sim | IA | Enum: `ALTA` \| `MEDIA` \| `BAIXA`. Calculada pelo modelo de fallback (ver RN-009 no Cap. 3), independente de `confiabilidade_dados`. |
| `confiabilidade_dados` | NUMERIC(5,2) | Sim | IA | 0–100. Mede completude/clareza dos dados desta promoção específica para a extração da IA — é o pilar "Confiabilidade" do motor, e é conceitualmente diferente de `confianca_historica`. |
| `justificativa` | TEXT | Sim | IA | Texto simplificado, gerado pela camada de Interpretação (pode cruzar critérios narrativamente, mesmo que a nota seja calculada por critérios independentes). É o que o usuário comum recebe junto da categoria. |
| `ativa` | BOOLEAN | Sim | SISTEMA | Apenas uma `TRUE` por `(entidade_tipo, entidade_id)`. Nova classificação desativa a anterior. |
| `processada_em` | TIMESTAMPTZ | Sim | SISTEMA | Quando o motor rodou — pode ser diferente de `created_at` em reprocessamentos em lote. |
| `created_at` | TIMESTAMPTZ | Sim | SISTEMA | — |

---

## Tabela `configuracoes`

| Campo | Tipo | Obrigatório | Origem | Regra / Validação |
|---|---|---|---|---|
| `id` | UUID | Sim | SISTEMA | — |
| `chave` | VARCHAR(200) | Sim | ADMIN | Nome do parâmetro. Ver lista de chaves conhecidas abaixo. |
| `dominio_id` | UUID (FK, nullable) | Não | ADMIN | `NULL` = aplica-se a todos os domínios (nível GLOBAL). |
| `programa_id` | UUID (FK, nullable) | Não | ADMIN | `NULL` = aplica-se a todo o domínio. Se preenchido, `dominio_id` deve ser consistente com o domínio desse programa (validação de aplicação). |
| `parceiro_id` | UUID (FK, nullable) | Não | ADMIN | `NULL` = aplica-se a todo o programa. Nível mais específico da hierarquia. |
| `valor` | JSONB | Sim | ADMIN | Estrutura livre, validada por chave (ver abaixo). |
| `descricao` | TEXT | Não | ADMIN | Explicação legível do parâmetro, para quem for calibrar depois. |
| `updated_at` | TIMESTAMPTZ | Sim | SISTEMA | Atualizado a cada edição — permite auditar quando um parâmetro mudou. |

**Chaves conhecidas na V1** (todas calibráveis sem alteração de código):

| Chave | Formato esperado de `valor` | Nível típico |
|---|---|---|
| `pesos_motor_v1` | `{historico, atratividade, amplitude, facilidade, exclusividade, confiabilidade_dados}` (somam 100) | GLOBAL, com override possível por PROGRAMA |
| `faixas_classificacao` | `{excepcional:{min,max}, excelente:{...}, boa:{...}, comum:{...}, pouco_atrativa:{...}}` | GLOBAL |
| `historico_suficiente` | `{min_campanhas, janela_dias}` | GLOBAL |
| `peso_temporal` | `{recente_meses, recente_peso, medio_meses, medio_peso, antigo_peso}` | GLOBAL |

---

## Observação para migrations

Os campos `JSONB` (`criterios_avaliados`, `parametros_utilizados`, `valor` em `configuracoes`) não têm schema validation no nível do banco — a validação de formato deve ser feita na camada de aplicação (Pydantic no FastAPI) antes do insert. Isso é intencional (mantém o banco flexível para o motor evoluir), mas significa que a API é a única linha de defesa contra dados malformados nesses campos — vale a pena tratar isso com atenção especial nos testes.

---

## Próximo capítulo sugerido

GAR-1100 Capítulo 5 — Estratégia de Migrations e Seed Inicial (ordem de criação das tabelas, dados iniciais de `dominios`, `perfis`, `categorias` base, e primeira versão de `configuracoes` com os valores desta auditoria).
