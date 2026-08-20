# Coletor do Garimpo Emissões — Azul

Busca disponibilidade de assento por milhas, por rota e data, e envia a
oferta **mais barata** encontrada pra API do Garimpo
(`POST /api/v1/emissoes/ofertas`). Ver `domain/emissoes.py` no backend pra
entender o modelo de dados, e a seção 5 do `docs/ai/HANDOFF.md` pro
raciocínio completo por trás de cada decisão abaixo.

## Dois sistemas de busca, não um

Achado técnico de 20/08/2026: a Azul tem duas buscas de milhas
independentes, e o coletor precisa falar com as duas.

| | Site principal (`voeazul.com.br`) | `azulpelomundo.voeazul.com.br` |
|---|---|---|
| Cobre | Só a malha própria da Azul (Brasil + Flórida/Lisboa/Paris) | Parceiros também — "+3.000 destinos" (testado: Avianca, voos direto de outras cias) |
| Classe na busca | Não tem — Economy e Business vêm juntas no mesmo resultado | Tem (`cabinCategory=ECONOMY`\|`BUSINESS`) |
| Proteção | Akamai na borda, mas mais simples | **Akamai Bot Manager** (cookies `_abck`/`bm_*`) — mais forte, `curl` com cookies reais também toma 403 |
| Endpoint de dado | Não é REST — entrega via canal "Listen" do Firestore | REST limpo: `GET /api/availability?origin=...&destination=...` |
| URL de busca direta (depois de aquecer a sessão) | `url_site_principal()` em `urls.py`, validada 20/08 | `url_azul_pelo_mundo()` em `urls.py`, validada 20/08 |

Em ambos: a **primeira busca da sessão precisa vir de navegação normal**
(carregar a home, passar pelo formulário) — só depois disso a URL direta
funciona, encadeada. Site principal: teto observado ~10 buscas por sessão
(sessão anterior). `azulpelomundo`: testado 6 buscas internacionais
encadeadas sem bloqueio, teto real ainda não mapeado.

`rotas_emissao.fonte` (`SITE_PRINCIPAL` | `AZUL_PELO_MUNDO`) no banco diz
qual dos dois buscar pra cada rota.

## O que já está pronto

- `urls.py` + `test_urls.py`: monta as URLs de busca direta pros dois
  sistemas, testado contra URLs reais capturadas em 20/08 (não inventadas).

## O que ainda falta — não fiz de propósito, pra não inventar estrutura

- **Parsing do resultado**: preciso capturar e inspecionar de verdade a
  resposta de cada sistema antes de escrever isso.
  - `azulpelomundo`: o endpoint `/api/availability` devolve JSON, mas eu só
    confirmei a URL da chamada, nunca abri o corpo da resposta.
  - Site principal: não é REST, é um canal Firestore "Listen" — preciso
    entender esse formato antes de escrever qualquer parser.
- **Orquestração Playwright**: aquecer sessão, decidir quando reaquecer,
  navegar pelos dois sistemas na mesma execução, tratar `f"não temos voos
  disponíveis"` como resultado válido (rota sem oferta na data, não erro).
- **Seed de `rotas_emissao`**: a matriz de rotas foi fechada com o usuário
  (HANDOFF seção 5), mas a tabela ainda está vazia.
- **Agendamento**: nenhum plist criado ainda. Cadência ainda não decidida —
  a amostragem de datas (6 pontos entre 30-180 dias) multiplicada pelas
  rotas dá um volume que precisa de mais de uma execução por dia, provável.

## Estrutura

```
coletor-emissoes-azul/
  urls.py           # monta URL de busca direta pros dois sistemas
  test_urls.py       # 6 testes, contra URLs reais capturadas
  requirements.txt   # playwright + httpx, mesmo padrão do coletor-nativo
```
