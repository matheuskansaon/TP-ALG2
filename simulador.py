# simulador.py
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

class SimuladorFrota:
    def __init__(self, caminho_csv="dados/bares.csv"):
        self.caminho_csv = caminho_csv
        self.restaurantes = pd.DataFrame()
        self.centros_demanda = [] 
        self.geolocator = Nominatim(user_agent="tp1_algoritmos_ufmg_v2")
        self.cache_coordenadas = {}  # Memória temporária para acelerar a busca
        self.carregar_dados()

    def carregar_dados(self):
        try:
            self.restaurantes = pd.read_csv(self.caminho_csv, encoding='utf-8', sep=',', on_bad_lines='skip')
            self.restaurantes = self.restaurantes.dropna(subset=['NOME_LOGRADOURO', 'NOME'])
        except Exception as e:
            print(f"Erro ao carregar o CSV: {e}")

    def geocodificar_endereco(self, linha, idx_linha=None):
        if idx_linha is not None and idx_linha in self.cache_coordenadas:
            return self.cache_coordenadas[idx_linha]

        tipo = linha.get('DESC_LOGRADOURO', '')
        rua = linha.get('NOME_LOGRADOURO', '')
        numero = linha.get('NUMERO_IMOVEL', '')
        bairro = linha.get('NOME_BAIRRO', '')
        
        # Cria uma lista de tentativas, do mais exato para o mais abrangente
        tentativas = [
            f"{tipo} {rua}, {numero}, {bairro}, Belo Horizonte, MG, Brasil",
            f"{tipo} {rua}, {bairro}, Belo Horizonte, MG, Brasil",
            f"{rua}, Belo Horizonte, MG, Brasil",
            f"{bairro}, Belo Horizonte, MG, Brasil"
        ]
        
        for endereco_str in tentativas:
            try:
                local = self.geolocator.geocode(endereco_str, timeout=3)
                if local:
                    coords = (local.latitude, local.longitude)
                    if idx_linha is not None:
                        self.cache_coordenadas[idx_linha] = coords
                    return coords
            except GeocoderTimedOut:
                continue
                
        return None

    def preparar_centros_demanda(self, quantidade_centros=5):
        self.centros_demanda = []
        # Garante que a frota será gerada em volta dos PRIMEIROS restaurantes do menu
        amostra = self.restaurantes.head(quantidade_centros)
        
        for idx, linha in amostra.iterrows():
            coords = self.geocodificar_endereco(linha, idx)
            if coords:
                self.centros_demanda.append(coords)
                
        if not self.centros_demanda:
            self.centros_demanda.append((-19.916681, -43.934493))

    def gerar_entregadores(self, n, geometria_rotas):
        entregadores = []
        if not self.centros_demanda:
            self.preparar_centros_demanda()
            
        por_centro = n // len(self.centros_demanda)
        resto = n % len(self.centros_demanda)
        desvio_padrao = 0.015 

        todas_lats = []
        todas_lons = []

        for i, centro in enumerate(self.centros_demanda):
            qtd = por_centro + (1 if i < resto else 0)
            lat_centro, lon_centro = centro
            
            todas_lats.extend(np.random.normal(lat_centro, desvio_padrao, qtd))
            todas_lons.extend(np.random.normal(lon_centro, desvio_padrao, qtd))
            
        # Chamada vetorizada: projeta todos os pontos em milissegundos
        lats_reais, lons_reais = geometria_rotas.projetar_multiplos_na_rua(todas_lats, todas_lons)
        
        for id_atual, (lat_r, lon_r) in enumerate(zip(lats_reais, lons_reais), start=1):
            entregadores.append({
                'id': f"E{id_atual:04d}",
                'lat': lat_r,
                'lon': lon_r
            })
            
        return entregadores