"""Recorte fiel de uma resposta real de GET /api/availability, capturada em
20/08/2026 (busca GRU->LHR, 15/09 a 22/09/2026, Economy). Só os dois
primeiros voos de ida foram mantidos — o resto do JSON é repetição da mesma
estrutura. Nada aqui foi inventado; é exatamente o que a API devolveu,
menos o corte de opções extras.
"""

RESPOSTA_REAL_TRIMMED = {
    "data": {
        "origin": "GRU",
        "finalDestination": "LHR",
        "departureFlights": {
            "date": "15/09/2026",
            "flights": [
                {
                    "id": 10,
                    "departureDate": "15/09/2026",
                    "departureTime": "15:30",
                    "firstFlightNumber": 246,
                    "operatingCarriers": ["BA"],
                    "marketingCarrier": "BA",
                    "points": {"value": 256500, "currency": "POINTS"},
                    "connection": 0,
                    "recommendations": [
                        {
                            "departureCategory": "ECONOMY",
                            "returnFlights": [
                                {
                                    "id": 7,
                                    "categories": [
                                        {
                                            "returnCategory": "ECONOMY",
                                            "points": {"value": 240000, "currency": "POINTS"},
                                            "fee": {"total": {"value": 1144.96, "currency": "BRL"}},
                                            "validateCompany": "BA",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
                {
                    "id": 1,
                    "departureDate": "15/09/2026",
                    "departureTime": "17:15",
                    "firstFlightNumber": 184,
                    "operatingCarriers": ["AV"],
                    "marketingCarrier": "AV",
                    "points": {"value": 192500, "currency": "POINTS"},
                    "connection": 1,
                    "recommendations": [
                        {
                            "departureCategory": "ECONOMY",
                            "returnFlights": [
                                {
                                    "id": 1,
                                    "categories": [
                                        {
                                            "returnCategory": "ECONOMY",
                                            "points": {"value": 142000, "currency": "POINTS"},
                                            "fee": {"total": {"value": 1144.96, "currency": "BRL"}},
                                            "validateCompany": "AV",
                                        }
                                    ],
                                },
                                {
                                    "id": 2,
                                    "categories": [
                                        {
                                            "returnCategory": "ECONOMY",
                                            "points": {"value": 142000, "currency": "POINTS"},
                                            "fee": {"total": {"value": 1144.96, "currency": "BRL"}},
                                            "validateCompany": "AV",
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                },
            ],
        },
    }
}
