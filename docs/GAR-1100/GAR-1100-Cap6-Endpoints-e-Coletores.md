# GAR-1100 — Capítulo 6
# EXTENSÃO: ENDPOINTS DO PAINEL ADMIN E MÓDULO DE COLETORES
**Versão:** 1.0
**Status:** Em construção
**Pré-requisito:** GAR-1100 Cap. 2 (Arquitetura Backend FastAPI — já aprovado) · Cap. 3 Rev. 2 · Cap. 4

> **Nota:** o Capítulo 2 já define a arquitetura oficial (Monolito Modular, camadas `api/application/domain/infrastructure`, JWT, RN-001 a RN-007) e **não precisa ser refeito**. Este capítulo só preenche duas lacunas que o Cap. 2 deixou em aberto por ainda não termos o schema físico na época: a lista concreta de endpoints e o desenho interno do módulo `coletores/`.

---

## 1. Endpoints REST (`/api/v1`)

### Módulo `promocoes`

| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| GET | `/promocoes` | ADMIN, OPERADOR | Lista com filtros (`status`, `programa_id`, `parceiro_id`, `data_inicio`) |
| GET | `/promocoes/{id}` | ADMIN, OPERADOR | Detalhe completo, incluindo classificação ativa |
| GET | `/promocoes/pendentes` | ADMIN, OPERADOR | Fila de revisão (`status = PENDENTE`), ordenada por nota desc |
| POST | `/promocoes/{id}/aprovar` | ADMIN, OPERADOR | Muda `status → APROVADA`, preenche `aprovada_por`/`aprovada_em`, dispara publicação |
| POST | `/promocoes/{id}/rejeitar` | ADMIN, OPERADOR | Muda `status → REJEITADA`, exige `motivo_rejeicao` no corpo da requisição |
| POST | `/promocoes` | ADMIN | Criação manual (`origem = MANUAL`) |

### Módulo `classificacoes`

| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| GET | `/promocoes/{id}/classificacoes` | ADMIN, OPERADOR | Histórico de classificações (todas as versões do motor) |
| POST | `/promocoes/{id}/reclassificar` | ADMIN | Força reprocessamento com a versão atual do motor |

### Módulo `parceiros` / `programas` / `categorias`

| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| GET/POST | `/parceiros` | ADMIN | CRUD — inclui gestão de `parceiro_aliases` |
| GET/POST | `/programas` | ADMIN | CRUD |
| GET/POST | `/categorias` | ADMIN | CRUD, com `categoria_pai_id` para subcategorias |

### Módulo `configuracoes`

| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| GET | `/configuracoes?chave=...&escopo=...` | ADMIN | Lê a configuração resolvida (mais específica vence) |
| PUT | `/configuracoes/{id}` | ADMIN | Edita `valor` — grava `auditoria` automaticamente (RN-006 do Cap. 2) |

### Autenticação

| Método | Rota | Descrição |
|---|---|---|
| POST | `/auth/login` | Retorna JWT (perfil embutido no token) |

---

## 2. Módulo `coletores/` — desenho interno

Segue o padrão de módulo do Cap. 2 (`api/services/repositories/entities/schemas`), mas como este módulo não expõe rotas HTTP diretamente (roda como job agendado), sua estrutura é um pouco diferente:

```
coletores/
  base/
    coletor_base.py        # classe abstrata: coletar() -> list[PromocaoBruta]
  livelo/
    coletor_livelo.py       # implementa coletor_base para Livelo
  esfera/
    coletor_esfera.py       # implementa coletor_base para Esfera
  scheduler.py               # dispara os coletores periodicamente
  pipeline.py                 # orquestra: coleta -> hash -> dedup -> IA -> promocoes
```

**Fluxo de uma execução:**

```
scheduler dispara coletor_livelo.coletar()
  ↓
retorna lista de PromocaoBruta (dado ainda não persistido)
  ↓
pipeline calcula hash_promocao de cada item
  ↓
compara com hash já existente em `promocoes`
  ↓
se igual → descarta (não cria registro, conforme regra de armazenamento)
se novo/diferente → cria `promocoes` (status=PENDENTE, origem=COLETOR, origem_detalhe=COLETOR_LIVELO)
  ↓
aciona serviço de Classificação (módulo classificacao/, via interface de serviço — nunca acesso direto a repositório, conforme Cap. 2)
  ↓
promoção pronta para aparecer em /promocoes/pendentes
```

**Tratamento de erro (decisão já registrada — erro de coleta nunca derruba o sistema):**

- Cada coletor roda isolado; exceção em `coletor_esfera` não impede `coletor_livelo` de rodar.
- Falha é registrada em log estruturado (não em `auditoria`, que é para ações de usuário) com `origem_detalhe` do coletor que falhou.
- Retry automático: até 3 tentativas com backoff, depois marca falha e segue para a próxima execução agendada — sem intervenção manual necessária para o sistema continuar operando.

---

## 3. Módulo `telegram/` — integração com os 2 canais

Consome o serviço de Publicação (nunca acessa `promocoes` diretamente, conforme regra de baixo acoplamento do Cap. 2):

```
publicacao_service.publicar(promocao_id, tipo="PUBLICO")   → canal público (categoria + resumo)
publicacao_service.publicar(promocao_id, tipo="AVANCADO")  → canal restrito (nota + critérios)
```

Cada chamada gera um registro em `publicacoes` (`entidade_tipo=PROMOCAO`, `tipo`, `status=PENDENTE` → `ENVIADO`/`FALHA`).

---

## Próximo capítulo sugerido

GAR-1100 Capítulo 7 — Plano de Implantação Local (Mac): estrutura de diretórios do repositório, gestão de segredos (`.env`), rotina de backup, e checklist para a primeira execução ponta a ponta (coleta → classificação → aprovação → publicação).
