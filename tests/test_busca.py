import random
import unittest

import numpy as np

from busca import (ResultadoBusca, buscar_linear, buscar_no_raio, indexar,
                   tempo_estimado_min)
from geohash import codificar
from trie import ArvoreTrie

BH = (-19.9167, -43.9345)


def frota(n, seed, centro=BH, sigma=0.03):
    rng = np.random.default_rng(seed)
    return [{'id': f"E{i:04d}", 'lat': float(la), 'lon': float(lo)}
            for i, (la, lo) in enumerate(zip(rng.normal(centro[0], sigma, n), rng.normal(centro[1], sigma, n)), 1)]


class TestBusca(unittest.TestCase):
    def test_trie_igual_a_busca_linear(self):
        random.seed(5)
        entregadores = frota(3000, 1)
        trie = ArvoreTrie()
        indexar(trie, entregadores)
        for raio in (0.5, 1.0, 2.0, 4.5, 6.0, 10.0):
            for _ in range(10):
                lat = random.uniform(-19.97, -19.86)
                lon = random.uniform(-43.99, -43.88)
                esperado = buscar_linear(entregadores, lat, lon, raio)
                obtido = buscar_no_raio(trie, lat, lon, raio).dentro
                self.assertEqual(obtido, esperado, (raio, lat, lon))

    def test_ponto_na_borda_do_raio(self):
        # Entregador exatamente a raio_km (a 1 ponto do limite) continua dentro.
        trie = ArvoreTrie()
        ent = [{'id': 'E1', 'lat': BH[0] + 2.0 / 111.195, 'lon': BH[1]}]
        indexar(trie, ent)
        r = buscar_no_raio(trie, *BH, 2.0001)
        self.assertEqual([x['id'] for x in r.dentro], ['E1'])

    def test_candidatos_sao_superconjunto_e_bem_menores_que_a_frota(self):
        entregadores = frota(5000, 2, sigma=0.06)
        trie = ArvoreTrie()
        indexar(trie, entregadores)
        r = buscar_no_raio(trie, *BH, 2.0)
        self.assertGreaterEqual(r.candidatos, len(r.dentro))
        self.assertLess(r.candidatos, 0.5 * len(entregadores))

    def test_resultado_ordenado_e_formato(self):
        entregadores = frota(500, 3)
        trie = ArvoreTrie()
        indexar(trie, entregadores)
        r = buscar_no_raio(trie, *BH, 3.0)
        self.assertIsInstance(r, ResultadoBusca)
        dist = [x['distancia'] for x in r.dentro]
        self.assertEqual(dist, sorted(dist))
        self.assertEqual(set(r.dentro[0]), {'id', 'distancia', 'tempo'})
        self.assertGreaterEqual(r.ms_total, 0)
        self.assertEqual(r.precisao, len(r.prefixos[0]))

    def test_frota_vazia(self):
        trie = ArvoreTrie()
        indexar(trie, [])
        r = buscar_no_raio(trie, *BH, 2.0)
        self.assertEqual((r.candidatos, r.dentro), (0, []))

    def test_tempo_estimado(self):
        self.assertEqual(tempo_estimado_min(15.0), 30)   # 15 km a 30 km/h = 30 min
        self.assertEqual(tempo_estimado_min(0.0), 0)

    def test_indexar_limpa_a_arvore(self):
        trie = ArvoreTrie()
        indexar(trie, frota(10, 1))
        indexar(trie, frota(4, 2))
        self.assertEqual(len(trie.buscar_prefixo("")), 4)


if __name__ == "__main__":
    unittest.main()
