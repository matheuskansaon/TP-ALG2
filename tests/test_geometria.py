import math
import unittest
from types import SimpleNamespace

import networkx as nx

import geometria
from geometria import (GeometriaRotas, calcular_distancia_haversine,
                       projetar_na_polilinha, projetar_ponto_no_segmento)

LAT, LON = -19.92, -43.94
M = 1 / geometria.METROS_POR_GRAU  # 1 metro em graus de latitude


class TestHaversine(unittest.TestCase):
    def test_um_grau_de_latitude(self):
        self.assertAlmostEqual(calcular_distancia_haversine(0, 0, 1, 0), 111.19, places=1)

    def test_mesmo_ponto(self):
        self.assertEqual(calcular_distancia_haversine(LAT, LON, LAT, LON), 0.0)

    def test_simetria(self):
        a = calcular_distancia_haversine(LAT, LON, -19.85, -43.97)
        b = calcular_distancia_haversine(-19.85, -43.97, LAT, LON)
        self.assertAlmostEqual(a, b, places=9)


class TestProjecaoNoSegmento(unittest.TestCase):
    def test_pe_da_perpendicular_no_meio_do_segmento(self):
        # Segmento leste-oeste de 200 m; ponto 100 m ao norte do meio.
        dlon = 100 / (geometria.METROS_POR_GRAU * math.cos(math.radians(LAT)))
        lat, lon, dist = projetar_ponto_no_segmento(LAT + 100 * M, LON, LAT, LON - dlon, LAT, LON + dlon)
        self.assertAlmostEqual(lat, LAT, places=9)
        self.assertAlmostEqual(lon, LON, places=9)
        self.assertAlmostEqual(dist, 100, delta=0.5)

    def test_alem_da_ponta_cai_no_extremo(self):
        lat, lon, _ = projetar_ponto_no_segmento(LAT, LON + 0.01, LAT, LON - 0.001, LAT, LON)
        self.assertEqual((lat, lon), (LAT, LON))

    def test_segmento_degenerado(self):
        lat, lon, dist = projetar_ponto_no_segmento(LAT + 50 * M, LON, LAT, LON, LAT, LON)
        self.assertEqual((lat, lon), (LAT, LON))
        self.assertAlmostEqual(dist, 50, delta=0.5)

    def test_quarteirao_longo_nao_vai_para_o_cruzamento(self):
        # Rua de 400 m; ponto a 20 m dela, no meio. O resultado fica ~20 m do ponto,
        # enquanto o cruzamento mais próximo (nó) estaria a ~200 m.
        dlon = 200 / (geometria.METROS_POR_GRAU * math.cos(math.radians(LAT)))
        lat, lon, dist = projetar_ponto_no_segmento(LAT + 20 * M, LON, LAT, LON - dlon, LAT, LON + dlon)
        self.assertLess(dist, 25)
        self.assertLess(calcular_distancia_haversine(LAT + 20 * M, LON, lat, lon), 0.025)


class TestPolilinha(unittest.TestCase):
    def test_escolhe_o_segmento_mais_proximo(self):
        # "L": segmento horizontal seguido de vertical; ponto perto do vertical.
        d = 0.002
        pontos = [(LAT, LON), (LAT, LON + d), (LAT + d, LON + d)]
        lat, lon, _ = projetar_na_polilinha(LAT + d / 2, LON + d + 0.0001, pontos)
        self.assertAlmostEqual(lon, LON + d, places=9)
        self.assertAlmostEqual(lat, LAT + d / 2, places=9)

    def test_um_unico_ponto(self):
        lat, lon, _ = projetar_na_polilinha(LAT + 0.001, LON, [(LAT, LON)])
        self.assertEqual((lat, lon), (LAT, LON))


class FakeOx:
    """Troca o osmnx: devolve sempre a aresta (1, 2, 0), como se fosse a mais próxima."""
    def __init__(self):
        self.distance = SimpleNamespace(nearest_edges=lambda G, X, Y: [(1, 2, 0)] * len(X))


class TestGeometriaRotas(unittest.TestCase):
    def setUp(self):
        self._original = geometria._osmnx
        geometria._osmnx = lambda: FakeOx()

    def tearDown(self):
        geometria._osmnx = self._original

    def _grafo(self, geometria_aresta=None):
        g = nx.MultiDiGraph()
        g.add_node(1, y=LAT, x=LON - 0.002)
        g.add_node(2, y=LAT, x=LON + 0.002)
        dados = {} if geometria_aresta is None else {"geometry": geometria_aresta}
        g.add_edge(1, 2, 0, **dados)
        return g

    def test_sem_malha_devolve_pontos_e_registra_que_pulou(self):
        geo = GeometriaRotas()
        lats, lons = geo.projetar_multiplos_na_rua([LAT + 0.001], [LON])
        self.assertEqual((lats, lons), ([LAT + 0.001], [LON]))
        self.assertFalse(geo.ultima_projecao_aplicada)

    def test_projeta_na_reta_entre_os_nos(self):
        geo = GeometriaRotas()
        geo.grafo = self._grafo()
        lats, lons = geo.projetar_multiplos_na_rua([LAT + 0.001, LAT - 0.001], [LON, LON + 0.0005])
        self.assertTrue(geo.ultima_projecao_aplicada)
        self.assertAlmostEqual(lats[0], LAT, places=9)
        self.assertAlmostEqual(lons[0], LON, places=9)
        self.assertAlmostEqual(lons[1], LON + 0.0005, places=9)  # não colou no nó

    def test_usa_a_geometria_curva_da_aresta(self):
        curva = SimpleNamespace(coords=[(LON - 0.002, LAT), (LON, LAT + 0.001), (LON + 0.002, LAT)])
        geo = GeometriaRotas()
        geo.grafo = self._grafo(curva)
        lats, _ = geo.projetar_multiplos_na_rua([LAT + 0.003], [LON])
        self.assertAlmostEqual(lats[0], LAT + 0.001, places=9)  # topo da curva


if __name__ == "__main__":
    unittest.main()
