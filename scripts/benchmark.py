# scripts/benchmark.py
# Avalia experimentalmente o desempenho da Trie Compacta + filtro Haversine
# frente à busca linear O(N) para diferentes tamanhos de frota (N) e raios (km).
# Uso:
#     python scripts/benchmark.py
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import busca  # noqa: E402
from simulador import CENTRO_BH, SimuladorFrota  # noqa: E402
from trie import ArvoreTrie  # noqa: E402


class _SemMalha:
    def projetar_multiplos_na_rua(self, lats, lons):
        return list(lats), list(lons)


def executar_benchmark(tamanhos_frota=(100, 500, 1000, 5000, 10000), raio_km=2.0, consultas=25):
    sim = SimuladorFrota(caminho_csv=None, geolocator=object(), arquivo_cache=None)
    sim.preparar_centros_demanda()
    rng = np.random.default_rng(42)
    sem_malha = _SemMalha()

    print("=" * 88)
    print(f"BENCHMARK EXPERIMENTAL - TRIE COMPACTA vs. BUSCA LINEAR (Raio = {raio_km} km, {consultas} consultas)")
    print("=" * 88)
    cabecalho = (
        f"{'N Frota':>8} | {'Nós Trie':>9} | {'Redução':>8} | "
        f"{'Index (ms)':>10} | {'Trie+Hav (ms)':>13} | {'Linear (ms)':>11} | {'Speedup':>8}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))

    pontos_consulta = [
        (
            float(rng.uniform(-19.97, -19.85)),
            float(rng.uniform(-43.99, -43.90)),
        )
        for _ in range(consultas)
    ]

    for n in tamanhos_frota:
        frota = sim.gerar_entregadores(n, sem_malha, rng=rng)
        trie = ArvoreTrie()

        t0 = time.perf_counter()
        busca.indexar(trie, frota)
        ms_index = (time.perf_counter() - t0) * 1000.0

        stats = trie.estatisticas_compactacao()

        tempos_trie = []
        tempos_linear = []
        for lat_q, lon_q in pontos_consulta:
            res = busca.buscar_no_raio(trie, lat_q, lon_q, raio_km)
            tempos_trie.append(res.ms_total)

            tl0 = time.perf_counter()
            ref = busca.buscar_linear(frota, lat_q, lon_q, raio_km)
            tempos_linear.append((time.perf_counter() - tl0) * 1000.0)

            assert [x["id"] for x in res.dentro] == [x["id"] for x in ref]

        media_trie = sum(tempos_trie) / len(tempos_trie)
        media_linear = sum(tempos_linear) / len(tempos_linear)
        speedup = media_linear / media_trie if media_trie > 0 else 1.0

        print(
            f"{n:>8d} | {stats['nos_compactos']:>9d} | {stats['reducao_pct']:>7.1f}% | "
            f"{ms_index:>10.2f} | {media_trie:>13.3f} | {media_linear:>11.3f} | {speedup:>7.2f}x"
        )
    print("=" * 88)


def main():
    parser = argparse.ArgumentParser(description="Executa benchmark experimental da Trie Compacta.")
    parser.add_argument("--raio", type=float, default=2.0, help="Raio de busca em km (padrão: 2.0)")
    parser.add_argument("--consultas", type=int, default=25, help="Número de consultas por tamanho N (padrão: 25)")
    args = parser.parse_args()
    executar_benchmark(raio_km=args.raio, consultas=args.consultas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
