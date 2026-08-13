# GAR-1100 — Capítulo 3 (Revisão 2)
# MODELO POSTGRESQL FÍSICO — GARIMPO PROMOÇÕES (MVP)
**Versão:** 2.0
**Status:** Em construção (revisão pós Auditoria Final do Motor de Análise V1)
**Base:** Revisão 1 (documento original), corrigida para refletir as decisões consolidadas nesta auditoria.

---

## O que mudou da Revisão 1 para a Revisão 2

| # | Mudança | Motivo |
|---|---|---|
| 1 | Nova tabela `dominios` | Domínio = Garimpo Promoções vs Garimpo Emissões — nível que faltava na hierarquia de parâmetros |
| 2 | `programas.dominio_id` adicionado | Todo programa pertence a um domínio |
| 3 | `configuracoes` ganhou `dominio_id`, `programa_id`, `parceiro_id` (nullable) | Sem isso a hierarquia GLOBAL→DOMÍNIO→PROGRAMA→PARCEIRO não podia ser representada |
| 4 | `configuracoes.valor` virou JSONB (era TEXT) | Pesos e faixas de classificação são estruturas, não apenas valores simples |
| 5 | Nova tabela `categorias` (com `categoria_pai_id` autorreferente) | Cadastro independente e editável de categorias/subcategorias, decidido mas nunca modelado |
| 6 | `parceiros.categoria_id` adicionado | Associa cada parceiro a uma categoria |
| 7 | `promocoes` ganhou 12 campos novos | Disponibilidade, regulamento completo, validação/rejeição, código amigável (ver seção da tabela) |
| 8 | `classificacoes.confianca` virou dois campos | `confianca_historica` (fallback estatístico) e `confiabilidade_dados` (pilar do motor) são conceitos diferentes |
| 9 | `classificacoes` ganhou `criterios_avaliados` JSONB | Subnotas internas dos 6 pilares, para auditoria/calibração |
| 10 | `publicacoes.tipo` passa a aceitar `PUBLICO` e `AVANCADO` | Reflete os dois canais de Telegram decididos nesta sessão |
| 11 | `classificacoes`, `arquivos` e `publicacoes` trocam `promocao_id` por `entidade_tipo` + `entidade_id` | Prepara o motor, os arquivos e a distribuição para servirem também ao futuro Garimpo Emissões, sem redesenho de schema quando esse domínio for implementado |

---

## PRINCÍPIOS GERAIS (mantidos da Revisão 1)

- **PG-001** — Todas as tabelas usam `id UUID` como chave primária técnica.
- **PG-002** — Entidades operacionais possuem `codigo BIGSERIAL` para uso administrativo.
- **PG-003** — Todas as tabelas possuem `created_at` / `updated_at`.
- **PG-004** — Datas em `TIMESTAMP WITH TIME ZONE`.
- **PG-005** — Sem soft delete no MVP; registros históricos são preservados (uso de `ativo BOOLEAN` para desativação lógica).

---

## TABELA `dominios` *(nova)*

Representa os dois produtos do Garimpo.

```sql
CREATE TABLE dominios (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo      BIGSERIAL UNIQUE,
  nome        VARCHAR(50) NOT NULL,      -- 'PROMOCOES' | 'EMISSOES'
  ativo       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Registros iniciais: `PROMOCOES` (ativo), `EMISSOES` (inativo até entrar em escopo).

---

## TABELA `marcas`

```sql
CREATE TABLE marcas (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo      BIGSERIAL UNIQUE,
  nome        VARCHAR(200) NOT NULL,
  ativo       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_marcas_nome ON marcas (nome);
```

---

## TABELA `categorias` *(nova)*

Cadastro editável de categorias e subcategorias (ex.: Moda → Calçados).

```sql
CREATE TABLE categorias (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo            BIGSERIAL UNIQUE,
  nome              VARCHAR(150) NOT NULL,
  categoria_pai_id  UUID NULL REFERENCES categorias(id),  -- NULL = categoria raiz
  ativo             BOOLEAN NOT NULL DEFAULT TRUE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_categorias_pai ON categorias (categoria_pai_id);
```

---

## TABELA `parceiros`

```sql
CREATE TABLE parceiros (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo            BIGSERIAL UNIQUE,
  marca_id          UUID NOT NULL REFERENCES marcas(id),
  categoria_id      UUID NULL REFERENCES categorias(id),   -- NOVO
  nome              VARCHAR(200) NOT NULL,
  nome_normalizado  VARCHAR(200) NOT NULL,
  ativo             BOOLEAN NOT NULL DEFAULT TRUE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_parceiros_marca ON parceiros (marca_id);
CREATE INDEX idx_parceiros_categoria ON parceiros (categoria_id);
```

Relacionamento: 1 Marca → N Parceiros. A "família histórica" de uma promoção é dada, sem tabela própria, pela combinação `(parceiro_id, programa_id)` — decisão aprovada nesta auditoria (automática, sem intervenção manual).

---

## TABELA `parceiro_aliases`

```sql
CREATE TABLE parceiro_aliases (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  parceiro_id  UUID NOT NULL REFERENCES parceiros(id),
  alias        VARCHAR(200) NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_parceiro_aliases_parceiro ON parceiro_aliases (parceiro_id);
```

---

## TABELA `programas`

```sql
CREATE TABLE programas (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo      BIGSERIAL UNIQUE,
  dominio_id  UUID NOT NULL REFERENCES dominios(id),   -- NOVO
  nome        VARCHAR(150) NOT NULL,                    -- Livelo, Esfera, Smiles...
  ativo       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_programas_dominio ON programas (dominio_id);
```

---

## TABELA `promocoes`

Entidade principal. **Imutável** (RN-001) — mudanças geram nova "fotografia"/registro, nunca update do histórico.

```sql
CREATE TABLE promocoes (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo                 BIGSERIAL UNIQUE,
  codigo_amigavel        VARCHAR(50) UNIQUE,              -- NOVO, ex: LIV-MAG-20260714-001
  programa_id            UUID NOT NULL REFERENCES programas(id),
  parceiro_id            UUID NOT NULL REFERENCES parceiros(id),
  titulo                 VARCHAR(300) NOT NULL,
  descricao              TEXT,
  url_origem             TEXT,
  regulamento_texto      TEXT,                            -- NOVO — texto completo capturado
  regulamento_resumo     TEXT,                             -- NOVO — resumo gerado por IA
  data_inicio            TIMESTAMPTZ,
  data_fim               TIMESTAMPTZ,
  pontuacao              NUMERIC(10,2) NOT NULL,
  unidade_pontuacao      VARCHAR(50),
  requer_clube           BOOLEAN NOT NULL DEFAULT FALSE,
  qual_clube             VARCHAR(100),
  requer_cupom           BOOLEAN NOT NULL DEFAULT FALSE,
  cupom                  VARCHAR(100),
  marketplace_status     VARCHAR(20),                      -- NOVO: PERMITIDO | PROIBIDO | PARCIAL
  abrangencia            TEXT,                             -- NOVO: descrição do alcance no catálogo
  restricoes             TEXT,                             -- NOVO
  disponibilidade        VARCHAR(20) NOT NULL DEFAULT 'PUBLICA', -- NOVO: PUBLICA | RESTRITA | PERSONALIZADA
  status                 VARCHAR(20) NOT NULL DEFAULT 'PENDENTE', -- RASCUNHO|PENDENTE|APROVADA|REJEITADA|PUBLICADA|ARQUIVADA
  motivo_rejeicao        TEXT,                             -- NOVO
  parametros_utilizados  JSONB,                            -- NOVO — snapshot dos parâmetros vigentes na análise
  origem                 VARCHAR(50),                      -- NOVO — ex: 'COLETOR_LIVELO'
  origem_detalhe         TEXT,                             -- NOVO
  hash_promocao          VARCHAR(128),                     -- NOVO — detecção de duplicidade
  criada_por             UUID REFERENCES usuarios(id),
  aprovada_por           UUID REFERENCES usuarios(id),     -- NOVO
  aprovada_em            TIMESTAMPTZ,                       -- NOVO
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_promocoes_programa ON promocoes (programa_id);
CREATE INDEX idx_promocoes_parceiro ON promocoes (parceiro_id);
CREATE INDEX idx_promocoes_status ON promocoes (status);
CREATE INDEX idx_promocoes_datas ON promocoes (data_inicio, data_fim);
CREATE INDEX idx_promocoes_hash ON promocoes (hash_promocao);
```

Status possíveis: `RASCUNHO`, `PENDENTE`, `APROVADA`, `REJEITADA`, `PUBLICADA`, `ARQUIVADA`.
Regra de armazenamento: se uma nova coleta encontrar a mesma campanha sem alteração, **não cria novo registro** — só gera nova fotografia quando houver mudança real.

---

## TABELA `categorias_promocao` *(nova, N:N)*

Uma promoção pode abranger mais de uma categoria de produto.

```sql
CREATE TABLE categorias_promocao (
  promocao_id   UUID NOT NULL REFERENCES promocoes(id),
  categoria_id  UUID NOT NULL REFERENCES categorias(id),
  PRIMARY KEY (promocao_id, categoria_id)
);
```

---

## TABELA `arquivos`

```sql
CREATE TABLE arquivos (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entidade_tipo   VARCHAR(20) NOT NULL,   -- NOVO (era promocao_id): 'PROMOCAO' | 'EMISSAO'
  entidade_id     UUID NOT NULL,          -- NOVO: id da promoção ou, futuramente, da emissão
  tipo            VARCHAR(50) NOT NULL,   -- PDF | REGULAMENTO | ANEXO
  arquivo_url     TEXT NOT NULL,
  hash_arquivo    VARCHAR(128),
  texto_extraido  TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_arquivos_entidade ON arquivos (entidade_tipo, entidade_id);
```

Arquivos **não** ficam dentro do PostgreSQL — a tabela só referencia a localização. Sem FK nativa (Postgres não valida FK polimórfica); a integridade é garantida na camada de aplicação — ver RN-012.

---

## TABELA `classificacoes`

Uma promoção pode ter várias classificações ao longo do tempo (uma por versão do motor).

```sql
CREATE TABLE classificacoes (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo                 BIGSERIAL UNIQUE,
  entidade_tipo          VARCHAR(20) NOT NULL,         -- NOVO (era promocao_id): 'PROMOCAO' | 'EMISSAO'
  entidade_id            UUID NOT NULL,                 -- NOVO
  versao_motor           VARCHAR(50) NOT NULL,
  nota                   NUMERIC(5,2) NOT NULL,
  categoria              VARCHAR(50) NOT NULL,        -- EXCEPCIONAL|EXCELENTE|BOA|COMUM|POUCO_ATRATIVA
  criterios_avaliados    JSONB NOT NULL,               -- NOVO: {historico, amplitude, facilidade, exclusividade, atratividade, confiabilidade_dados}
  confianca_historica    VARCHAR(20) NOT NULL,         -- NOVO (renomeado): ALTA|MEDIA|BAIXA — vem do fallback
  confiabilidade_dados   NUMERIC(5,2) NOT NULL,        -- NOVO (renomeado): 0-100, pilar do motor
  justificativa          TEXT NOT NULL,
  ativa                  BOOLEAN NOT NULL DEFAULT TRUE,
  processada_em          TIMESTAMPTZ NOT NULL,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_classificacoes_entidade ON classificacoes (entidade_tipo, entidade_id);
CREATE INDEX idx_classificacoes_ativa ON classificacoes (ativa);
CREATE INDEX idx_classificacoes_nota ON classificacoes (nota);
```

Regra: apenas uma classificação `ativa = TRUE` por entidade (promoção ou, futuramente, emissão). O motor de 6 pilares, os pesos e as faixas de `configuracoes` já são domínio-agnósticos — poderá ser reaproveitado por Emissões com pesos próprios, calibrados via `configuracoes.dominio_id`.

---

## TABELA `publicacoes`

```sql
CREATE TABLE publicacoes (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entidade_tipo  VARCHAR(20) NOT NULL,    -- NOVO (era promocao_id): 'PROMOCAO' | 'EMISSAO'
  entidade_id    UUID NOT NULL,           -- NOVO
  canal          VARCHAR(50) NOT NULL DEFAULT 'TELEGRAM',
  tipo           VARCHAR(20) NOT NULL,   -- ADMIN | PUBLICO | AVANCADO  (AVANCADO é novo)
  status         VARCHAR(20) NOT NULL DEFAULT 'PENDENTE', -- PENDENTE|ENVIADO|FALHA
  erro_resumido  TEXT,
  data_envio     TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_publicacoes_entidade ON publicacoes (entidade_tipo, entidade_id);
CREATE INDEX idx_publicacoes_status ON publicacoes (status);
CREATE INDEX idx_publicacoes_data_envio ON publicacoes (data_envio);
```

`tipo = PUBLICO` publica a versão simplificada (categoria + resumo) no canal público; `tipo = AVANCADO` publica nota + critérios no canal restrito.

---

## TABELA `usuarios`

```sql
CREATE TABLE usuarios (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo      BIGSERIAL UNIQUE,
  nome        VARCHAR(200) NOT NULL,
  email       VARCHAR(200) UNIQUE NOT NULL,
  senha_hash  TEXT NOT NULL,
  ativo       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## TABELA `perfis`

```sql
CREATE TABLE perfis (
  id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome  VARCHAR(100) NOT NULL   -- ADMIN | OPERADOR
);
```

## TABELA `usuario_perfis`

```sql
CREATE TABLE usuario_perfis (
  usuario_id  UUID NOT NULL REFERENCES usuarios(id),
  perfil_id   UUID NOT NULL REFERENCES perfis(id),
  PRIMARY KEY (usuario_id, perfil_id)
);
```

---

## TABELA `configuracoes` *(revisada)*

Parâmetros calibráveis, agora com suporte real à hierarquia GLOBAL → DOMÍNIO → PROGRAMA → PARCEIRO.

```sql
CREATE TABLE configuracoes (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chave        VARCHAR(200) NOT NULL,     -- ex: 'peso_historico', 'faixas_classificacao'
  dominio_id   UUID NULL REFERENCES dominios(id),    -- NOVO
  programa_id  UUID NULL REFERENCES programas(id),   -- NOVO
  parceiro_id  UUID NULL REFERENCES parceiros(id),   -- NOVO
  valor        JSONB NOT NULL,             -- ALTERADO de TEXT para JSONB
  descricao    TEXT,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- garante no máximo um registro por combinação chave+escopo
  UNIQUE (chave, dominio_id, programa_id, parceiro_id)
);
CREATE INDEX idx_configuracoes_chave ON configuracoes (chave);
```

**Regra de resolução (valor mais específico vence):**
`PARCEIRO` (se existir) → senão `PROGRAMA` → senão `DOMÍNIO` → senão `GLOBAL` (todas as colunas de escopo NULL).

Exemplos de registros:

```json
// GLOBAL
{ "chave": "faixas_classificacao", "dominio_id": null, "programa_id": null, "parceiro_id": null,
  "valor": {"excepcional":{"min":90,"max":100},"excelente":{"min":75,"max":89},
            "boa":{"min":55,"max":74},"comum":{"min":35,"max":54},"pouco_atrativa":{"min":0,"max":34}} }

// GLOBAL — pesos do motor
{ "chave": "pesos_motor_v1", "valor":
  {"historico":25,"atratividade":25,"amplitude":20,"facilidade":10,"exclusividade":10,"confiabilidade_dados":10} }

// GLOBAL — limiar de histórico suficiente
{ "chave": "historico_suficiente", "valor":
  {"min_campanhas":3,"janela_dias":365} }
```

---

## TABELA `auditoria`

```sql
CREATE TABLE auditoria (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id        UUID REFERENCES usuarios(id),
  entidade          VARCHAR(100) NOT NULL,
  entidade_id       UUID NOT NULL,
  acao              VARCHAR(100) NOT NULL,
  dados_anteriores  JSONB,
  dados_novos       JSONB,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_auditoria_entidade ON auditoria (entidade, entidade_id);
```

---

## REGRAS DE NEGÓCIO CONSOLIDADAS

| Código | Regra |
|---|---|
| RN-001 | Promoções são imutáveis; mudança real gera novo registro, não update. |
| RN-002 | Classificações são versionadas (uma por `versao_motor`); apenas uma `ativa` por promoção. |
| RN-003 | Arquivos ficam fora do PostgreSQL; a tabela só referencia a localização. |
| RN-004 | Parceiros pertencem a uma marca (obrigatório) e a uma categoria (opcional). |
| RN-005 | Toda publicação gera registro operacional em `publicacoes`. |
| RN-006 | Toda alteração relevante gera registro em `auditoria`. |
| RN-007 | Programas são cadastráveis via painel administrativo. |
| RN-008 *(novo)* | Família histórica = `(parceiro_id, programa_id)`, sempre automática, sem tabela própria. |
| RN-009 *(novo)* | Histórico é "suficiente" quando há no mínimo N campanhas dentro da janela configurada (parâmetro `historico_suficiente`, default 3 campanhas / 365 dias); abaixo disso, o motor usa o fallback em cascata: específico → parceiro → mercado competitivo → dados da promoção atual. |
| RN-010 *(novo)* | 100% das promoções passam por revisão humana antes da publicação; a saída dessa regra será baseada em confiabilidade observada do motor, não em volume — sem prazo definido. |
| RN-011 *(novo)* | Configuração resolvida sempre pelo escopo mais específico disponível: PARCEIRO → PROGRAMA → DOMÍNIO → GLOBAL. |
| RN-012 *(novo)* | `classificacoes`, `arquivos` e `publicacoes` referenciam sua entidade via `entidade_tipo` + `entidade_id` (não FK nativa), para servirem tanto a `promocoes` quanto à futura tabela principal de Emissões sem alteração de schema. |
| RN-013 *(novo)* | Como `entidade_id` não tem FK nativa do Postgres, a camada de aplicação (ORM/service layer) é responsável por validar que o `entidade_id` referenciado existe na tabela correspondente ao `entidade_tipo` antes de qualquer insert. |

---

## STATUS

Este capítulo permanece **EM CONSTRUÇÃO** até validação humana. Após aprovação, deve ser marcado como `TRAVADO` — mudanças estruturais a partir daí passam a ter custo real de desenvolvimento (migrations).

Próximos capítulos sugeridos:
1. Dicionário de dados campo a campo (tipos, obrigatoriedade, origem, validações)
2. Estratégia de migrations e seed inicial (domínios, categorias-base, perfis)
3. Arquitetura backend FastAPI (módulos, endpoints do painel admin)
