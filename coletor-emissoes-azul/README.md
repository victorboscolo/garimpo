# Coletor do Garimpo Emissões — Azul

Busca disponibilidade de assento por milhas, por rota e data, **só ida**
(decisão do usuário, 21/08 — ver `domain/emissoes.py` no backend), e envia
a oferta **mais barata** encontrada pra API do Garimpo
(`POST /api/v1/emissoes/ofertas`). Ver a seção 5 do `docs/ai/HANDOFF.md`
pro raciocínio completo por trás de cada decisão abaixo.

## Por que só ida

Uma promoção de ida sozinha tem mais alcance de público e dá liberdade pro
usuário não ficar preso a uma data de volta específica — uma "oferta de
volta" é só outra linha, na rota oposta, não um pacote amarrado à ida. E
mais: o preço da ida dentro de um pacote ida+volta pode ser mais barato do
que comprá-la sozinha, então descartar a volta de uma busca ida-e-volta
não bastava — a busca em si precisou virar só-ida de verdade nos dois
sistemas (revalidado empiricamente em 21/08/2026).

## Dois sistemas de busca, não um

Achado técnico de 20/08/2026: a Azul tem duas buscas de milhas
independentes, e o coletor precisa falar com as duas.

| | Site principal (`voeazul.com.br`) | `azulpelomundo.voeazul.com.br` |
|---|---|---|
| Cobre | Só a malha própria da Azul (Brasil + Flórida/Lisboa/Paris) | Parceiros também — "+3.000 destinos" (testado: TAP, Japan Airlines/American, Avianca) |
| Classe na busca | Não tem — Economy e Business vêm juntas no mesmo resultado | Tem (`cabinCategory=ECONOMY`\|`BUSINESS`) |
| Proteção | Akamai na borda, mas mais simples | **Akamai Bot Manager** (cookies `_abck`/`bm_*`) — mais forte, `curl` com cookies reais também toma 403 |
| Endpoint de dado | Nenhuma chamada de rede interceptável — lido do **DOM renderizado** (achado 21/08) | REST limpo: `GET /api/availability?tripType=ONE_WAY&origin=...&destination=...` |
| URL de busca direta (depois de aquecer a sessão) | `url_site_principal()` em `urls.py`, revalidada 21/08 pra só-ida | `url_azul_pelo_mundo()` em `urls.py`, revalidada 21/08 pra só-ida |
| Número de paradas | Texto do card: `(\d+)\s*conex` ou "Direto" (0) | Campo `connection` — inteiro de verdade, não booleano (confirmado: resposta real trouxe `connection: 1` com `flightGroup` de duas pernas) |

Em ambos: a **primeira busca da sessão precisa vir de navegação normal**
(carregar a home, passar pelo formulário) — só depois disso a URL direta
funciona, encadeada. Site principal: teto observado ~10 buscas por sessão
(sessão anterior). `azulpelomundo`: testado 6+ buscas internacionais
encadeadas sem bloqueio, teto real ainda não mapeado.

`rotas_emissao.fonte` (`SITE_PRINCIPAL` | `AZUL_PELO_MUNDO`) no banco diz
qual dos dois buscar pra cada rota.

## O que já está pronto

- `urls.py` + `test_urls.py`: monta as URLs de busca direta só-ida pros
  dois sistemas, testado contra URLs reais capturadas em 21/08 (não
  inventadas).
- `parsing.py` + `test_parsing.py`: extrai o voo de ida mais barato da
  resposta JSON do `azulpelomundo`, testado contra dois recortes fiéis de
  respostas reais (`fixture_azul_pelo_mundo.py`). Numa busca só-ida
  `returnFlights` vem `null` e o `points.value` no nível do próprio voo já
  é o preço real — sem a armadilha da busca ida-e-volta (não usada mais),
  onde esse mesmo campo era só o trecho de ida isolado.
- `parsing_site_principal.py` + `test_parsing_site_principal.py`: extrai
  preço em pontos, assentos restantes e número de paradas de um card do
  site principal, lido do DOM (não de rede — ver achado abaixo), testado
  contra `outerHTML` real de um card com conexão, um indisponível e um
  direto (`fixture_site_principal.py`).

### Achado 21/08: o site principal se lê pelo DOM, não pela rede

Confirmei os dois canais reais que o site usa —
`b2c-api.voeazul.com.br/tudoAzulReservationAvailability/.../v6/availability`
(REST) e um canal `Listen` do Firestore
(`firestore.googleapis.com/google.firestore.v1.Firestore/Listen/channel?database=projects%2Fazul-storage-prd%2F...`)
— mas nenhum dos dois foi interceptável com as ferramentas de rede
disponíveis (toda busca faz reload completo da página, a chamada acontece
cedo demais no carregamento). O caminho que funcionou: ler o **DOM já
renderizado**, mesmo princípio do fallback de texto do coletor da Livelo.
Confirmado de novo em 21-22/08 que os mesmos anchors valem pra busca
só-ida — o card não muda, só a página passa a ter uma seção em vez de duas.

Cada `.flight-card` tem:
- `data-test-id="fare-price fare-price-with-points"`: o preço real (com
  desconto). **Não** confundir com `.initial`, que é o preço riscado antes
  do desconto — os dois aparecem no mesmo card.
- `data-leg-remaining-seats`: assentos restantes, sinal de escassez de
  graça que o `azulpelomundo` não dá.
- Texto do voo: `"1 conexão    •  Voo 4450"` (com conexão) ou
  `"Voo 4043  Direto"` (sem conexão) — `extrair_paradas()` cobre os dois.
- O `id` do card, decodificado em base64 URL-safe, traz o itinerário
  completo (voos, aeroportos, horários) — não usado ainda no parser, fica
  como achado registrado pra quando precisar de mais detalhe do que o
  texto visível já dá.
- Sem oferta: mostra "Indisponível" e não tem o `data-test-id` do preço —
  resultado válido (rota sem disponibilidade nessa data), não erro.

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
  urls.py                          # monta URL de busca direta só-ida pros dois sistemas
  test_urls.py                      # 7 testes, contra URLs reais capturadas
  parsing.py                        # extrai o voo de ida mais barato do JSON do azulpelomundo
  test_parsing.py                   # 6 testes, contra JSON real
  fixture_azul_pelo_mundo.py        # dois recortes fiéis de respostas reais (direto e com conexão)
  parsing_site_principal.py         # extrai preço/assentos/paradas de um card do site principal (DOM)
  test_parsing_site_principal.py    # 9 testes, contra outerHTML real
  fixture_site_principal.py         # outerHTML real: card com conexão, indisponível e direto
  requirements.txt                  # playwright + httpx, mesmo padrão do coletor-nativo
```
