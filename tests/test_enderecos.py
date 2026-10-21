import unittest

import pandas as pd

import enderecos
from enderecos import (BAIRRO, EXATO, RUA, buscar_restaurantes, expandir_tipo,
                       indice_de_busca, montar_tentativas, normalizar, rotulo_restaurante)

LINHA = {"DESC_LOGRADOURO": "AVE", "NOME_LOGRADOURO": "PORTUGAL", "NUMERO_IMOVEL": 4316,
         "NOME_BAIRRO": "JARDIM ATLANTICO", "NOME": "BAR E CAFE DONATELO LTDA", "NOME_FANTASIA": float("nan")}


class TestAbreviacoes(unittest.TestCase):
    def test_expande_os_tipos_do_csv(self):
        esperado = {"AVE": "AVENIDA", "PCA": "PRACA", "ROD": "RODOVIA", "BEC": "BECO",
                    "ALA": "ALAMEDA", "EST": "ESTRADA", "TRV": "TRAVESSA"}
        for abrev, completo in esperado.items():
            self.assertEqual(expandir_tipo(abrev), completo)

    def test_rua_e_desconhecidos_ficam_como_estao(self):
        self.assertEqual(expandir_tipo("RUA"), "RUA")
        self.assertEqual(expandir_tipo("VDP"), "VDP")
        self.assertEqual(expandir_tipo(float("nan")), "")

    def test_normalizar(self):
        self.assertEqual(normalizar("  Praça   da Liberdade "), "PRACA DA LIBERDADE")


class TestTentativas(unittest.TestCase):
    def test_ordem_e_precisao(self):
        t = montar_tentativas(LINHA)
        self.assertEqual(t[0], ("AVENIDA PORTUGAL, 4316, JARDIM ATLANTICO, Belo Horizonte, MG, Brasil", EXATO))
        self.assertEqual([p for _, p in t], [EXATO, RUA, RUA, BAIRRO])
        self.assertTrue(all("AVE " not in c for c, _ in t))  # abreviação não vai para o Nominatim

    def test_sem_numero_nao_tenta_endereco_exato(self):
        for numero in (0, "S/N", float("nan"), ""):
            t = montar_tentativas({**LINHA, "NUMERO_IMOVEL": numero})
            self.assertNotIn(EXATO, [p for _, p in t], numero)

    def test_sem_duplicatas(self):
        t = montar_tentativas({**LINHA, "DESC_LOGRADOURO": "", "NOME_BAIRRO": ""})
        consultas = [c for c, _ in t]
        self.assertEqual(len(consultas), len(set(consultas)))


class TestBuscaRestaurantes(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame([
            {"DESC_LOGRADOURO": "AVE", "NOME_LOGRADOURO": "AFONSO PENA", "NUMERO_IMOVEL": 1000,
             "NOME_BAIRRO": "CENTRO", "NOME": "ALFA ALIMENTOS LTDA", "NOME_FANTASIA": "PADARIA DO ZE"},
            {"DESC_LOGRADOURO": "RUA", "NOME_LOGRADOURO": "DA BAHIA", "NUMERO_IMOVEL": 22,
             "NOME_BAIRRO": "LOURDES", "NOME": "BETA COMERCIO LTDA", "NOME_FANTASIA": float("nan")},
            {"DESC_LOGRADOURO": "RUA", "NOME_LOGRADOURO": "DOS TIMBIRAS", "NUMERO_IMOVEL": 5,
             "NOME_BAIRRO": "CENTRO", "NOME": "GAMA RESTAURANTE LTDA", "NOME_FANTASIA": "ZE DO PASTEL"},
        ], index=[10, 20, 30])
        self.indice = indice_de_busca(self.df)

    def test_por_nome_fantasia(self):
        self.assertEqual(buscar_restaurantes(self.indice, "padaria"), [10])

    def test_por_razao_social(self):
        self.assertEqual(buscar_restaurantes(self.indice, "beta comercio"), [20])

    def test_por_endereco_com_abreviacao_expandida(self):
        self.assertEqual(buscar_restaurantes(self.indice, "avenida afonso pena"), [10])

    def test_por_bairro_e_numero_sem_acento(self):
        self.assertEqual(buscar_restaurantes(self.indice, "lourdes 22"), [20])

    def test_todas_as_palavras_precisam_casar(self):
        self.assertCountEqual(buscar_restaurantes(self.indice, "ze centro"), [10, 30])
        self.assertEqual(buscar_restaurantes(self.indice, "ze lourdes"), [])

    def test_quem_casa_no_nome_vem_primeiro(self):
        # "centro" está no endereço dos dois; "pastel" só no nome do 30.
        self.assertEqual(buscar_restaurantes(self.indice, "centro pastel"), [30])

    def test_limite_e_termo_vazio(self):
        self.assertEqual(len(buscar_restaurantes(self.indice, "centro", limite=1)), 1)
        self.assertEqual(buscar_restaurantes(self.indice, "   "), [])

    def test_rotulo_prefere_nome_fantasia(self):
        self.assertTrue(rotulo_restaurante(self.df.loc[10]).startswith("PADARIA DO ZE — AVE AFONSO PENA, 1000"))
        self.assertTrue(rotulo_restaurante(self.df.loc[20]).startswith("BETA COMERCIO LTDA"))


if __name__ == "__main__":
    unittest.main()
