# geometria.py
import math
import os
import time

# Caminhos relativos à raiz do projeto, e não à pasta de onde o app foi chamado.
RAIZ = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_GRAFO = os.path.join(RAIZ, "dados", "malha_bh.graphml")
PASTA_CACHE_OSMNX = os.path.join(RAIZ, "cache")
CENTRO_BH = (-19.916681, -43.934493)

# Servidores Overpass tentados em ordem. O principal costuma devolver 502/504
# sob carga, então a falha de um endpoint passa para o próximo.
# (overpass.kumi.systems foi removido: não responde e só consumia o timeout.)
ENDPOINTS_OVERPASS = [
    "https://overpass-api.de/api",
    "https://lz4.overpass-api.de/api",
]
RODADAS_DOWNLOAD = 1
ESPERA_BASE_S = 3
# Timeout de cada requisição ao Overpass ao abrir o app. O padrão do osmnx (180 s)
# fazia o app esperar mais de 10 min antes de desistir quando os servidores estavam
# fora. O scripts/baixar_malha.py usa valores mais pacientes (o osmnx repassa o
# timeout também ao servidor, que aborta consultas mais longas que ele).
TIMEOUT_OVERPASS_S = 60


def _osmnx():
    """Importa e configura o osmnx só quando preciso (o import é lento e pesado)."""
    import osmnx as ox

    ox.settings.use_cache = True
    ox.settings.log_console = False
    ox.settings.overpass_rate_limit = False
    ox.settings.cache_folder = PASTA_CACHE_OSMNX
    # Contorno de TLS só para o Python nativo do macOS (ver compat_macos.py)
    return ox


def _definir_endpoint(ox, url):
    # O nome da configuração mudou entre as versões do osmnx (1.x x 2.x).
    for nome in ("overpass_endpoint", "overpass_url"):
        if hasattr(ox.settings, nome):
            setattr(ox.settings, nome, url)
            return


class GeometriaRotas:
    def __init__(self):
        self.grafo = None
        self.erro_malha = None  # texto mostrado na interface quando não há malha
        self.ultima_projecao_aplicada = False

    @property
    def malha_disponivel(self):
        return self.grafo is not None

    def carregar_grafo(self, lat_centro=CENTRO_BH[0], lon_centro=CENTRO_BH[1],
                       raio_metros=12000, arquivo_grafo=ARQUIVO_GRAFO,
                       timeout_s=TIMEOUT_OVERPASS_S, rodadas=RODADAS_DOWNLOAD):
        """
        Carrega a malha do disco; se não existir (ou estiver corrompida), baixa com
        novas tentativas e alterna entre servidores Overpass. Retorna True se a
        malha ficou pronta.
        """
        ox = _osmnx()
        ox.settings.timeout = timeout_s
        if os.path.exists(arquivo_grafo):
            print(f"[OSMnx] Carregando malha viária do cache local ({arquivo_grafo})...")
            try:
                self.grafo = ox.load_graphml(arquivo_grafo)
                self.erro_malha = None
                print("[OSMnx] Malha viária carregada com sucesso!")
                return True
            except Exception as e:  # arquivo truncado (download interrompido) ou inválido
                print(f"[OSMnx] Arquivo da malha inválido ({e}); tentando baixar de novo.")

        ultimo_erro = None
        for rodada in range(rodadas):
            for endpoint in ENDPOINTS_OVERPASS:
                try:
                    print(f"[OSMnx] Baixando a malha de BH via {endpoint} (pode levar 1-2 min)...")
                    _definir_endpoint(ox, endpoint)
                    self.grafo = ox.graph_from_point(
                        (lat_centro, lon_centro), dist=raio_metros, network_type="drive"
                    )
                    os.makedirs(os.path.dirname(arquivo_grafo) or ".", exist_ok=True)
                    # grava num temporário e renomeia: se o processo morrer no meio,
                    # não fica um .graphml truncado no lugar do arquivo bom
                    temporario = arquivo_grafo + ".parcial"
                    ox.save_graphml(self.grafo, temporario)
                    os.replace(temporario, arquivo_grafo)
                    self.erro_malha = None
                    print(f"[OSMnx] Malha viária salva em {arquivo_grafo}!")
                    return True
                except Exception as e:  # rede, 502, timeout, resposta inválida
                    ultimo_erro = e
                    print(f"[OSMnx] Falha em {endpoint}: {e}")
            if rodada < rodadas - 1:
                time.sleep(ESPERA_BASE_S * (rodada + 1))

        self.grafo = None
        self.erro_malha = (
            "Malha viária indisponível: os entregadores foram gerados sem projeção "
            "nas ruas. Rode `python scripts/baixar_malha.py` e reinicie o app. "
            f"(último erro: {ultimo_erro})"
        )
        print(f"[OSMnx] Aviso: {self.erro_malha}")
        return False

    def projetar_multiplos_na_rua(self, lats, lons):
        """
        Leva cada ponto ao ponto mais próximo da RUA (e não ao cruzamento):
        1. nearest_edges (vetorizado) acha a aresta mais próxima de cada ponto;
        2. o ponto é projetado ortogonalmente na polilinha dessa aresta.

        Retorna (lats, lons). Sem malha carregada, devolve os pontos como vieram
        e deixa o aviso em self.erro_malha / self.ultima_projecao_aplicada.
        """
        lats, lons = list(lats), list(lons)
        self.ultima_projecao_aplicada = False
        if self.grafo is None:
            aviso = self.erro_malha or "Malha viária não carregada."
            print(f"[Projeção] Pulada: {aviso}")
            return lats, lons

        arestas = _osmnx().distance.nearest_edges(self.grafo, lons, lats)

        ruas_lat, ruas_lon = [], []
        for lat, lon, (u, v, chave) in zip(lats, lons, arestas):
            plat, plon, _ = projetar_na_polilinha(lat, lon, self._polilinha_da_aresta(u, v, chave))
            ruas_lat.append(plat)
            ruas_lon.append(plon)
        self.ultima_projecao_aplicada = True
        return ruas_lat, ruas_lon

    def _polilinha_da_aresta(self, u, v, chave):
        """Lista de (lat, lon) da aresta: a geometria real da rua, ou a reta u-v."""
        dados = self.grafo.edges[u, v, chave]
        geometria = dados.get("geometry")
        if geometria is not None:
            return [(y, x) for x, y in geometria.coords]
        no_u, no_v = self.grafo.nodes[u], self.grafo.nodes[v]
        return [(no_u["y"], no_u["x"]), (no_v["y"], no_v["x"])]


METROS_POR_GRAU = 111194.93  # 2*pi*6371000/360


def projetar_ponto_no_segmento(plat, plon, alat, alon, blat, blon):
    """
    Projeção ortogonal do ponto P no segmento AB (num plano local em metros).
    Retorna (lat, lon, distancia_m) do ponto do segmento mais próximo de P.
    Em BH (segmentos de dezenas de metros) o erro do plano local é desprezível.
    """
    k = math.cos(math.radians(plat))
    ax, ay = (alon - plon) * k * METROS_POR_GRAU, (alat - plat) * METROS_POR_GRAU
    bx, by = (blon - plon) * k * METROS_POR_GRAU, (blat - plat) * METROS_POR_GRAU
    dx, dy = bx - ax, by - ay
    comprimento2 = dx * dx + dy * dy
    # P está na origem, então t = -(A.(B-A)) / |B-A|^2, limitado a [0, 1]
    t = 0.0 if comprimento2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / comprimento2))
    fx, fy = ax + t * dx, ay + t * dy
    return alat + t * (blat - alat), alon + t * (blon - alon), math.hypot(fx, fy)


def projetar_na_polilinha(plat, plon, pontos):
    """Projeta P na polilinha [(lat, lon), ...]; escolhe o segmento mais próximo."""
    if len(pontos) == 1:
        lat, lon = pontos[0]
        return projetar_ponto_no_segmento(plat, plon, lat, lon, lat, lon)
    melhor = None
    for (alat, alon), (blat, blon) in zip(pontos, pontos[1:]):
        cand = projetar_ponto_no_segmento(plat, plon, alat, alon, blat, blon)
        if melhor is None or cand[2] < melhor[2]:
            melhor = cand
    return melhor


def calcular_distancia_haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Raio da Terra em km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
