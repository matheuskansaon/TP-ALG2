import unittest
from types import SimpleNamespace

import simulador
from simulador import Coordenada, SimuladorFrota, dentro_de_bh

LINHA = {"DESC_LOGRADOURO": "AVE", "NOME_LOGRADOURO": "PORTUGAL", "NUMERO_IMOVEL": 4316,
         "NOME_BAIRRO": "JARDIM ATLANTICO", "NOME": "X", "NOME_FANTASIA": float("nan")}
EM_BH = SimpleNamespace(latitude=-19.85, longitude=-43.97)
FORA = SimpleNamespace(latitude=-22.9, longitude=-43.2)  # Rio de Janeiro


class FakeGeolocator:
    """Responde conforme o roteiro: cada item é um resultado, None ou uma exceção."""
    def __init__(self, roteiro):
        self.roteiro, self.consultas = list(roteiro), []

    def geocode(self, consulta, timeout=None):
        self.consultas.append(consulta)
        item = self.roteiro.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Relogio:
    def __init__(self):
        self.t, self.esperas = 0.0, []

    def agora(self):
        return self.t

    def dormir(self, s):
        self.esperas.append(s)
        self.t += s


def criar(roteiro):
    rel = Relogio()
    geo = FakeGeolocator(roteiro)
    sim = SimuladorFrota(caminho_csv=None, geolocator=geo, arquivo_cache=None,
                         dormir=rel.dormir, agora=rel.agora)
    return sim, geo, rel


class TestGeocodificacao(unittest.TestCase):
    def test_endereco_exato(self):
        sim, geo, _ = criar([EM_BH])
        r = sim.geocodificar(LINHA, 1)
        self.assertEqual((r.lat, r.lon, r.precisao, r.aproximada), (-19.85, -43.97, "exato", False))
        self.assertEqual(len(geo.consultas), 1)
        self.assertIn("AVENIDA PORTUGAL", geo.consultas[0])

    def test_fallback_avisa_que_e_aproximado(self):
        sim, _, _ = criar([None, None, None, EM_BH])  # só o bairro é achado
        r = sim.geocodificar(LINHA, 1)
        self.assertEqual(r.precisao, "bairro")
        self.assertTrue(r.aproximada)

    def test_descarta_resultado_fora_de_bh(self):
        sim, _, _ = criar([FORA, EM_BH])
        r = sim.geocodificar(LINHA, 1)
        self.assertEqual(r.precisao, "rua")  # a 1ª consulta (exata) caiu fora de BH

    def test_cache_evita_nova_consulta(self):
        sim, geo, _ = criar([EM_BH])
        sim.geocodificar(LINHA, 7)
        sim.geocodificar(LINHA, 7)
        self.assertEqual(len(geo.consultas), 1)

    def test_timeout_e_repetido_e_depois_funciona(self):
        sim, geo, _ = criar([simulador.GeocoderTimedOut("t"), simulador.GeocoderTimedOut("t"), EM_BH])
        self.assertIsNotNone(sim.geocodificar(LINHA, 1))
        self.assertEqual(len(geo.consultas), 3)

    def test_servico_fora_do_ar_nao_quebra_e_nao_insiste_nas_outras_consultas(self):
        erros = [simulador.GeocoderUnavailable("fora")] * simulador.TENTATIVAS_POR_CONSULTA
        sim, geo, _ = criar(erros)
        self.assertIsNone(sim.geocodificar(LINHA, 1))
        self.assertEqual(len(geo.consultas), simulador.TENTATIVAS_POR_CONSULTA)
        self.assertIn("indispon", sim.ultimo_erro_geo)

    def test_erro_generico_do_servico_e_tratado(self):
        sim, _, _ = criar([simulador.GeopyError("HTTP 429")] * simulador.TENTATIVAS_POR_CONSULTA)
        self.assertIsNone(sim.geocodificar(LINHA, 1))
        self.assertIn("429", sim.ultimo_erro_geo)

    def test_respeita_uma_requisicao_por_segundo(self):
        sim, _, rel = criar([None, None, None, None])
        sim.geocodificar(LINHA, 1)  # 4 consultas seguidas, todas sem resultado
        instantes_minimos = simulador.INTERVALO_NOMINATIM_S * 3
        self.assertGreaterEqual(rel.t, instantes_minimos - 1e-9)

    def test_texto_livre(self):
        sim, geo, _ = criar([EM_BH])
        r = sim.geocodificar_texto("  Rua da Bahia   1000 ")
        self.assertEqual(r.precisao, "exato")
        self.assertEqual(geo.consultas[0], "Rua da Bahia 1000, Belo Horizonte, MG, Brasil")
        self.assertIsNone(sim.geocodificar_texto("   "))

    def test_wrapper_antigo_devolve_tupla(self):
        sim, _, _ = criar([EM_BH])
        self.assertEqual(sim.geocodificar_endereco(LINHA, 1), (-19.85, -43.97))

    def test_limites_de_bh(self):
        self.assertTrue(dentro_de_bh(-19.9167, -43.9345))
        self.assertFalse(dentro_de_bh(-22.9, -43.2))


class TestCacheEmDisco(unittest.TestCase):
    def test_persiste_entre_execucoes(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as d:
            arq = os.path.join(d, "geo.json")
            rel = Relogio()
            a = SimuladorFrota(None, FakeGeolocator([EM_BH]), arq, rel.dormir, rel.agora)
            a.geocodificar(LINHA, 3)
            geo2 = FakeGeolocator([])  # se consultar, o roteiro vazio levanta IndexError
            b = SimuladorFrota(None, geo2, arq, rel.dormir, rel.agora)
            self.assertEqual(b.geocodificar(LINHA, 3), Coordenada(-19.85, -43.97, "exato"))
            self.assertEqual(geo2.consultas, [])


if __name__ == "__main__":
    unittest.main()
