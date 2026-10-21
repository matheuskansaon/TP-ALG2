import unittest

import numpy as np

import geometria
from simulador import (DESVIO_PADRAO_GRAUS, SimuladorFrota, carregar_centros,
                       dentro_de_bh, dividir_entre_centros)


class SemMalha:
    """Geometria que não altera os pontos (isola o teste da distribuição)."""
    def projetar_multiplos_na_rua(self, lats, lons):
        return list(lats), list(lons)


def sim_com_centros():
    sim = SimuladorFrota(caminho_csv=None, geolocator=object(), arquivo_cache=None)
    sim.preparar_centros_demanda()
    return sim


class TestCentros(unittest.TestCase):
    def test_csv_de_centros_cobre_a_cidade(self):
        centros = carregar_centros("dados/centros_demanda.csv")
        self.assertGreaterEqual(len(centros), 20)
        self.assertEqual(len(centros), len(set(centros)))
        self.assertTrue(all(dentro_de_bh(lat, lon) for lat, lon in centros))
        lats = [c[0] for c in centros]
        lons = [c[1] for c in centros]
        # Espalhados: o conjunto atravessa BH de ponta a ponta (>15 km de norte a sul, >12 km de leste a oeste).
        self.assertGreater((max(lats) - min(lats)) * 111.2, 15)
        self.assertGreater((max(lons) - min(lons)) * 104.5, 12)

    def test_arquivo_ausente(self):
        self.assertEqual(carregar_centros("nao_existe.csv"), [])


class TestGeracao(unittest.TestCase):
    def test_quantidade_e_ids(self):
        ents = sim_com_centros().gerar_entregadores(103, SemMalha(), rng=np.random.default_rng(1))
        self.assertEqual(len(ents), 103)
        self.assertEqual(len({e["id"] for e in ents}), 103)
        self.assertEqual(ents[0]["id"], "E0001")

    def test_divisao_entre_centros(self):
        for n, k in [(100, 22), (7, 22), (22, 22), (5000, 22), (1, 3)]:
            q = dividir_entre_centros(n, k)
            self.assertEqual((sum(q), len(q)), (n, k))
            self.assertLessEqual(max(q) - min(q), 1)

    def test_barreiro_e_venda_nova_tem_entregadores(self):
        # Reclamação da revisão: com 5 centros no eixo Centro-Sul, essas regiões ficavam vazias.
        ents = sim_com_centros().gerar_entregadores(400, SemMalha(), rng=np.random.default_rng(3))
        for nome, (lat, lon) in {"Barreiro": (-19.9760, -44.0240), "Venda Nova": (-19.8120, -43.9510)}.items():
            perto = [e for e in ents if geometria.calcular_distancia_haversine(lat, lon, e["lat"], e["lon"]) <= 3.0]
            self.assertGreater(len(perto), 5, nome)

    def test_desvio_padrao_e_normal_em_torno_do_centro(self):
        sim = SimuladorFrota(caminho_csv=None, geolocator=object(), arquivo_cache=None)
        sim.centros_demanda = [(-19.92, -43.94)]
        ents = sim.gerar_entregadores(20000, SemMalha(), rng=np.random.default_rng(4))
        lats = np.array([e["lat"] for e in ents])
        lons = np.array([e["lon"] for e in ents])
        self.assertAlmostEqual(lats.std(), DESVIO_PADRAO_GRAUS, delta=0.0005)
        self.assertAlmostEqual(lons.std(), DESVIO_PADRAO_GRAUS, delta=0.0005)
        self.assertAlmostEqual(lats.mean(), -19.92, delta=0.0005)
        dentro_1sigma = np.mean((np.abs(lats + 19.92) < DESVIO_PADRAO_GRAUS))
        self.assertAlmostEqual(dentro_1sigma, 0.683, delta=0.02)

    def test_semente_repete_a_geracao(self):
        sim = sim_com_centros()
        a = sim.gerar_entregadores(50, SemMalha(), rng=np.random.default_rng(9))
        b = sim.gerar_entregadores(50, SemMalha(), rng=np.random.default_rng(9))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
