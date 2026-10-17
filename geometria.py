# geometria.py
import math
import osmnx as ox
import os

# Habilita o cache interno do OSMnx para evitar downloads redundantes
ox.settings.use_cache = True
ox.settings.log_console = False

class GeometriaRotas:
    def __init__(self):
        self.grafo = None

    def carregar_grafo(self, lat_centro=-19.916681, lon_centro=-43.934493, raio_metros=12000):
        arquivo_grafo = "dados/malha_bh.graphml"
        if os.path.exists(arquivo_grafo):
            self.grafo = ox.load_graphml(arquivo_grafo)
            return

        try:
            self.grafo = ox.graph_from_point((lat_centro, lon_centro), dist=raio_metros, network_type='drive')
            os.makedirs("dados", exist_ok=True)
            ox.save_graphml(self.grafo, arquivo_grafo)
        except Exception as e:
            self.grafo = None

    def projetar_multiplos_na_rua(self, lats, lons):
        """
        Versão vetorizada e ultrarrápida: calcula o nó mais próximo para TODOS 
        os entregadores de uma vez só, evitando reconstruir a árvore do OSMnx.
        """
        if self.grafo is None:
            return lats, lons 
            
        nos_ids = ox.distance.nearest_nodes(self.grafo, list(lons), list(lats))
        
        ruas_lat = [self.grafo.nodes[n]['y'] for n in nos_ids]
        ruas_lon = [self.grafo.nodes[n]['x'] for n in nos_ids]
        
        return ruas_lat, ruas_lon

def calcular_distancia_haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Raio da Terra em km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c