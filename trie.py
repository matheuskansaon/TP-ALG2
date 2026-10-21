# trie.py
# Implementação da estrutura de dados Trie Compacta (Radix Tree / Patrícia) para armazenamento de prefixos.

class NoTrie:
    def __init__(self, prefixo=""):
        self.prefixo = prefixo  # Substring compactada representada pela aresta que chega a este nó
        self.filhos = {}        # Mapeia o primeiro caractere da aresta filha -> NoTrie
        self.entregadores = []  # Armazena os dados dos entregadores alocados neste nó

class ArvoreTrie:
    def __init__(self):
        self.raiz = NoTrie()
        
    def _tamanho_prefixo_comum(self, s1, s2):
        limite = min(len(s1), len(s2))
        i = 0
        while i < limite and s1[i] == s2[i]:
            i += 1
        return i

    def inserir(self, geohash, dados_entregador):
        """
        Insere uma string geohash na Trie Compacta comprimindo caminhos únicos
        e armazena a referência do entregador na folha correspondente.
        """
        no = self.raiz
        restante = geohash

        while restante:
            primeiro_char = restante[0]
            if primeiro_char not in no.filhos:
                novo_no = NoTrie(prefixo=restante)
                novo_no.entregadores.append(dados_entregador)
                no.filhos[primeiro_char] = novo_no
                return

            filho = no.filhos[primeiro_char]
            tam_comum = self._tamanho_prefixo_comum(restante, filho.prefixo)

            # Caso 1: A aresta do filho é inteiramente prefixo do que resta inserir
            if tam_comum == len(filho.prefixo):
                no = filho
                restante = restante[tam_comum:]
                if not restante:
                    no.entregadores.append(dados_entregador)
                    return
            # Caso 2: Divergência no meio da aresta -> divide (split) o nó filho
            else:
                no_intermediario = NoTrie(prefixo=restante[:tam_comum])
                filho.prefixo = filho.prefixo[tam_comum:]
                no_intermediario.filhos[filho.prefixo[0]] = filho
                no.filhos[primeiro_char] = no_intermediario

                sufixo_novo = restante[tam_comum:]
                if sufixo_novo:
                    novo_no = NoTrie(prefixo=sufixo_novo)
                    novo_no.entregadores.append(dados_entregador)
                    no_intermediario.filhos[sufixo_novo[0]] = novo_no
                else:
                    no_intermediario.entregadores.append(dados_entregador)
                return

        no.entregadores.append(dados_entregador)
        
    def buscar_prefixo(self, prefixo):
        """
        Busca em tempo O(m+k) todos os entregadores que compartilham o mesmo prefixo geohash.
        m = tamanho do prefixo, k = número de entregadores encontrados.
        """
        no = self.raiz
        restante = prefixo

        # O(m) para caminhar até o nó (ou aresta compactada) correspondente ao prefixo
        while restante:
            primeiro_char = restante[0]
            if primeiro_char not in no.filhos:
                return []

            filho = no.filhos[primeiro_char]
            if len(restante) <= len(filho.prefixo):
                if filho.prefixo.startswith(restante):
                    return self._coletar_todos(filho)
                return []
            else:
                if restante.startswith(filho.prefixo):
                    no = filho
                    restante = restante[len(filho.prefixo):]
                else:
                    return []
            
        # O(k) para coletar todos os entregadores nas subárvores compactadas
        return self._coletar_todos(no)
        
    def _coletar_todos(self, no):
        resultados = list(no.entregadores)
        for filho in no.filhos.values():
            resultados.extend(self._coletar_todos(filho))
        return resultados

    def limpar(self):
        """Descarta todos os nós para gerar uma nova frota."""
        self.raiz = NoTrie()