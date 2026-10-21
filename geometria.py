# geometria.py
import math
import os
import shutil
import subprocess
import requests
import osmnx as ox

# Habilita o cache interno do OSMnx para evitar downloads redundantes
ox.settings.use_cache = True
ox.settings.log_console = False
ox.settings.overpass_rate_limit = False

# Fallback automático para macOS com Python nativo (LibreSSL 2.8.3 sem suporte a TLS 1.3):
# Caso o servidor (Overpass API / Nominatim) recuse o handshake TLS 1.2 antigo do LibreSSL 2.8.3,
# utiliza o /usr/bin/curl nativo do sistema (que possui SecureTransport / TLS 1.3).
_original_session_send = requests.Session.send


def _session_send_com_fallback_curl(self, request, **kwargs):
    try:
        return _original_session_send(self, request, **kwargs)
    except requests.exceptions.SSLError:
        curl_bin = shutil.which("curl") or "/usr/bin/curl"
        timeout = kwargs.get("timeout")
        if isinstance(timeout, tuple):
            timeout = max(timeout)
        timeout = int(timeout or 180)

        cmd = [curl_bin, "-sS", "-L", "-m", str(timeout), "-w", "\n%{http_code}", "-X", request.method]
        for k, v in (request.headers or {}).items():
            if k.lower() == "accept-encoding":
                continue
            cmd.extend(["-H", f"{k}: {v}"])
        if request.body:
            body_str = request.body.decode("utf-8") if isinstance(request.body, bytes) else str(request.body)
            cmd.extend(["--data-raw", body_str])
        cmd.append(request.url)

        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            raise
        saida = proc.stdout
        linhas = saida.rsplit(b"\n", 1)
        corpo = linhas[0] if len(linhas) == 2 else saida
        status_bytes = linhas[1].strip() if len(linhas) == 2 else b"200"

        resp = requests.Response()
        resp.status_code = int(status_bytes) if status_bytes.isdigit() else 200
        resp.reason = "OK" if 200 <= resp.status_code < 400 else "Error"
        resp._content = corpo
        resp.encoding = "utf-8"
        resp.url = request.url
        resp.request = request
        return resp


requests.Session.send = _session_send_com_fallback_curl

class GeometriaRotas:
    def __init__(self):
        self.grafo = None

    def carregar_grafo(self, lat_centro=-19.916681, lon_centro=-43.934493, raio_metros=12000):
        arquivo_grafo = "dados/malha_bh.graphml"
        if os.path.exists(arquivo_grafo):
            print(f"[OSMnx] Carregando malha viária do cache local ({arquivo_grafo})...")
            self.grafo = ox.load_graphml(arquivo_grafo)
            print("[OSMnx] Malha viária carregada com sucesso!")
            return

        try:
            print("[OSMnx] Baixando malha viária de Belo Horizonte (1ª execução, aguarde 1-2 min)...")
            self.grafo = ox.graph_from_point((lat_centro, lon_centro), dist=raio_metros, network_type='drive')
            os.makedirs("dados", exist_ok=True)
            ox.save_graphml(self.grafo, arquivo_grafo)
            print(f"[OSMnx] Malha viária salva em {arquivo_grafo}!")
        except Exception as e:
            print(f"[OSMnx] Aviso: Não foi possível carregar a malha viária ({e}).")
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