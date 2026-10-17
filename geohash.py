# geohash.py
# Implementação própria do algoritmo de codificação Geohash e cálculo de vizinhança.

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
    Retorna uma lista com os 8 geohashes vizinhos da célula fornecida.
    Resolve o problema de borda calculando coordenadas levemente além dos limites.
    """
    min_lat, max_lat, min_lon, max_lon = decodificar_bbox(geohash)
    
    centro_lat = (min_lat + max_lat) / 2.0
    centro_lon = (min_lon + max_lon) / 2.0
    
    delta_lat = max_lat - min_lat
    delta_lon = max_lon - min_lon
    
    precisao = len(geohash)
    
    adjacentes = [
        codificar(centro_lat + delta_lat, centro_lon, precisao),               # Norte
        codificar(centro_lat - delta_lat, centro_lon, precisao),               # Sul
        codificar(centro_lat, centro_lon + delta_lon, precisao),               # Leste
        codificar(centro_lat, centro_lon - delta_lon, precisao),               # Oeste
        codificar(centro_lat + delta_lat, centro_lon + delta_lon, precisao),   # Nordeste
        codificar(centro_lat + delta_lat, centro_lon - delta_lon, precisao),   # Noroeste
        codificar(centro_lat - delta_lat, centro_lon + delta_lon, precisao),   # Sudeste
        codificar(centro_lat - delta_lat, centro_lon - delta_lon, precisao)    # Sudoeste
    ]
    
    # Retorna valores únicos removendo o próprio geohash central (caso ocorra na precisão máxima)
    return list(set(adjacentes) - {geohash})