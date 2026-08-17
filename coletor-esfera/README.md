# Coletor Esfera

Ao contrário do coletor da Livelo, este **não precisa de Chromium nem de
Playwright**. A Esfera expõe uma API pública
(`GET /bff-product/ehcs/products?categoryId=esf02163`) sem cookie, sessão ou
qualquer proteção anti-robô — confirmado com `curl` puro em 17/08/2026. O
coletor é Python simples com `httpx`.

Continua rodando fora do Docker, via launchd, para manter um único padrão
operacional de agendamento com o coletor da Livelo — não por necessidade
técnica desta vez.

Envia os dados coletados via HTTP para `POST /api/v1/promocoes/ingerir`,
igual ao coletor da Livelo. Só cria promoções **PENDENTES**: a aprovação
continua manual, no painel.

## O que fica de fora, por ora

A Esfera não expõe campo limpo equivalente ao `parityBau` da Livelo (piso
fora de campanha) nem a datas de início/fim de campanha — só aparecem em
texto livre do regulamento, com redação inconsistente entre parceiros. Ver
o cabeçalho de `esfera_api.py` para o levantamento que embasou essa decisão.

## Setup (uma vez só)

```bash
cd coletor-esfera

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Testar manualmente

Com a API rodando no Docker (`docker compose up -d backend`), rode:

```bash
./rodar_coletor.sh
```

Ou diretamente:

```bash
source venv/bin/activate
python3 coletor_esfera.py
```

Testes (não precisam da API nem do Docker — são só a lógica de mapeamento):

```bash
source venv/bin/activate
python3 -m pytest test_esfera_api.py -v
```

## Agendar automaticamente (launchd)

```bash
cp com.garimpo.coletor-esfera.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.garimpo.coletor-esfera.plist
```

Roda diariamente às 10h20 (15 minutos depois do coletor da Livelo, para não
disputar recursos no mesmo minuto).

```bash
# Rodar manualmente uma vez, via launchd
launchctl start com.garimpo.coletor-esfera

# Ver os logs
cat coletor.log
cat coletor-erro.log
```
