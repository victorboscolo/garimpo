"""Recortes fiéis de respostas reais de GET /api/availability, busca
só-ida (tripType=ONE_WAY), capturadas em 21/08/2026 depois da mudança pra
busca só-ida. Duas buscas diferentes, cada uma recortada só na quantidade
de voos — nada aqui foi inventado ou misturado entre buscas.

RESPOSTA_REAL_GRU_LIS: GRU->LIS, 25/08/2026, Economy — todos os voos da
TAP Portugal são diretos (`connection: 0`), serve pra testar preço mais
barato e a taxa/companhia.

RESPOSTA_REAL_GRU_HND: GRU->HND, 25/08/2026, Economy — os voos da Japan
Airlines têm conexão (`connection: 1`, com um `flightGroup` de duas
pernas: GRU->JFK->HND), serve pra confirmar que `connection` é mesmo o
número de paradas, não um booleano.
"""

RESPOSTA_REAL_GRU_LIS = {
    "data": {
        "origin": "GRU",
        "finalDestination": "LIS",
        "departureFlights": {
            "date": "25/08/2026",
            "flights": [
                {
                    "id": 7,
                    "departureDate": "25/08/2026",
                    "departureTime": "00:45",
                    "firstFlightNumber": 84,
                    "operatingCarriers": ["TP"],
                    "marketingCarrier": "TP",
                    "points": {"value": 410000, "currency": "POINTS"},
                    "connection": 0,
                    "recommendations": [
                        {
                            "departureCategory": "ECONOMY",
                            "returnFlights": None,
                            "fee": {"total": {"value": 68.61, "currency": "BRL"}},
                            "validateCompany": "TP",
                        }
                    ],
                },
                {
                    "id": 28,
                    "departureDate": "25/08/2026",
                    "departureTime": "20:45",
                    "firstFlightNumber": 88,
                    "operatingCarriers": ["TP"],
                    "marketingCarrier": "TP",
                    "points": {"value": 494000, "currency": "POINTS"},
                    "connection": 0,
                    "recommendations": [
                        {
                            "departureCategory": "ECONOMY",
                            "returnFlights": None,
                            "fee": {"total": {"value": 68.61, "currency": "BRL"}},
                            "validateCompany": "TP",
                        }
                    ],
                },
            ],
        },
    }
}

RESPOSTA_REAL_GRU_HND = {
    "data": {
        "origin": "GRU",
        "finalDestination": "HND",
        "departureFlights": {
            "date": "25/08/2026",
            "flights": [
                {
                    "id": 1,
                    "departureDate": "25/08/2026",
                    "departureTime": "22:30",
                    "firstFlightNumber": 7201,
                    "operatingCarriers": ["AA"],
                    "marketingCarrier": "JL",
                    "points": {"value": 330500, "currency": "POINTS"},
                    "connection": 1,
                    "recommendations": [
                        {
                            "departureCategory": "ECONOMY",
                            "returnFlights": None,
                            "fee": {"total": {"value": 215.51, "currency": "BRL"}},
                            "validateCompany": "JL",
                        }
                    ],
                    "flightGroup": [
                        {"flightNumber": 7201, "origin": "GRU", "destination": "JFK"},
                        {"flightNumber": 7009, "origin": "JFK", "destination": "HND"},
                    ],
                },
                {
                    "id": 2,
                    "departureDate": "25/08/2026",
                    "departureTime": "22:00",
                    "firstFlightNumber": 7205,
                    "operatingCarriers": ["AA"],
                    "marketingCarrier": "JL",
                    "points": {"value": 330500, "currency": "POINTS"},
                    "connection": 1,
                    "recommendations": [
                        {
                            "departureCategory": "ECONOMY",
                            "returnFlights": None,
                            "fee": {"total": {"value": 215.51, "currency": "BRL"}},
                            "validateCompany": "JL",
                        }
                    ],
                    "flightGroup": [
                        {"flightNumber": 7205, "origin": "GRU", "destination": "DFW"},
                        {"flightNumber": 7013, "origin": "DFW", "destination": "HND"},
                    ],
                },
            ],
        },
    }
}
