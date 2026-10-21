import math
import random
import unittest

from geohash import (BASE32, cobrir_circulo, codificar, decodificar_bbox, dimensoes_celula,
                     dimensoes_celula_km, obter_vizinhos)
from geometria import calcular_distancia_haversine

BH = (-19.9167, -43.9345)


def ponto_a(lat, lon, dist_km, rumo_graus):
    """Ponto a dist_km de (lat, lon) no rumo dado (aproximação plana, ok para poucos km)."""
    r = math.radians(rumo_graus)
    return (lat + dist_km * math.cos(r) / 111.195,
            lon + dist_km * math.sin(r) / (111.195 * math.cos(math.radians(lat))))


class TestCodificacao(unittest.TestCase):
    def test_valores_conhecidos(self):
        self.assertEqual(codificar(57.64911, 10.40744, 8), "u4pruydq")  # exemplo da Wikipédia
        self.assertEqual(codificar(42.6, -5.6, 5), "ezs42")             # exemplo da Wikipédia

    def test_precisao_e_alfabeto(self):
        for p in range(1, 10):
            h = codificar(*BH, p)
            self.assertEqual(len(h), p)
            self.assertTrue(set(h) <= set(BASE32))

    def test_prefixo_de_precisao_menor(self):
        random.seed(1)
        for _ in range(200):
            lat, lon = random.uniform(-20.05, -19.78), random.uniform(-44.06, -43.86)
            h8 = codificar(lat, lon, 8)
            for p in range(1, 8):
                self.assertEqual(codificar(lat, lon, p), h8[:p])

    def test_bbox_contem_o_ponto(self):
        random.seed(2)
        for _ in range(200):
            lat, lon = random.uniform(-89, 89), random.uniform(-179, 179)
            for p in (4, 6, 8):
                s, n, o, l = decodificar_bbox(codificar(lat, lon, p))
                self.assertTrue(s <= lat < n and o <= lon < l)

    def test_ida_e_volta_do_centro(self):
        s, n, o, l = decodificar_bbox("u4pruydq")
        self.assertEqual(codificar((s + n) / 2, (o + l) / 2, 8), "u4pruydq")


class TestDimensoes(unittest.TestCase):
    def test_tamanhos_em_bh(self):
        # Valores citados no relatório: 0,61 km (p6), 4,60 km (p5), 19,5 km (p4).
        self.assertAlmostEqual(dimensoes_celula_km(6, -19.92)[0], 0.61, delta=0.01)
        self.assertAlmostEqual(dimensoes_celula_km(5, -19.92)[1], 4.60, delta=0.02)
        self.assertAlmostEqual(dimensoes_celula_km(4, -19.92)[0], 19.5, delta=0.1)

    def test_bate_com_a_decodificacao(self):
        for p in range(1, 9):
            s, n, o, l = decodificar_bbox(codificar(*BH, p))
            altura, largura = dimensoes_celula(p)
            self.assertAlmostEqual(n - s, altura, places=9)
            self.assertAlmostEqual(l - o, largura, places=9)


class TestVizinhos(unittest.TestCase):
    def test_oito_vizinhos_distintos(self):
        for p in (3, 5, 6, 8):
            viz = obter_vizinhos(codificar(*BH, p))
            self.assertEqual(len(viz), 8)
            self.assertNotIn(codificar(*BH, p), viz)

    def test_cada_vizinho_encosta_na_celula(self):
        h = codificar(*BH, 6)
        s, n, o, l = decodificar_bbox(h)
        for v in obter_vizinhos(h):
            vs, vn, vo, vl = decodificar_bbox(v)
            toca_lat = vs <= n + 1e-12 and vn >= s - 1e-12
            toca_lon = vo <= l + 1e-12 and vl >= o - 1e-12
            self.assertTrue(toca_lat and toca_lon, v)

    def test_pontos_do_outro_lado_da_borda_estao_nos_vizinhos(self):
        # Dois pontos a ~2 m um do outro, em lados opostos da borda leste/norte da célula.
        random.seed(3)
        for p in (4, 5, 6, 7):
            for _ in range(100):
                lat, lon = random.uniform(-20.05, -19.78), random.uniform(-44.06, -43.86)
                h = codificar(lat, lon, p)
                s, n, o, l = decodificar_bbox(h)
                eps = 2e-5
                for outro in [(lat, l + eps), (lat, o - eps), (n + eps, lon), (s - eps, lon),
                              (n + eps, l + eps), (s - eps, o - eps)]:
                    ho = codificar(*outro, p)
                    self.assertIn(ho, obter_vizinhos(h), (p, outro))

    def test_borda_que_muda_ja_no_primeiro_caractere(self):
        # A longitude -45 separa o caractere 1 ('7'...). Os dois lados têm prefixos diferentes.
        a, b = codificar(-19.9, -45.0001, 5), codificar(-19.9, -44.9999, 5)
        self.assertNotEqual(a[0], b[0])
        self.assertIn(b, obter_vizinhos(a))
        self.assertIn(a, obter_vizinhos(b))

    def test_antimeridiano_e_polos(self):
        h = codificar(0.0, 179.9999, 4)
        self.assertEqual(len(obter_vizinhos(h)), 8)           # a longitude dá a volta
        topo = codificar(89.99, 10.0, 4)
        self.assertEqual(len(obter_vizinhos(topo)), 5)        # sem células além do polo


class TestCobrirCirculo(unittest.TestCase):
    def test_todo_ponto_do_circulo_cai_numa_celula_devolvida(self):
        random.seed(4)
        for raio in (0.3, 0.5, 1.0, 2.0, 4.5, 7.0, 10.0):
            for _ in range(15):
                lat, lon = random.uniform(-20.0, -19.8), random.uniform(-44.0, -43.88)
                celulas, p = cobrir_circulo(lat, lon, raio)
                conjunto = set(celulas)
                for _ in range(80):
                    alvo = ponto_a(lat, lon, raio * math.sqrt(random.random()) * 0.999, random.uniform(0, 360))
                    self.assertIn(codificar(*alvo, p), conjunto, (raio, p))
                # pontos sobre a circunferência (os mais difíceis de cobrir)
                for rumo in range(0, 360, 15):
                    alvo = ponto_a(lat, lon, raio * 0.999, rumo)
                    self.assertIn(codificar(*alvo, p), conjunto, (raio, rumo))

    def test_numero_de_celulas_limitado_e_sem_repeticao(self):
        for raio in (0.5, 2.0, 10.0):
            celulas, _ = cobrir_circulo(*BH, raio)
            self.assertLessEqual(len(celulas), 64)
            self.assertEqual(len(celulas), len(set(celulas)))

    def test_precisao_diminui_com_o_raio(self):
        precisoes = [cobrir_circulo(*BH, r)[1] for r in (0.1, 0.5, 2.0, 5.0, 10.0)]
        self.assertEqual(precisoes, sorted(precisoes, reverse=True))
        self.assertEqual(cobrir_circulo(*BH, 2.0)[1], 6)
        self.assertEqual(cobrir_circulo(*BH, 10.0)[1], 5)

    def test_janela_a_2km_e_bem_menor_que_o_3x3_da_precisao_5(self):
        celulas, p = cobrir_circulo(*BH, 2.0)
        altura, largura = dimensoes_celula_km(p, BH[0])
        area_janela = len(celulas) * altura * largura
        altura5, largura5 = dimensoes_celula_km(5, BH[0])
        self.assertLess(area_janela, 0.4 * 9 * altura5 * largura5)
        self.assertLess(area_janela, 40)  # ~30 km2, contra ~200 km2 do 3x3 antigo

    def test_raio_pequeno_vira_no_maximo_um_bloco_3x3_quando_celula_maior_que_o_raio(self):
        celulas, p = cobrir_circulo(*BH, 0.05, max_celulas=9)
        self.assertLessEqual(len(celulas), 9)


if __name__ == "__main__":
    unittest.main()
