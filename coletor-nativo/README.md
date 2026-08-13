# Coletor Livelo Nativo

Roda direto no macOS (fora do Docker) porque o site da Livelo bloqueia
(403 Access Denied) o Chromium rodando dentro de um container Linux,
mesmo com disfarces de headers. Rodando nativo no Mac, usa o Chromium
real do sistema — muito mais parecido com um usuário comum.

Envia os dados coletados via HTTP para `POST /api/v1/promocoes/ingerir`
na API (que continua rodando no Docker, como sempre).

## Setup (uma vez só)

```bash
cd coletor-nativo

# Cria um ambiente virtual Python isolado (não interfere com o resto do sistema)
python3 -m venv venv
source venv/bin/activate

# Instala as dependências
pip install -r requirements.txt

# Instala o Chromium do Playwright (versão nativa do Mac, não a do Docker)
playwright install chromium
```

## Testar manualmente

Com a API rodando no Docker (`docker compose up -d backend`), rode:

```bash
./rodar_coletor.sh
```

Ou diretamente:

```bash
source venv/bin/activate
python3 coletor_livelo_nativo.py
```

## Agendar automaticamente (launchd)

1. Edite `com.garimpo.coletor-livelo.plist` e troque `SEU_USUARIO` pelo seu
   nome de usuário real do Mac (aparece no Terminal antes do `@`) em todos
   os caminhos.

2. Copie o arquivo para a pasta de agentes do usuário:

```bash
cp com.garimpo.coletor-livelo.plist ~/Library/LaunchAgents/
```

3. Carregue o agendamento:

```bash
launchctl load ~/Library/LaunchAgents/com.garimpo.coletor-livelo.plist
```

A partir daqui, o coletor roda sozinho a cada 6 horas (mais uma vez
imediatamente ao carregar, para testar), sem precisar abrir nada
manualmente — desde que o Mac esteja ligado.

## Comandos úteis

```bash
# Ver se está agendado
launchctl list | grep garimpo

# Rodar manualmente uma vez, via launchd (bom para testar sem esperar 6h)
launchctl start com.garimpo.coletor-livelo

# Ver os logs
cat coletor.log
cat coletor-erro.log

# Pausar o agendamento (sem apagar a configuração)
launchctl unload ~/Library/LaunchAgents/com.garimpo.coletor-livelo.plist

# Retomar
launchctl load ~/Library/LaunchAgents/com.garimpo.coletor-livelo.plist
```

## Limitação conhecida

Só roda enquanto o Mac estiver ligado. Se o Mac estiver desligado ou
hibernando no horário agendado, essa execução é simplesmente pulada até
o próximo ciclo (não acumula nem executa "atrasado").
