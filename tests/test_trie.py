import random
import unittest

from geohash import BASE32, codificar
from trie import ArvoreTrie


def ids(lista):
    return sorted(x['id'] for x in lista)


def todos_os_nos(trie):
    pilha = [trie.raiz]
    while pilha:
        no = pilha.pop()
        yield no
        pilha.extend(no.filhos.values())


class TestInsercao(unittest.TestCase):
    def test_caso_novo_filho(self):
        t = ArvoreTrie()
        t.inserir("abc", {'id': 1})
        t.inserir("xyz", {'id': 2})
        self.assertEqual(set(t.raiz.filhos), {'a', 'x'})
        self.assertEqual(t.raiz.filhos['a'].prefixo, "abc")  # aresta compactada, 1 nó

    def test_caso_aresta_inteira_e_prefixo_desce(self):
        t = ArvoreTrie()
        t.inserir("ab", {'id': 1})
        t.inserir("abcd", {'id': 2})
        no_ab = t.raiz.filhos['a']
        self.assertEqual(no_ab.prefixo, "ab")
        self.assertEqual(no_ab.filhos['c'].prefixo, "cd")
        self.assertEqual(ids(no_ab.entregadores), [1])

    def test_caso_divisao_no_meio_da_aresta(self):
        t = ArvoreTrie()
        t.inserir("abcd", {'id': 1})
        t.inserir("abxy", {'id': 2})
        meio = t.raiz.filhos['a']
        self.assertEqual(meio.prefixo, "ab")
        self.assertEqual(meio.entregadores, [])
        self.assertEqual({k: v.prefixo for k, v in meio.filhos.items()}, {'c': "cd", 'x': "xy"})

    def test_divisao_onde_a_nova_chave_termina_no_ponto_de_divisao(self):
        t = ArvoreTrie()
        t.inserir("abcd", {'id': 1})
        t.inserir("ab", {'id': 2})
        meio = t.raiz.filhos['a']
        self.assertEqual((meio.prefixo, ids(meio.entregadores)), ("ab", [2]))
        self.assertEqual(meio.filhos['c'].prefixo, "cd")

    def test_mesma_chave_acumula_entregadores(self):
        t = ArvoreTrie()
        for i in range(3):
            t.inserir("u0v7abcd", {'id': i})
        self.assertEqual(ids(t.buscar_prefixo("u0v7abcd")), [0, 1, 2])
        self.assertEqual(t.contar_nos(), 1)


class TestBusca(unittest.TestCase):
    def setUp(self):
        self.t = ArvoreTrie()
        for i, h in enumerate(["abcd", "abxy", "abce", "zzzz"]):
            self.t.inserir(h, {'id': i})

    def test_prefixo_que_termina_no_meio_de_uma_aresta(self):
        t = ArvoreTrie()
        t.inserir("abcdefgh", {'id': 1})
        # a aresta "abcdefgh" é uma só; o prefixo "abcd" acaba no meio dela
        self.assertEqual(ids(t.buscar_prefixo("abcd")), [1])
        self.assertEqual(ids(t.buscar_prefixo("a")), [1])
        self.assertEqual(t.buscar_prefixo("abcx"), [])      # diverge no meio da aresta
        self.assertEqual(t.buscar_prefixo("abcdefghi"), [])  # mais longo que qualquer chave

    def test_prefixos_em_varios_niveis(self):
        self.assertEqual(ids(self.t.buscar_prefixo("ab")), [0, 1, 2])
        self.assertEqual(ids(self.t.buscar_prefixo("abc")), [0, 2])
        self.assertEqual(ids(self.t.buscar_prefixo("abcd")), [0])
        self.assertEqual(ids(self.t.buscar_prefixo("zzzz")), [3])
        self.assertEqual(self.t.buscar_prefixo("q"), [])

    def test_prefixo_vazio_devolve_tudo(self):
        self.assertEqual(ids(self.t.buscar_prefixo("")), [0, 1, 2, 3])

    def test_limpar(self):
        self.t.limpar()
        self.assertEqual(self.t.buscar_prefixo(""), [])
        self.assertEqual(self.t.contar_nos(), 0)


class TestContraBuscaLinear(unittest.TestCase):
    def test_aleatorio_igual_a_varredura(self):
        random.seed(6)
        chaves = ["".join(random.choice(BASE32[:4]) for _ in range(8)) for _ in range(2000)]
        t = ArvoreTrie()
        for i, c in enumerate(chaves):
            t.inserir(c, {'id': i})
        for _ in range(300):
            m = random.randint(0, 8)
            prefixo = "".join(random.choice(BASE32[:5]) for _ in range(m))
            esperado = sorted(i for i, c in enumerate(chaves) if c.startswith(prefixo))
            self.assertEqual(ids(t.buscar_prefixo(prefixo)), esperado, prefixo)

    def test_com_geohash_real(self):
        random.seed(7)
        pontos = [(random.uniform(-20.0, -19.8), random.uniform(-44.0, -43.9)) for _ in range(1500)]
        hashes = [codificar(la, lo, 8) for la, lo in pontos]
        t = ArvoreTrie()
        for i, h in enumerate(hashes):
            t.inserir(h, {'id': i})
        for p in (3, 4, 5, 6, 7):
            alvo = hashes[random.randrange(len(hashes))][:p]
            esperado = [i for i, h in enumerate(hashes) if h.startswith(alvo)]
            self.assertEqual(ids(t.buscar_prefixo(alvo)), sorted(esperado))


class TestCompacidade(unittest.TestCase):
    def test_todo_no_sem_entregador_tem_pelo_menos_dois_filhos(self):
        random.seed(8)
        t = ArvoreTrie()
        for i in range(3000):
            t.inserir("".join(random.choice("0123456789bcdefg") for _ in range(8)), {'id': i})
        for no in todos_os_nos(t):
            if no is t.raiz:
                continue
            self.assertTrue(no.entregadores or len(no.filhos) >= 2, no.prefixo)

    def test_subarvore_tem_no_maximo_2k_nos(self):
        # Base da análise O(m+k): numa árvore compacta, a subárvore com k entregadores
        # em chaves distintas tem no máximo 2k-1 nós, então coletá-la custa O(k).
        random.seed(9)
        t = ArvoreTrie()
        for i in range(2000):
            t.inserir("".join(random.choice(BASE32) for _ in range(8)), {'id': i})
        for prefixo in ["", "0", "1b", "3"]:
            k = len(t.buscar_prefixo(prefixo))
            if k == 0:
                continue
            sub = ArvoreTrie()
            sub.raiz = self._no_do_prefixo(t, prefixo)
            self.assertLessEqual(sub.contar_nos() + 1, 2 * k)

    def test_estatisticas_compactacao(self):
        t = ArvoreTrie()
        t.inserir("7h2y8nrb", {'id': 1})
        t.inserir("7h2y8nrc", {'id': 2})
        stats = t.estatisticas_compactacao()
        self.assertEqual(stats["nos_compactos"], 3)  # "7h2y8nr", "b", "c"
        self.assertEqual(stats["nos_padrao"], 9)     # 7 + 1 + 1 caracteres
        self.assertGreater(stats["reducao_pct"], 60.0)

    @staticmethod
    def _no_do_prefixo(t, prefixo):
        no, resto = t.raiz, prefixo
        while resto:
            filho = no.filhos[resto[0]]
            if len(resto) <= len(filho.prefixo):
                return filho
            no, resto = filho, resto[len(filho.prefixo):]
        return no


if __name__ == "__main__":
    unittest.main()
