# app.py
import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from geohash import codificar, obter_vizinhos
from trie import ArvoreTrie
from simulador import SimuladorFrota
from geometria import GeometriaRotas, calcular_distancia_haversine

motor_trie = ArvoreTrie()
simulador = SimuladorFrota("dados/bares.csv")
geo_rotas = GeometriaRotas()

opcoes_restaurantes = []
if not simulador.restaurantes.empty:
    amostra_ui = simulador.restaurantes.head(500)
    for index, row in amostra_ui.iterrows():
        nome = row.get('NOME', 'Desconhecido')
        rua = row.get('NOME_LOGRADOURO', '')
        num = row.get('NUMERO_IMOVEL', '')
        bairro = row.get('NOME_BAIRRO', '')
        texto = f"{nome} ({rua}, {num} - {bairro})"
        opcoes_restaurantes.append({'label': texto, 'value': index})

# Inicializa o app com um tema moderno do Bootstrap
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])

app.layout = dbc.Container([
    dbc.Row(
        dbc.Col(html.H2("Monitoramento Geoespacial de Frotas", className="text-center my-4 fw-bold text-primary"))
    ),

    dbc.Row([
        # Coluna da Esquerda: Painel de Controles
        dbc.Col([
            # Painel 1: Simulação
            dbc.Card([
                dbc.CardHeader(html.H5("1. Simulação da Frota", className="mb-0 fw-bold")),
                dbc.CardBody([
                    dbc.Label("Quantidade de entregadores (N):", className="fw-semibold"),
                    # dbc.Input substitui o dcc.Input e corrige o bug nativo de renderização
                    dbc.Input(id='input-n', type='number', value=100, min=1, step=1, className="mb-3"),
                    dbc.Button('Gerar Entregadores', id='btn-gerar', color="success", className="w-100 fw-bold"),
                    html.Div(id='msg-geracao', className="mt-3 text-success fw-bold text-center")
                ])
            ], className="mb-4 shadow-sm border-0"),

            # Painel 2: Filtros
            dbc.Card([
                dbc.CardHeader(html.H5("2. Consulta e Filtros", className="mb-0 fw-bold")),
                dbc.CardBody([
                    dbc.Label("Restaurante / Ponto de Coleta:", className="fw-semibold"),
                    dcc.Dropdown(
                        id='dropdown-restaurante', 
                        options=opcoes_restaurantes, 
                        placeholder="Selecione um restaurante...",
                        className="mb-4"
                    ),
                    dbc.Label("Raio de Atendimento (km):", className="fw-semibold"),
                    dcc.Slider(
                        id='slider-raio', min=0.5, max=10.0, step=0.5, value=2.0, 
                        marks={i: f"{i}" for i in range(1, 11)},
                        className="mb-4"
                    ),
                    dbc.Button('Buscar Entregadores', id='btn-buscar', color="primary", className="w-100 fw-bold")
                ])
            ], className="shadow-sm border-0")
        ], md=4), # Ocupa 4 de 12 colunas no grid

        # Coluna da Direita: Visualização de Dados
        dbc.Col([
            # Painel do Mapa
            dbc.Card([
                dbc.CardBody([
                    dl.Map(id='mapa-interativo', center=[-19.916681, -43.934493], zoom=13, 
                           style={'width': '100%', 'height': '55vh', 'borderRadius': '8px'}, children=[
                        dl.TileLayer(),
                        dl.LayerGroup(id='camada-marcadores')
                    ])
                ], className="p-2")
            ], className="mb-4 shadow-sm border-0"),

            # Painel da Tabela
            dbc.Card([
                dbc.CardHeader(html.H5("Entregadores Disponíveis", className="mb-0 fw-bold")),
                dbc.CardBody([
                    dash_table.DataTable(
                        id='tabela-resultados',
                        columns=[
                            {'name': 'ID Entregador', 'id': 'id'},
                            {'name': 'Distância (km)', 'id': 'distancia'},
                            {'name': 'Tempo Estimado (min)', 'id': 'tempo'}
                        ],
                        style_table={'overflowX': 'auto'},
                        style_cell={'textAlign': 'center', 'fontFamily': 'sans-serif', 'padding': '12px'},
                        style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
                        page_size=5 # Adiciona paginação para não estourar a tela verticalmente
                    )
                ])
            ], className="shadow-sm border-0")
        ], md=8) # Ocupa 8 de 12 colunas no grid
    ])
], fluid=True, className="bg-light pb-5")

@app.callback(
    Output('msg-geracao', 'children'),
    Input('btn-gerar', 'n_clicks'),
    State('input-n', 'value'),
    prevent_initial_call=True
)
def callback_gerar(n_clicks, n_entregadores):
    if not n_entregadores:
        return "Informe um número válido."
        
    motor_trie.limpar() 
    entregadores_gerados = simulador.gerar_entregadores(n_entregadores, geo_rotas)
    
    for ent in entregadores_gerados:
        hash_str = codificar(ent['lat'], ent['lon'], precisao=8)
        motor_trie.inserir(hash_str, ent)
        
    return f"Frota de {n_entregadores} entregadores gerada com sucesso."

@app.callback(
    Output('camada-marcadores', 'children'),
    Output('tabela-resultados', 'data'),
    Output('mapa-interativo', 'center'),
    Input('btn-buscar', 'n_clicks'),
    State('dropdown-restaurante', 'value'),
    State('slider-raio', 'value'),
    prevent_initial_call=True
)
def callback_buscar(n_clicks, restaurante_idx, raio_km):
    if restaurante_idx is None:
        return [], [], [-19.916681, -43.934493]
        
    linha = simulador.restaurantes.loc[restaurante_idx]
    coords_restaurante = simulador.geocodificar_endereco(linha, restaurante_idx)
    
    if not coords_restaurante:
        # Se a API de mapa falhar, preserva os entregadores já gerados
        todos_entregadores = motor_trie.buscar_prefixo("") 
        marcadores_preservados = []
        for ent in todos_entregadores:
            marcadores_preservados.append(dl.Marker(
                position=[ent['lat'], ent['lon']],
                icon=dict(iconUrl="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-grey.png", iconSize=[25, 41], iconAnchor=[12, 41]),
                children=[dl.Tooltip(ent['id'])]
            ))
        return marcadores_preservados, [], [-19.916681, -43.934493]
        
    lat_r, lon_r = coords_restaurante
    tamanho_prefixo = 6 if raio_km <= 3.0 else 5
    hash_restaurante = codificar(lat_r, lon_r, precisao=tamanho_prefixo)
    prefixos_busca = [hash_restaurante] + obter_vizinhos(hash_restaurante)
    
    candidatos_ids = set()
    candidatos_dados = []
    
    for prefixo in prefixos_busca:
        resultados_trie = motor_trie.buscar_prefixo(prefixo)
        for cand in resultados_trie:
            if cand['id'] not in candidatos_ids:
                candidatos_ids.add(cand['id'])
                candidatos_dados.append(cand)
                
    tabela_dados = []
    todos_entregadores = motor_trie.buscar_prefixo("") 
    
    marcadores = []
    marcadores.append(dl.Marker(position=[lat_r, lon_r], 
                                icon=dict(iconUrl="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png", iconSize=[25, 41], iconAnchor=[12, 41])))

    filtrados_ids = set()
    for ent in candidatos_dados:
        dist = calcular_distancia_haversine(lat_r, lon_r, ent['lat'], ent['lon'])
        if dist <= raio_km:
            filtrados_ids.add(ent['id'])
            tempo_min = round((dist / 30.0) * 60)
            tabela_dados.append({'id': ent['id'], 'distancia': round(dist, 2), 'tempo': tempo_min})
            
    for ent in todos_entregadores:
        icone_url = "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png" if ent['id'] in filtrados_ids else "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-grey.png"
        marcadores.append(dl.Marker(
            position=[ent['lat'], ent['lon']],
            icon=dict(iconUrl=icone_url, iconSize=[25, 41], iconAnchor=[12, 41]),
            children=[dl.Tooltip(ent['id'])]
        ))
        
    tabela_dados = sorted(tabela_dados, key=lambda k: k['distancia'])

    return marcadores, tabela_dados, [lat_r, lon_r]

if __name__ == '__main__':
    geo_rotas.carregar_grafo()
    app.run(debug=True, port=8050)