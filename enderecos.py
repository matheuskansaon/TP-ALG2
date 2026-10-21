# Tratamento de texto de endereços: abreviações do CSV, consultas de geocodificação
# e busca de restaurantes. Só usa a biblioteca padrão (testável sem rede).
import re
import unicodedata

# Tipos de logradouro abreviados no bares.csv (coluna DESC_LOGRADOURO).
# "VDP" aparece uma única vez e não tem expansão segura, então fica como está.
ABREVIACOES_TIPO = {
    "AVE": "AVENIDA",
    "PCA": "PRACA",
    "ROD": "RODOVIA",
    "BEC": "BECO",
    "ALA": "ALAMEDA",
    "EST": "ESTRADA",
    "TRV": "TRAVESSA",
}

# Níveis de precisão de uma geocodificação, do melhor para o pior.
EXATO, RUA, BAIRRO = "exato", "rua", "bairro"


def _texto(valor):
    """Converte célula do pandas em texto limpo ('' para NaN/None)."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    return "" if texto.lower() in ("nan", "none") else texto


def _numero(valor):
    """Número do imóvel como texto, ou '' se vazio, zero ou 'S/N'."""
    texto = _texto(valor)
    if texto.endswith(".0"):
        texto = texto[:-2]
    return "" if texto in ("", "0") or texto.upper().replace(" ", "") in ("S/N", "SN") else texto


def normalizar(texto):
    """Maiúsculas, sem acentos e com espaços colapsados (para comparar e buscar)."""
    sem_acento = unicodedata.normalize("NFKD", _texto(texto)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento.upper()).strip()


def expandir_tipo(abreviacao):
    """'AVE' -> 'AVENIDA'. Tipos desconhecidos (ou RUA, VIA) voltam inalterados."""
    tipo = _texto(abreviacao).upper()
    return ABREVIACOES_TIPO.get(tipo, tipo)


def montar_tentativas(linha):
    """
    Consultas de geocodificação, da mais exata para a mais vaga, cada uma com o
    nível de precisão que a resposta representa: [(texto, precisao), ...].
    """
    tipo = expandir_tipo(linha.get("DESC_LOGRADOURO", ""))
    rua = _texto(linha.get("NOME_LOGRADOURO", ""))
    numero = _numero(linha.get("NUMERO_IMOVEL", ""))
    bairro = _texto(linha.get("NOME_BAIRRO", ""))
    cidade = "Belo Horizonte, MG, Brasil"

    via = f"{tipo} {rua}".strip()
    tentativas = []
    if via and numero:
        tentativas.append((", ".join(p for p in (f"{via}, {numero}", bairro, cidade) if p), EXATO))
    if via:
        tentativas.append((", ".join(p for p in (via, bairro, cidade) if p), RUA))
        tentativas.append((f"{rua}, {cidade}" if rua else f"{via}, {cidade}", RUA))
    if bairro:
        tentativas.append((f"{bairro}, {cidade}", BAIRRO))

    vistas, unicas = set(), []
    for consulta, precisao in tentativas:
        if consulta not in vistas:
            vistas.add(consulta)
            unicas.append((consulta, precisao))
    return unicas


def rotulo_restaurante(linha):
    """Texto do menu: nome fantasia (ou razão social) e endereço."""
    fantasia = _texto(linha.get("NOME_FANTASIA", ""))
    nome = fantasia or _texto(linha.get("NOME", "")) or "Sem nome"
    tipo = _texto(linha.get("DESC_LOGRADOURO", ""))
    rua = _texto(linha.get("NOME_LOGRADOURO", ""))
    numero = _numero(linha.get("NUMERO_IMOVEL", ""))
    bairro = _texto(linha.get("NOME_BAIRRO", ""))
    endereco = f"{tipo} {rua}".strip() + (f", {numero}" if numero else "")
    return f"{nome} — {endereco} · {bairro}" if bairro else f"{nome} — {endereco}"


def indice_de_busca(restaurantes):
    """
    Pré-calcula (uma vez) o texto normalizado de cada restaurante:
    [(indice_do_dataframe, parte_nome, texto_completo), ...].
    """
    indice = []
    for idx, linha in restaurantes.iterrows():
        parte_nome = normalizar(f"{_texto(linha.get('NOME_FANTASIA', ''))} {_texto(linha.get('NOME', ''))}")
        endereco = normalizar(
            f"{expandir_tipo(linha.get('DESC_LOGRADOURO', ''))} {_texto(linha.get('NOME_LOGRADOURO', ''))} "
            f"{_numero(linha.get('NUMERO_IMOVEL', ''))} {_texto(linha.get('NOME_BAIRRO', ''))}"
        )
        indice.append((idx, parte_nome, f"{parte_nome} {endereco}"))
    return indice


def buscar_restaurantes(indice, termo, limite=50):
    """
    Busca por nome fantasia, razão social ou endereço (rua, número, bairro).
    Todas as palavras do termo precisam aparecer; quem casa mais palavras no
    nome vem primeiro. Retorna até `limite` índices do dataframe.
    """
    palavras = normalizar(termo).split()
    if not palavras:
        return []
    achados = []
    for idx, parte_nome, completo in indice:
        if all(p in completo for p in palavras):
            no_nome = sum(1 for p in palavras if p in parte_nome)
            achados.append((-no_nome, len(completo), idx))
    achados.sort()
    return [idx for _, _, idx in achados[:limite]]
