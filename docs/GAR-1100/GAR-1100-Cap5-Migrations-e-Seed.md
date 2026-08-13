# GAR-1100 — Capítulo 5
# ESTRATÉGIA DE MIGRATIONS E SEED INICIAL — GARIMPO PROMOÇÕES (MVP)
**Versão:** 1.0
**Status:** Em construção
**Pré-requisitos:** GAR-1100 Cap. 3 (Rev. 2) — Modelo Físico · Cap. 4 — Dicionário de Dados

---

## Ordem de criação das tabelas (respeitando dependências de FK)

```
1.  dominios
2.  marcas
3.  categorias
4.  programas          (depende de dominios)
5.  parceiros          (depende de marcas, categorias)
6.  parceiro_aliases   (depende de parceiros)
7.  usuarios
8.  perfis
9.  usuario_perfis     (depende de usuarios, perfis)
10. configuracoes      (depende de dominios, programas, parceiros — todas nullable)
11. promocoes          (depende de programas, parceiros, usuarios)
12. categorias_promocao(depende de promocoes, categorias)
13. classificacoes     (entidade_id sem FK nativa — ver RN-012/013)
14. arquivos           (idem)
15. publicacoes        (idem)
16. auditoria          (depende de usuarios)
```

Ferramenta recomendada: **Alembic** (padrão para PostgreSQL + SQLAlchemy/FastAPI), uma migration por tabela nesta primeira leva, para manter o histórico de versionamento granular e facilitar rollback pontual se algo falhar durante a implantação inicial.

---

## Seed inicial (dados que o sistema precisa para funcionar no primeiro dia)

### 1. `dominios`

| nome | ativo |
|---|---|
| PROMOCOES | true |
| EMISSOES | false *(reservado — fica inativo até entrar em escopo)* |

### 2. `perfis`

| nome |
|---|
| ADMIN |
| OPERADOR |

### 3. `programas`

| nome | dominio |
|---|---|
| Livelo | PROMOCOES |
| Esfera | PROMOCOES |

*(Smiles, Latam Pass, TudoAzul ficam cadastrados apenas quando Emissões entrar em escopo — RN-007 já permite cadastro via painel sem precisar de nova migration.)*

### 4. `categorias` (nível raiz — exemplo inicial, expansível via painel)

```
Moda
Eletrônicos
Supermercado
Farmácia
Viagens
Casa
Esportes
Livros
```

Subcategorias (ex.: Moda → Roupas, Calçados, Acessórios) ficam para cadastro incremental conforme os primeiros parceiros forem coletados — não é necessário popular todas de antemão.

### 5. `configuracoes` (nível GLOBAL — `dominio_id`, `programa_id`, `parceiro_id` todos NULL)

```json
[
  {
    "chave": "pesos_motor_v1",
    "valor": {
      "historico": 25,
      "atratividade": 25,
      "amplitude": 20,
      "facilidade": 10,
      "exclusividade": 10,
      "confiabilidade_dados": 10
    },
    "descricao": "Pesos dos 6 pilares do Motor V1. Soma deve ser 100."
  },
  {
    "chave": "faixas_classificacao",
    "valor": {
      "excepcional": { "min": 90, "max": 100 },
      "excelente":   { "min": 75, "max": 89 },
      "boa":         { "min": 55, "max": 74 },
      "comum":       { "min": 35, "max": 54 },
      "pouco_atrativa": { "min": 0, "max": 34 }
    },
    "descricao": "Faixas de nota que definem a categoria final exibida ao usuário."
  },
  {
    "chave": "historico_suficiente",
    "valor": { "min_campanhas": 3, "janela_dias": 365 },
    "descricao": "Limiar para o motor considerar o histórico da família (parceiro+programa) como suficiente, sem cair no fallback."
  },
  {
    "chave": "peso_temporal",
    "valor": {
      "recente_dias": 180, "recente_peso": 1.0,
      "medio_dias": 365, "medio_peso": 0.6,
      "antigo_peso": 0.3
    },
    "descricao": "PROPOSTA A VALIDAR: campanhas nos últimos 180 dias entram com peso 1.0 no cálculo de médias históricas; entre 180-365 dias, peso 0.6; acima de 365 dias, peso 0.3. Os multiplicadores numéricos (1.0/0.6/0.3) não haviam sido definidos no documento original — são uma proposta inicial a refinar com dados reais, seguindo o mesmo espírito de 'faixas_classificacao'."
  }
]
```

> ⚠️ **Ponto para sua validação:** os multiplicadores `1.0 / 0.6 / 0.3` de `peso_temporal` são uma proposta minha (o documento original definia apenas "máximo/médio/reduzido" qualitativamente, com as janelas de 180/365 dias já definidas). Se quiser ajustar os números antes de rodar o seed, é só avisar — do contrário, seguimos com esses valores e refinamos depois, como já vínhamos fazendo com os outros parâmetros.

---

## Estratégia de migrations — princípios

- **MIG-001** — Cada migration é reversível (`downgrade` implementado, não só `upgrade`), mesmo no MVP — o custo de escrever o rollback agora é baixo comparado a precisar reconstruir o banco manualmente depois de um erro em produção.
- **MIG-002** — Seed de dados (`dominios`, `perfis`, `configuracoes` iniciais) roda como uma migration própria, separada da criação de schema — assim é possível recriar o ambiente do zero (ex.: para testes) com um único comando.
- **MIG-003** — Nenhuma migration futura pode alterar o *conteúdo* de `promocoes` já persistidas (coerente com a imutabilidade — RN-001 do Cap. 3); migrations de schema podem adicionar colunas nullable, nunca reescrever histórico.
- **MIG-004** — Alterações em `configuracoes` (pesos, faixas) **não são migrations** — são operações normais de UPDATE feitas pelo painel admin ou por script de calibração; migrations só criam a estrutura e o seed inicial.

---

## Ambiente

Confirmando a decisão já registrada no início do projeto: banco rodando **localmente no Mac** nesta fase, com toda a estrutura (UUID como PK, timestamps com timezone, sem dependência de features específicas de nuvem) já preparada para portabilidade — migração para um provedor gerenciado no futuro não deve exigir mudança de schema, apenas mudança de connection string e rotina de backup.

---

## Próximo capítulo sugerido

GAR-1100 Capítulo 6 — Arquitetura Backend FastAPI (módulos, estrutura de diretórios, endpoints do painel admin, integração com o coletor Playwright).
