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
- `parsing.py` + `test_parsing.py`: extrai a oferta mais barata (ida+volta)
  da resposta JSON do `azulpelomundo`, testado contra um recorte fiel de
  uma resposta real (`fixture_azul_pelo_mundo.py`). Armadilha real: o
  `points.value` no nível do voo de ida é só o preço do trecho de ida
  sozinho — o preço da combinação completa mora dentro de
  `recommendations[].returnFlights[].categories[].points.value`.

## O que ainda falta — não fiz de propósito, pra não inventar estrutura

- **Parsing do resultado do site principal**: confirmados os dois canais
  reais que ele usa —
  `b2c-api.voeazul.com.br/tudoAzulReservationAvailability/api/tudoazul/reservation/availability/v6/availability`
  (REST) e um canal `Listen` do Firestore
  (`firestore.googleapis.com/google.firestore.v1.Firestore/Listen/channel?database=projects%2Fazul-storage-prd%2F...`).
  Os resultados chegam de verdade na tela nos testes manuais, mas **toda
  busca faz reload completo da página** — isso impediu interceptar o
  payload real com as ferramentas de rede disponíveis aqui (a chamada
  acontece cedo demais no carregamento). Precisa de uma sessão com
  DevTools de verdade pra capturar isso; não vale a pena escrever parser
  sem ver o dado.
- **Orquestração Playwright**: aquecer sessão, decidir quando reaquecer,
  navegar pelos dois sistemas na mesma execução, tratar `"não temos voos
  disponíveis"` como resultado válido (rota sem oferta na data, não erro).
- **Seed de `rotas_emissao`**: a matriz de rotas foi fechada com o usuário
  (HANDOFF seção 5), mas a tabela ainda está vazia.
- **Agendamento**: nenhum plist criado ainda. Cadência ainda não decidida —
  a amostragem de datas (6 pontos entre 30-180 dias) multiplicada pelas
  rotas dá um volume que precisa de mais de uma execução por dia, provável.

## Estrutura

```
coletor-emissoes-azul/
  urls.py                       # monta URL de busca direta pros dois sistemas
  test_urls.py                   # 6 testes, contra URLs reais capturadas
  parsing.py                     # extrai a oferta mais barata do JSON do azulpelomundo
  test_parsing.py                # 6 testes, contra JSON real
  fixture_azul_pelo_mundo.py     # recorte fiel de uma resposta real
  requirements.txt               # playwright + httpx, mesmo padrão do coletor-nativo
```
