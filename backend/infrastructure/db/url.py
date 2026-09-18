"""Adapta a `DATABASE_URL` de provedores gerenciados (Neon, e a maioria dos
outros) pro driver `asyncpg`.

Esses provedores devolvem parâmetros do mundo libpq/psycopg na própria URL —
`sslmode=require`, `channel_binding=require` — que o `asyncpg` não reconhece
como parte da URL: ele falha a conexão com `TypeError: connect() got an
unexpected keyword argument 'sslmode'` (ou `channel_binding`). SSL no asyncpg
é `connect_args={"ssl": ...}`, um argumento separado, não parte da URL.

Local (Postgres do docker-compose, sem TLS) não tem nenhum desses parâmetros,
então a URL sai inalterada e `connect_args` fica vazio.
"""
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

# Nomes de parâmetro do libpq que o asyncpg não entende na URL. `sslmode`
# liga o TLS (via connect_args); os demais (channel_binding, sslcert, etc.)
# são camadas extra de segurança do libpq sem equivalente direto no asyncpg —
# seguras de descartar aqui, porque o TLS em si já é garantido pelo `ssl`
# passado via connect_args.
_PARAMETROS_LIBPQ = {"sslmode", "channel_binding", "sslcert", "sslkey", "sslrootcert"}


def preparar_conexao(database_url: str) -> tuple[str, dict]:
    partes = urlsplit(database_url)
    query = parse_qs(partes.query, keep_blank_values=True)

    exige_ssl = "require" in query.get("sslmode", [])
    for parametro in _PARAMETROS_LIBPQ:
        query.pop(parametro, None)

    nova_query = urlencode(query, doseq=True)
    nova_url = urlunsplit((partes.scheme, partes.netloc, partes.path, nova_query, partes.fragment))

    connect_args = {"ssl": "require"} if exige_ssl else {}
    return nova_url, connect_args
