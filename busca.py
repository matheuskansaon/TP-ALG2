# Consulta de entregadores no raio de um ponto, em duas etapas:
#   1. Trie: recupera os candidatos das células geohash que cobrem o círculo;
#   2. Haversine: descarta quem está fora do raio (a janela de células é um
#      retângulo, maior que o círculo).
# Também oferece a busca linear usada como referência nos testes e no benchmark.
import time
from dataclasses import dataclass, field

from geohash import cobrir_circulo, codificar
from geometria import calcular_distancia_haversine

VELOCIDADE_KMH = 30.0  # velocidade média suposta; o tempo estimado é em linha reta


def tempo_estimado_min(distancia_km, velocidade_kmh=VELOCIDADE_KMH):
    return round(distancia_km / velocidade_kmh * 60)


@dataclass
class ResultadoBusca:
    prefixos: list            # células geohash consultadas na Trie
    precisao: int             # tamanho dos prefixos
    candidatos: int           # entregadores devolvidos pela Trie (etapa 1)
    dentro: list = field(default_factory=list)  # [{'id','distancia','tempo'}], do mais perto ao mais longe
    ms_trie: float = 0.0
    ms_filtro: float = 0.0

    @property
    def ms_total(self):
        return self.ms_trie + self.ms_filtro


def _linha_tabela(entregador, distancia_km):
    return {'id': entregador['id'], 'distancia': round(distancia_km, 2),
            'tempo': tempo_estimado_min(distancia_km), '_d': distancia_km}


def _ordenar_e_limpar(linhas):
    linhas.sort(key=lambda l: (l['_d'], l['id']))
    for l in linhas:
        del l['_d']
    return linhas


def buscar_no_raio(trie, lat, lon, raio_km):
    """Entregadores a no máximo raio_km de (lat, lon), usando a Trie."""
    t0 = time.perf_counter()
    prefixos, precisao = cobrir_circulo(lat, lon, raio_km)
    candidatos = []
    for prefixo in prefixos:  # células disjuntas: nenhum entregador aparece duas vezes
        candidatos.extend(trie.buscar_prefixo(prefixo))
    t1 = time.perf_counter()

    dentro = []
    for ent in candidatos:
        d = calcular_distancia_haversine(lat, lon, ent['lat'], ent['lon'])
        if d <= raio_km:
            dentro.append(_linha_tabela(ent, d))
    t2 = time.perf_counter()

    return ResultadoBusca(prefixos, precisao, len(candidatos), _ordenar_e_limpar(dentro),
                          (t1 - t0) * 1000.0, (t2 - t1) * 1000.0)


def buscar_linear(entregadores, lat, lon, raio_km):
    """Referência O(N): Haversine em toda a frota. Mesmo formato de saída de buscar_no_raio."""
    dentro = []
    for ent in entregadores:
        d = calcular_distancia_haversine(lat, lon, ent['lat'], ent['lon'])
        if d <= raio_km:
            dentro.append(_linha_tabela(ent, d))
    return _ordenar_e_limpar(dentro)


def indexar(trie, entregadores, precisao=8):
    """Insere toda a frota na Trie (a árvore é esvaziada antes)."""
    trie.limpar()
    for ent in entregadores:
        trie.inserir(codificar(ent['lat'], ent['lon'], precisao), ent)
