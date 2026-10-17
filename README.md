# TP1 - ALG2

**Universidade Federal de Minas Gerais (UFMG)**  
**Departamento de Ciência da Computação - Algoritmos 2**  

**Integrantes do Grupo:**
- João Vitor Vieira Neves (Matrícula: 2023028633)
- Matheus Costa Melo Silva (Matrícula: 2023087826)
- Matheus Pimentel Kansaon (Matrícula: 2022111561)

---

## 📍 Sobre o Projeto
Este repositório contém a implementação de um motor de busca e monitoramento geoespacial híbrido para visualização e consulta de uma frota de entregadores operando na cidade de Belo Horizonte. 

O sistema realiza a indexação de coordenadas através da conversão para strings Geohash (Base32, 8 níveis) e armazena os dados em uma árvore Trie implementada do zero. A partir disso, o motor filtra entregadores dentro de um raio de atendimento específico utilizando a fórmula de Haversine e plota os resultados em um mapa interativo.

## ⚙️ Funcionalidades e Requisitos Atendidos
- **Indexação por Geohash e Trie:** Busca instantânea de prefixos em tempo $O(m+k)$ e tratamento do problema de borda verificando células adjacentes.
- **Simulador de Frota:** Geração sintética de $N$ entregadores baseada em distribuição normal centrada nos restaurantes.
- **Realismo Geográfico (Restrição Viária):** Correção das coordenadas matemáticas geradas projetando os entregadores para as vias transitáveis do OpenStreetMap via biblioteca `osmnx`.
- **Interface Gráfica Interativa:** Desenvolvida em Dash/Python, atualiza dinamicamente os marcadores do mapa (destacados e descartados) e exibe tabelas com ID, distância e tempo.

## 🚀 Pré-requisitos e Dependências
O sistema foi desenvolvido em Python e utiliza bibliotecas específicas para visualização e processamento viário. Certifique-se de ter o Python 3.8 ou superior instalado.

Instale as dependências executando:
`pip install -r requirements.txt`

## 💻 Instruções de Execução
1. Certifique-se de que o arquivo de dados original (`bares.csv`) esteja localizado dentro da pasta `dados/`.
2. Abra o terminal na raiz do projeto e execute a aplicação:
`python app.py`
3. **Atenção:** A primeira execução poderá demorar alguns minutos, pois o sistema fará o download da malha viária completa de Belo Horizonte. O grafo será salvo no disco para carregamento imediato nas execuções subsequentes.
4. Acesse o painel interativo no seu navegador através do endereço: `http://127.0.0.1:8050/`
