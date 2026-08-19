#!/bin/bash
# Checagem periódica do Painel de Saúde: atraso não é evento como falha —
# ninguém "avisa" sozinho que um job ficou atrasado, ele só fica assim
# conforme o tempo passa sem ninguém reportar. Este script existe só pra
# bater aqui de tempos em tempos e deixar o backend decidir se avisa
# (ver application/saude_service.py::verificar_atrasados_e_alertar).
#
# Roda via launchd (com.garimpo.verificar-saude.plist), em intervalo fixo
# (StartInterval), não em horário de calendário — não importa a que hora do
# dia roda, só que rode com regularidade.
curl -s --max-time 30 -X POST http://127.0.0.1:8000/api/v1/saude/verificar-atrasados > /dev/null
