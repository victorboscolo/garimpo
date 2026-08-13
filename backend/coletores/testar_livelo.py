
"""Script de teste manual do coletor Livelo — roda a coleta real e imprime
o resultado no terminal, sem tocar no banco de dados.

Uso: docker compose run --rm backend python coletores/testar_livelo.py
"""
import asyncio

from coletores.livelo.coletor_livelo import ColetorLivelo


async def main():
    print("Iniciando coleta real da Livelo (pode levar 10-30 segundos)...\n")
    coletor = ColetorLivelo()
    promocoes = await coletor.coletar()

    print(f"\n{'='*70}")
    print(f"TOTAL COLETADO: {len(promocoes)} promoções")
    print(f"{'='*70}\n")

    for i, p in enumerate(promocoes[:15], start=1):
        clube = " [CLUBE]" if p.requer_clube else ""
        print(f"{i:3d}. {p.parceiro_nome_bruto:30s} {p.pontuacao:>6} {p.unidade_pontuacao}{clube}")

    if len(promocoes) > 15:
        print(f"\n... e mais {len(promocoes) - 15} promoções (mostrando só as 15 primeiras)")


if __name__ == "__main__":
    asyncio.run(main())
