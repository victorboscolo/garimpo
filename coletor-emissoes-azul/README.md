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
| Endpoint de dado | Nenhuma chamada de rede interceptável — lido do **DOM renderizado** (achado 21/08) | REST limpo: `GET /api/availability?origin=...&destination=...` |
| URL de busca direta (depois de aquecer a sessão) | `url_site_principal()` em `urls.py`, validada 20/08 | `url_azul_pelo_mundo()` em `urls.py`, validada 20/08 |
| Ida e volta no resultado | **Duas seções separadas** de cards (não uma combinação por card) — preço total = menor preço da ida + menor preço da volta | Uma combinação por card, preço já somado |

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
- `parsing_site_principal.py` + `test_parsing_site_principal.py`: extrai o
  preço em pontos e assentos restantes de um card do site principal, lido
  do DOM (não de rede — ver achado abaixo), testado contra `outerHTML`
  real de um card disponível e um indisponível
  (`fixture_site_principal.py`).

### Achado 21/08: o site principal se lê pelo DOM, não pela rede

Confirmei os dois canais reais que o site usa —
`b2c-api.voeazul.com.br/tudoAzulReservationAvailability/.../v6/availability`
(REST) e um canal `Listen` do Firestore
(`firestore.googleapis.com/google.firestore.v1.Firestore/Listen/channel?database=projects%2Fazul-storage-prd%2F...`)
— mas nenhum dos dois foi interceptável com as ferramentas de rede
disponíveis (toda busca faz reload completo da página, a chamada acontece
cedo demais no carregamento). O caminho que funcionou: ler o **DOM já
renderizado**, mesmo princípio do fallback de texto do coletor da Livelo.

Cada `.flight-card` tem:
- `data-test-id="fare-price fare-price-with-points"`: o preço real (com
  desconto). **Não** confundir com `.initial`, que é o preço riscado antes
  do desconto — os dois aparecem no mesmo card.
- `data-leg-remaining-seats`: assentos restantes, sinal de escassez de
  graça que o `azulpelomundo` não dá.
- O `id` do card, decodificado em base64 URL-safe, traz o itinerário
  completo (voos, aeroportos, horários) — não usado ainda no parser, fica
  como achado registrado pra quando precisar de mais detalhe que "1 conexão
  • Voo NNNN" já dá pelo texto visível.
- Sem oferta: mostra "Indisponível" e não tem o `data-test-id` do preço —
  resultado válido (rota sem disponibilidade nessa data), não erro.

**Ida e volta não vêm combinadas** num card só (diferente do
`azulpelomundo`): são duas seções de cards separadas na mesma página. O
preço total da viagem é a soma do menor preço de cada seção
(`menor_preco_entre_os_cards()`), não um valor único por card.

## O que ainda falta

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
  urls.py                          # monta URL de busca direta pros dois sistemas
  test_urls.py                      # 6 testes, contra URLs reais capturadas
  parsing.py                        # extrai a oferta mais barata do JSON do azulpelomundo
  test_parsing.py                   # 6 testes, contra JSON real
  fixture_azul_pelo_mundo.py        # recorte fiel de uma resposta real
  parsing_site_principal.py         # extrai preço/assentos de um card do site principal (DOM)
  test_parsing_site_principal.py    # 7 testes, contra outerHTML real
  fixture_site_principal.py         # outerHTML real de um card disponível e um indisponível
  requirements.txt                  # playwright + httpx, mesmo padrão do coletor-nativo
```
