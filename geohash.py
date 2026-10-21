# geohash.py
# Implementação própria do algoritmo de codificação Geohash e cálculo de vizinhança.

import math

BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

def codificar(lat, lon, precisao=8):
    """
    Converte latitude e longitude em uma string Geohash intercalando os bits.
    A latitude deve estar em [-90, 90] e a longitude em [-180, 180].
    """
    lat_intervalo = [-90.0, 90.0]
    lon_intervalo = [-180.0, 180.0]
    geohash = []
    bits = []
    
    # Intercalação binária: começa com a longitude
    is_lon = True
    
    while len(geohash) < precisao:
        if is_lon:
            meio = (lon_intervalo[0] + lon_intervalo[1]) / 2.0
            if lon >= meio:
                bits.append(1)
                lon_intervalo[0] = meio
            else:
                bits.append(0)
                lon_intervalo[1] = meio
        else:
            meio = (lat_intervalo[0] + lat_intervalo[1]) / 2.0
            if lat >= meio:
                bits.append(1)
                lat_intervalo[0] = meio
            else:
                bits.append(0)
                lat_intervalo[1] = meio
        
        is_lon = not is_lon
        
        # Quando agruparmos 5 bits, convertemos para 1 caractere na Base32
        if len(bits) == 5:
            idx = 0
            for bit in bits:
                idx = (idx << 1) | bit
            geohash.append(BASE32[idx])
            bits = []
            
    return "".join(geohash)

def decodificar_bbox(geohash):
    """
    Decodifica um geohash, retornando os limites do retângulo (min_lat, max_lat, min_lon, max_lon).
    """
    lat_intervalo = [-90.0, 90.0]
    lon_intervalo = [-180.0, 180.0]
    is_lon = True
    
    for char in geohash:
        idx = BASE32.find(char)
        # Lê os 5 bits do caractere
        for i in range(4, -1, -1):
            bit = (idx >> i) & 1
            if is_lon:
                meio = (lon_intervalo[0] + lon_intervalo[1]) / 2.0
                if bit == 1:
                    lon_intervalo[0] = meio
                else:
                    lon_intervalo[1] = meio
            else:
                meio = (lat_intervalo[0] + lat_intervalo[1]) / 2.0
                if bit == 1:
                    lat_intervalo[0] = meio
                else:
                    lat_intervalo[1] = meio
            is_lon = not is_lon
            
    return lat_intervalo[0], lat_intervalo[1], lon_intervalo[0], lon_intervalo[1]

def obter_vizinhos(geohash):
    """
    Retorna a lista com os (até) 8 geohashes vizinhos da célula fornecida.
    Resolve o problema de borda calculando o centro de cada célula adjacente, o que
    funciona mesmo quando o vizinho tem um prefixo totalmente diferente (ex.: dois
    pontos de lados opostos da longitude -45 diferem já no 1º caractere).
    Células além dos polos são omitidas; a longitude dá a volta em +-180.
    """
    min_lat, max_lat, min_lon, max_lon = decodificar_bbox(geohash)

    centro_lat = (min_lat + max_lat) / 2.0
    centro_lon = (min_lon + max_lon) / 2.0
    delta_lat = max_lat - min_lat
    delta_lon = max_lon - min_lon
    precisao = len(geohash)

    adjacentes = set()
    for passo_lat in (-1, 0, 1):
        for passo_lon in (-1, 0, 1):
            if passo_lat == 0 and passo_lon == 0:
                continue
            lat = centro_lat + passo_lat * delta_lat
            if not -90.0 <= lat < 90.0:
                continue
            lon = (centro_lon + passo_lon * delta_lon + 180.0) % 360.0 - 180.0
            adjacentes.add(codificar(lat, lon, precisao))

    adjacentes.discard(geohash)  # numa célula que ocupa o globo todo na longitude
    return sorted(adjacentes)


def dimensoes_celula(precisao):
    """Altura e largura, em graus, de uma célula geohash da precisão dada."""
    bits = 5 * precisao
    return 180.0 / 2 ** (bits // 2), 360.0 / 2 ** (bits - bits // 2)


def dimensoes_celula_km(precisao, lat):
    """(altura_km, largura_km) de uma célula na latitude dada (a largura encolhe com cos(lat))."""
    altura, largura = dimensoes_celula(precisao)
    return altura * KM_POR_GRAU, largura * KM_POR_GRAU * math.cos(math.radians(lat))


KM_POR_GRAU = 111.195
MAX_CELULAS_BUSCA = 64


def cobrir_circulo(lat, lon, raio_km, max_celulas=MAX_CELULAS_BUSCA, precisao_maxima=8):
    """
    Células geohash que cobrem o círculo de centro (lat, lon) e raio raio_km.

    Escolhe a MAIOR precisão (células menores, janela mais justa) cujo retângulo
    envolvente do círculo cabe em no máximo max_celulas células, e devolve todas
    as células que tocam esse retângulo: (lista_de_geohashes, precisao).
    É a generalização do "célula central + 8 vizinhas": quando as células são
    maiores que o círculo, o resultado é no máximo um bloco 3x3.
    """
    d = raio_km / 6371.0  # raio angular
    meia_altura = math.degrees(d)
    cos_lat = math.cos(math.radians(lat))
    # semilargura exata em longitude de um círculo geodésico (>= d / cos(lat))
    meia_largura = math.degrees(math.asin(min(1.0, math.sin(d) / cos_lat))) if cos_lat > math.sin(d) else 180.0

    # margem de ~10 cm: um ponto exatamente na circunferência não cai fora por arredondamento
    margem = 1e-6
    sul = max(-90.0, lat - meia_altura - margem)
    norte = min(90.0 - 1e-9, lat + meia_altura + margem)
    oeste = lon - meia_largura - margem
    leste = lon + meia_largura + margem

    for precisao in range(precisao_maxima, 0, -1):
        altura, largura = dimensoes_celula(precisao)
        linha_ini, linha_fim = int((sul + 90.0) // altura), int((norte + 90.0) // altura)
        col_ini, col_fim = int((oeste + 180.0) // largura), int((leste + 180.0) // largura)
        total = (linha_fim - linha_ini + 1) * (col_fim - col_ini + 1)
        if total <= max_celulas or precisao == 1:
            n_colunas = int(round(360.0 / largura))
            celulas = []
            for i in range(linha_ini, linha_fim + 1):
                for j in range(col_ini, col_fim + 1):
                    lat_c = -90.0 + (i + 0.5) * altura
                    lon_c = -180.0 + ((j % n_colunas) + 0.5) * largura
                    celulas.append(codificar(lat_c, lon_c, precisao))
            return list(dict.fromkeys(celulas)), precisao
