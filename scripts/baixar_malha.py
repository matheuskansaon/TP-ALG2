# scripts/baixar_malha.py
# Baixa a malha viária de BH e salva em dados/malha_bh.graphml.
# Rode uma vez (ou de novo, se o Overpass estiver instável) antes de abrir o app:
#     python scripts/baixar_malha.py [--raio 12000]
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from geometria import GeometriaRotas  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Baixa a malha viária de Belo Horizonte.")
    parser.add_argument("--raio", type=int, default=12000, help="raio em metros ao redor do centro (padrão: 12000)")
    parser.add_argument("--refazer", action="store_true", help="apaga o arquivo existente e baixa de novo")
    parser.add_argument("--timeout", type=int, default=180,
                        help="timeout de cada consulta ao Overpass, em segundos (padrão: 180)")
    args = parser.parse_args()

    from geometria import ARQUIVO_GRAFO
    if args.refazer and os.path.exists(ARQUIVO_GRAFO):
        os.remove(ARQUIVO_GRAFO)

    geo = GeometriaRotas()
    # Aqui ninguém espera a interface abrir: mais tempo e mais rodadas que no app.
    if geo.carregar_grafo(raio_metros=args.raio, timeout_s=args.timeout, rodadas=2):
        print(f"OK: {geo.grafo.number_of_nodes()} nós e {geo.grafo.number_of_edges()} arestas.")
        return 0
    print(geo.erro_malha, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
