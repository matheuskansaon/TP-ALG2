# TP1 - ALG2: Indexação Geoespacial e Geometria Computacional Híbrida

**Universidade Federal de Minas Gerais (UFMG)**  
**Departamento de Ciência da Computação - DCC207 (Algoritmos 2)**  

**Integrantes do Grupo:**
- João Vitor Vieira Neves (Matrícula: 2023028633)
- Matheus Costa Melo Silva (Matrícula: 2023087826)
- Matheus Pimentel Kansaon (Matrícula: 2022111561)

---

## 📍 Sobre o Projeto
Este repositório contém a implementação de um motor de busca e monitoramento geoespacial híbrido para visualização e consulta de uma frota de entregadores operando na cidade de Belo Horizonte.

O sistema realiza a indexação espacial de coordenadas convertendo latitude e longitude em strings **Geohash** (Base32, 8 níveis de precisão) por intercalação binária de intervalos, armazenando-as em uma **Árvore Trie Compacta (Radix Tree / Patrícia)** implementada do zero. Nas consultas, o motor recupera os candidatos das células que cobrem o círculo do raio de atendimento em tempo $O(m+k)$, refina os resultados exatamente pela distância geodésica de **Haversine** e plota a frota e as células consultadas em um mapa interativo.

## ⚙️ Funcionalidades e Arquitetura
- **Codificação Geohash e Cobertura de Borda (`geohash.py`):** Intercalação binária em 8 níveis (Base32), cálculo dos 8 vizinhos e determinação das células Geohash que cobrem qualquer círculo de raio $R$ sem perda de pontos nas fronteiras.
- **Árvore Trie Compacta (`trie.py`):** Implementação autoral com compressão de caminhos unários em arestas rotuladas por substrings (`prefixo`), garantindo complexidade $O(m+k)$ e redução do número de nós internos.
- **Simulador de Demanda Realista (`simulador.py` e `dados/centros_demanda.csv`):** Geração sintética de $N$ entregadores distribuídos equitativamente entre 22 centros de demanda distribuídos pelas regionais de Belo Horizonte seguindo uma distribuição normal ($\sigma = 0{,}015^\circ$).
- **Restrição Viária por Projeção Ortogonal (`geometria.py`):** Localiza de forma vetorizada a aresta viária mais próxima (`osmnx.distance.nearest_edges`) e projeta ortogonalmente cada coordenada matemática sobre a polilinha real da rua.
- **Busca Textual e Geocodificação Resiliente (`enderecos.py` e `busca.py`):** Pesquisa instantânea sobre todos os estabelecimentos de `dados/bares.csv` (nome fantasia, razão social, logradouro e bairro) ou endereço livre, com cache persistente em `cache/geocodificacao.json`.
- **Interface Interativa (`app.py`):** Painel web em Dash + Leaflet com desenho do círculo do raio e das células Geohash consultadas, pinos destacados (vermelho) e descartados (cinza), tabela ordenada por distância/tempo e painel de métricas resumo com runtime em milissegundos.

## 🚀 Pré-requisitos e Instalação
Certifique-se de ter o **Python 3.9+** instalado (compatível com Linux, Windows e macOS).

```bash
# 1. Crie e ative um ambiente virtual (opcional, mas recomendado)
python3 -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate

# 2. Instale as dependências
pip install -r requirements.txt
```

## 💻 Instruções de Execução (Comando Único)
Basta executar um único comando na raiz do repositório:

```bash
python app.py
```

1. **Download Automático da Malha Viária:** Na primeira execução, caso `dados/malha_bh.graphml` ainda não exista no disco, o sistema baixará automaticamente a malha viária de Belo Horizonte via Overpass API (levando cerca de 1 a 2 minutos) e a salvará em `dados/malha_bh.graphml`. Nas execuções seguintes, o carregamento do disco leva apenas alguns segundos.
2. Acesse o painel interativo no navegador em: **`http://127.0.0.1:8050/`**

*(Opcional)* Caso deseje baixar ou atualizar a malha viária separadamente via linha de comando:
```bash
python scripts/baixar_malha.py
```

## 🧪 Testes Automatizados e Benchmark Experimental
Para executar a suíte de testes unitários (Geohash, Trie Compacta, Busca por Raio vs. Busca Linear, Projeção Geométrica, Simulador e Endereços):

```bash
python -m unittest discover -s tests -v
```

Para executar o benchmark experimental comparando o tempo de resposta da **Trie Compacta + Haversine** contra a **Busca Linear $O(N)$**:

```bash
python scripts/benchmark.py
```
