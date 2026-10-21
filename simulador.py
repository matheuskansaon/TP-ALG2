# simulador.py
import json
import os
import time
from dataclasses import dataclass

import pandas as pd
import numpy as np

import enderecos

try:
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable, GeopyError
except ImportError:  # geopy ausente (ex.: testes): classes só para o except funcionar
    class GeopyError(Exception):
        pass

    class GeocoderTimedOut(GeopyError):
        pass

    class GeocoderUnavailable(GeopyError):
        pass

# Retângulo de Belo Horizonte (min_lat, max_lat, min_lon, max_lon). Respostas fora
# dele (ruas homônimas em outras cidades) são descartadas.
BBOX_BH = (-20.06, -19.77, -44.07, -43.85)
CENTRO_BH = (-19.916681, -43.934493)
INTERVALO_NOMINATIM_S = 1.1  # política de uso do Nominatim: no máximo 1 req/s
TENTATIVAS_POR_CONSULTA = 3
# Caminhos relativos à raiz do projeto, e não à pasta de onde o app foi chamado.
RAIZ = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_RESTAURANTES = os.path.join(RAIZ, "dados", "bares.csv")
ARQUIVO_CACHE_GEO = os.path.join(RAIZ, "cache", "geocodificacao.json")
ARQUIVO_CENTROS = os.path.join(RAIZ, "dados", "centros_demanda.csv")

# Desvio padrão da distribuição normal em torno de cada centro, em graus:
# 0,015 grau = ~1,67 km em latitude e ~1,57 km em longitude na latitude de BH.
# Cerca de 68% dos entregadores de um centro ficam a até ~1,6 km dele em cada eixo.
DESVIO_PADRAO_GRAUS = 0.015


def dentro_de_bh(lat, lon):
    min_lat, max_lat, min_lon, max_lon = BBOX_BH
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


@dataclass
class Coordenada:
    lat: float
    lon: float
    precisao: str  # enderecos.EXATO, RUA ou BAIRRO

    @property
    def aproximada(self):
        return self.precisao != enderecos.EXATO

    def como_tupla(self):
        return (self.lat, self.lon)


def dividir_entre_centros(n, quantidade_centros):
    """Quantos entregadores cada centro recebe: soma n e difere no máximo em 1."""
    base, resto = divmod(n, quantidade_centros)
    return [base + (1 if i < resto else 0) for i in range(quantidade_centros)]


def carregar_centros(caminho):
    """Lê o CSV de centros e devolve [(lat, lon), ...]; lista vazia se não der."""
    try:
        tabela = pd.read_csv(caminho)
        return list(zip(tabela["lat"].astype(float), tabela["lon"].astype(float)))
    except (OSError, ValueError, KeyError, pd.errors.EmptyDataError):
        return []


class ServicoIndisponivel(Exception):
    """O geocodificador falhou em todas as tentativas (rede fora do ar, bloqueio)."""


class SimuladorFrota:
    def __init__(self, caminho_csv=ARQUIVO_RESTAURANTES, geolocator=None,
                 arquivo_cache=ARQUIVO_CACHE_GEO, dormir=time.sleep, agora=time.monotonic):
        self.caminho_csv = caminho_csv
        self.restaurantes = pd.DataFrame()
        self.centros_demanda = []
        if geolocator is None:
            from geopy.geocoders import Nominatim
            geolocator = Nominatim(user_agent="tp1_algoritmos_ufmg_v2")
        self.geolocator = geolocator
        self.arquivo_cache = arquivo_cache
        self.cache_coordenadas = self._ler_cache()
        self.ultimo_erro_geo = None  # texto do último erro de rede/serviço, para a interface
        self._dormir, self._agora = dormir, agora
        self._ultima_requisicao = None
        if caminho_csv:
            self.carregar_dados()

    def carregar_dados(self):
        try:
            self.restaurantes = pd.read_csv(self.caminho_csv, encoding='utf-8', sep=',', on_bad_lines='skip')
            self.restaurantes = self.restaurantes.dropna(subset=['NOME_LOGRADOURO', 'NOME'])
        except Exception as e:
            print(f"Erro ao carregar o CSV: {e}")

    # ---------------------------------------------------------------- cache
    def _ler_cache(self):
        if not self.arquivo_cache or not os.path.exists(self.arquivo_cache):
            return {}
        try:
            with open(self.arquivo_cache, encoding="utf-8") as f:
                return {chave: Coordenada(**dados) for chave, dados in json.load(f).items()}
        except (OSError, ValueError, TypeError):
            return {}

    def _gravar_cache(self):
        if not self.arquivo_cache:
            return
        try:
            os.makedirs(os.path.dirname(self.arquivo_cache) or ".", exist_ok=True)
            with open(self.arquivo_cache, "w", encoding="utf-8") as f:
                json.dump({k: vars(c) for k, c in self.cache_coordenadas.items()}, f)
        except OSError:
            pass  # cache é só otimização

    # --------------------------------------------------------- geocodificação
    def _aguardar_intervalo(self):
        if self._ultima_requisicao is not None:
            falta = INTERVALO_NOMINATIM_S - (self._agora() - self._ultima_requisicao)
            if falta > 0:
                self._dormir(falta)
        self._ultima_requisicao = self._agora()

    def _consultar(self, consulta):
        """
        Uma consulta ao Nominatim, respeitando 1 req/s e repetindo em falhas
        transitórias (timeout, serviço fora do ar, excesso de pedidos).
        Retorna o resultado do geopy, ou None se o endereço não existe.
        Levanta ServicoIndisponivel quando esgota as tentativas por falha de serviço.
        """
        for tentativa in range(TENTATIVAS_POR_CONSULTA):
            self._aguardar_intervalo()
            try:
                local = self.geolocator.geocode(consulta, timeout=5)
                self.ultimo_erro_geo = None
                return local
            except (GeocoderTimedOut, GeocoderUnavailable) as e:
                self.ultimo_erro_geo = f"Nominatim indisponível ({type(e).__name__})."
                self._dormir(2 ** tentativa)
            except GeopyError as e:  # inclui 429 (excesso de pedidos) e erros de serviço
                self.ultimo_erro_geo = f"Erro do serviço de geocodificação: {e}"
                espera = getattr(e, "retry_after", None) or 5 * (tentativa + 1)
                self._dormir(espera)
        raise ServicoIndisponivel(self.ultimo_erro_geo)

    def _geocodificar_tentativas(self, tentativas, chave_cache=None):
        if chave_cache is not None and chave_cache in self.cache_coordenadas:
            return self.cache_coordenadas[chave_cache]
        for consulta, precisao in tentativas:
            try:
                local = self._consultar(consulta)
            except ServicoIndisponivel:
                return None  # o serviço caiu: insistir nas demais consultas só atrasaria
            if local and dentro_de_bh(local.latitude, local.longitude):
                resultado = Coordenada(local.latitude, local.longitude, precisao)
                if chave_cache is not None:
                    self.cache_coordenadas[chave_cache] = resultado
                    self._gravar_cache()
                return resultado
        return None

    def geocodificar(self, linha, idx_linha=None):
        """Coordenada (com a precisão obtida) de um restaurante do CSV, ou None."""
        chave = None if idx_linha is None else f"restaurante:{idx_linha}"
        return self._geocodificar_tentativas(enderecos.montar_tentativas(linha), chave)

    def geocodificar_texto(self, texto):
        """Coordenada de um endereço digitado livremente (restrito a BH)."""
        texto = " ".join(str(texto).split())
        if not texto:
            return None
        consulta = f"{texto}, Belo Horizonte, MG, Brasil"
        return self._geocodificar_tentativas([(consulta, enderecos.EXATO)], f"texto:{texto.lower()}")

    def geocodificar_endereco(self, linha, idx_linha=None):
        """Compatível com a versão anterior: tupla (lat, lon) ou None."""
        resultado = self.geocodificar(linha, idx_linha)
        return resultado.como_tupla() if resultado else None

    def preparar_centros_demanda(self, arquivo_centros=ARQUIVO_CENTROS):
        """
        Carrega os centros de demanda de um CSV (nome, lat, lon) já geocodificado,
        espalhado pelas regionais de BH. Sem o arquivo, usa só o centro da cidade.
        """
        self.centros_demanda = carregar_centros(arquivo_centros)
        if not self.centros_demanda:
            print(f"[Simulador] Aviso: {arquivo_centros} ausente ou vazio; usando só o centro de BH.")
            self.centros_demanda = [CENTRO_BH]

    def gerar_entregadores(self, n, geometria_rotas, rng=None):
        """
        Gera n entregadores: divide n igualmente entre os centros de demanda e, em
        torno de cada um, sorteia posições com distribuição normal (desvio padrão
        DESVIO_PADRAO_GRAUS em latitude e em longitude). Depois leva cada ponto à
        rua mais próxima. `rng` (numpy Generator) permite repetir uma geração.
        """
        if not self.centros_demanda:
            self.preparar_centros_demanda()
        rng = rng if rng is not None else np.random.default_rng()

        quantidades = dividir_entre_centros(n, len(self.centros_demanda))
        todas_lats, todas_lons = [], []
        for (lat_centro, lon_centro), qtd in zip(self.centros_demanda, quantidades):
            todas_lats.extend(rng.normal(lat_centro, DESVIO_PADRAO_GRAUS, qtd))
            todas_lons.extend(rng.normal(lon_centro, DESVIO_PADRAO_GRAUS, qtd))

        lats_reais, lons_reais = geometria_rotas.projetar_multiplos_na_rua(todas_lats, todas_lons)

        return [
            {'id': f"E{id_atual:04d}", 'lat': float(lat_r), 'lon': float(lon_r)}
            for id_atual, (lat_r, lon_r) in enumerate(zip(lats_reais, lons_reais), start=1)
        ]
