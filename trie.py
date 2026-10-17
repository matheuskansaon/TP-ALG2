# trie.py
# Implementação da estrutura de dados Trie para armazenamento de prefixos.

class NoTrie:
    def __init__(self):
        self.filhos = {}
        self.entregadores = []  # Armazena os dados do entregador que pertence a este nó ou subárvore

class ArvoreTrie:
    def __init__(self):
        self.raiz = NoTrie()
        
    def inserir(self, geohash, dados_entregador):
        """
        Insere uma string geohash na árvore e armazena a referência do entregador.
        """
        no = self.raiz
        for char in geohash:
            if char not in no.filhos:
                no.filhos[char] = NoTrie()
            no = no.filhos[char]
            
        # Adiciona o entregador na folha correspondente ao geohash completo
        no.entregadores.append(dados_entregador)
        
    def buscar_prefixo(self, prefixo):
        """
        Busca em tempo O(m+k) todos os entregadores que compartilham o mesmo prefixo geohash.
        m = tamanho do prefixo, k = número de entregadores encontrados.
        """
        no = self.raiz
        # O(m) para caminhar até o nó do prefixo
        for char in prefixo:
            if char not in no.filhos:
                return []
            no = no.filhos[char]
            
        # O(k) para coletar todos os entregadores nas subárvores
        return self._coletar_todos(no)
        
    def _coletar_todos(self, no):
        resultados = list(no.entregadores)
        for filho in no.filhos.values():
            resultados.extend(self._coletar_todos(filho))
        return resultados

    def limpar(self):
        """Descarta todos os nós para gerar uma nova frota."""
        self.raiz = NoTrie()