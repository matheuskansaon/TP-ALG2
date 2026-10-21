# scripts/gerar_centros.py
# Regenera dados/centros_demanda.csv geocodificando, no Nominatim, os bairros com
# mais restaurantes no bares.csv (os bairros com mais restaurantes concentram mais
# pedidos). Respeita 1 requisição por segundo, então 20 bairros levam ~30 s.
#     python scripts/gerar_centros.py [--quantidade 20]
import argparse
import os
import sys

import pandas as pd

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RAIZ)

from simulador import ARQUIVO_CENTROS, ARQUIVO_RESTAURANTES, SimuladorFrota  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Gera o CSV de centros de demanda.")
    parser.add_argument("--quantidade", type=int, default=20, help="quantos bairros usar (padrão: 20)")
    parser.add_argument("--csv", default=ARQUIVO_RESTAURANTES)
    parser.add_argument("--saida", default=ARQUIVO_CENTROS)
    args = parser.parse_args()

    bares = pd.read_csv(args.csv)
    bairros = bares["NOME_BAIRRO"].value_counts().head(args.quantidade).index.tolist()

    regionais = {}
    if os.path.exists(args.saida):  # preserva a coluna regional já preenchida à mão
        antigo = pd.read_csv(args.saida)
        regionais = dict(zip(antigo["nome"], antigo.get("regional", "")))

    sim = SimuladorFrota(caminho_csv=None)
    linhas = []
    for bairro in bairros:
        r = sim.geocodificar_texto(f"bairro {bairro}")
        if r is None:
            print(f"  [falhou] {bairro} ({sim.ultimo_erro_geo or 'não encontrado'})")
            continue
        print(f"  {bairro}: {r.lat:.5f}, {r.lon:.5f}")
        linhas.append({"nome": bairro, "lat": round(r.lat, 5), "lon": round(r.lon, 5),
                       "regional": regionais.get(bairro, ""), "fonte": "nominatim"})

    if not linhas:
        print("Nenhum bairro geocodificado; o arquivo existente foi mantido.", file=sys.stderr)
        return 1
    pd.DataFrame(linhas).to_csv(args.saida, index=False)
    print(f"{len(linhas)} centros gravados em {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
