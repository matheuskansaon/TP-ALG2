# app.py
import time
import warnings
warnings.filterwarnings("ignore", module="urllib3")

import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from geohash import codificar, obter_vizinhos
from trie import ArvoreTrie
from simulador import SimuladorFrota
from geometria import GeometriaRotas, calcular_distancia_haversine

motor_trie = ArvoreTrie()
simulador = SimuladorFrota("dados/bares.csv")
geo_rotas = GeometriaRotas()

ICONE_VERMELHO = dict(
    iconUrl="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png",
    iconSize=[25, 41],
    iconAnchor=[12, 41]
)
ICONE_CINZA = dict(
    iconUrl="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-grey.png",
    iconSize=[25, 41],
    iconAnchor=[12, 41]
)
ICONE_AZUL = dict(
    iconUrl="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png",
    iconSize=[25, 41],
    iconAnchor=[12, 41]
)

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

            # Painel da Tabela e Métricas Resumo
            dbc.Card([
                dbc.CardHeader(html.H5("Entregadores Disponíveis e Métricas Resumo", className="mb-0 fw-bold")),
                dbc.CardBody([
                    html.Div(id='metricas-resumo', className="mb-3"),
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


def _criar_painel_metricas(total_filtrados, total_frota, menor_dist, media_dist, tempo_medio, runtime_ms):
    return dbc.Row([
        dbc.Col(dbc.Alert([html.Small("No Raio / Frota", className="d-block text-muted"), html.Strong(f"{total_filtrados} / {total_frota}")], color="light", className="p-2 mb-0 text-center border"), width=3),
        dbc.Col(dbc.Alert([html.Small("Menor Distância", className="d-block text-muted"), html.Strong(f"{menor_dist} km" if menor_dist is not None else "-")], color="light", className="p-2 mb-0 text-center border"), width=3),
        dbc.Col(dbc.Alert([html.Small("Distância / Tempo Médio", className="d-block text-muted"), html.Strong(f"{media_dist} km ({tempo_medio} min)" if media_dist is not None else "-")], color="light", className="p-2 mb-0 text-center border"), width=3),
        dbc.Col(dbc.Alert([html.Small("Runtime da Busca", className="d-block text-muted"), html.Strong(f"{runtime_ms:.2f} ms")], color="light", className="p-2 mb-0 text-center border"), width=3),
    ], className="g-2")


@app.callback(
    Output('msg-geracao', 'children'),
    Output('camada-marcadores', 'children'),
    Output('tabela-resultados', 'data'),
    Output('mapa-interativo', 'center'),
    Output('metricas-resumo', 'children'),
    Input('btn-gerar', 'n_clicks'),
    Input('btn-buscar', 'n_clicks'),
    State('input-n', 'value'),
    State('dropdown-restaurante', 'value'),
    State('slider-raio', 'value'),
    State('msg-geracao', 'children'),
    prevent_initial_call=True
)
def callback_principal(n_gerar, n_buscar, n_entregadores, restaurante_idx, raio_km, msg_atual):
    acao = ctx.triggered_id

    # Ação 1: Gerar nova frota (descarta árvore anterior, limpa tabela e atualiza pinos no mapa)
    if acao == 'btn-gerar':
        if not n_entregadores or n_entregadores < 1:
            return "Informe um número válido.", dash.no_update, dash.no_update, dash.no_update, dash.no_update

        motor_trie.limpar()
        entregadores_gerados = simulador.gerar_entregadores(int(n_entregadores), geo_rotas)

        marcadores_novos = []
        for ent in entregadores_gerados:
            hash_str = codificar(ent['lat'], ent['lon'], precisao=8)
            motor_trie.inserir(hash_str, ent)
            marcadores_novos.append(dl.Marker(
                position=[ent['lat'], ent['lon']],
                icon=ICONE_CINZA,
                children=[dl.Tooltip(f"{ent['id']} (Geohash: {hash_str})")]
            ))

        centro_mapa = [-19.916681, -43.934493]
        if entregadores_gerados:
            centro_mapa = [entregadores_gerados[0]['lat'], entregadores_gerados[0]['lon']]

        msg = f"Frota de {n_entregadores} entregadores gerada com sucesso."
        resumo_inicial = dbc.Alert(
            f"Frota ativa: {len(entregadores_gerados)} entregadores indexados na Trie Compacta. Selecione um restaurante e clique em Buscar.",
            color="secondary", className="py-2 mb-0 text-center"
        )
        return msg, marcadores_novos, [], centro_mapa, resumo_inicial

    # Ação 2: Buscar entregadores próximos ao restaurante selecionado
    if restaurante_idx is None:
        return msg_atual, dash.no_update, [], [-19.916681, -43.934493], dbc.Alert("Selecione um restaurante para realizar a consulta.", color="warning", className="py-2 mb-0 text-center")

    linha = simulador.restaurantes.loc[restaurante_idx]
    coords_restaurante = simulador.geocodificar_endereco(linha, restaurante_idx)

    todos_entregadores = motor_trie.buscar_prefixo("")
    if not coords_restaurante:
        marcadores_preservados = [
            dl.Marker(
                position=[ent['lat'], ent['lon']],
                icon=ICONE_CINZA,
                children=[dl.Tooltip(ent['id'])]
            )
            for ent in todos_entregadores
        ]
        return msg_atual, marcadores_preservados, [], [-19.916681, -43.934493], dbc.Alert("Não foi possível geocodificar o endereço selecionado.", color="danger", className="py-2 mb-0 text-center")

    lat_r, lon_r = coords_restaurante

    # Medição do tempo de resposta (runtime) da busca na Trie + vizinhança + filtragem Haversine
    t_inicio = time.perf_counter()

    # Escolha do tamanho do prefixo compatível com a cobertura da grade 3x3 (célula central + 8 vizinhas):
    # Nível 6 (~0.61 km x 1.15 km) cobre com segurança raios até 0.6 km;
    # Nível 5 (~4.89 km x 4.60 km) cobre com segurança raios até 4.5 km;
    # Nível 4 (~19.5 km x 36.8 km) cobre com segurança raios até 10.0 km.
    if raio_km <= 0.6:
        tamanho_prefixo = 6
    elif raio_km <= 4.5:
        tamanho_prefixo = 5
    else:
        tamanho_prefixo = 4

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
    filtrados_ids = set()
    for ent in candidatos_dados:
        dist = calcular_distancia_haversine(lat_r, lon_r, ent['lat'], ent['lon'])
        if dist <= raio_km:
            filtrados_ids.add(ent['id'])
            tempo_min = round((dist / 30.0) * 60)
            tabela_dados.append({'id': ent['id'], 'distancia': round(dist, 2), 'tempo': tempo_min})

    tabela_dados = sorted(tabela_dados, key=lambda k: k['distancia'])
    runtime_ms = (time.perf_counter() - t_inicio) * 1000.0

    marcadores = [
        dl.Marker(
            position=[lat_r, lon_r],
            icon=ICONE_AZUL,
            children=[dl.Tooltip(f"Restaurante (Prefixo: {hash_restaurante})")]
        )
    ]

    for ent in todos_entregadores:
        icone = ICONE_VERMELHO if ent['id'] in filtrados_ids else ICONE_CINZA
        marcadores.append(dl.Marker(
            position=[ent['lat'], ent['lon']],
            icon=icone,
            children=[dl.Tooltip(ent['id'])]
        ))

    if tabela_dados:
        menor_dist = tabela_dados[0]['distancia']
        media_dist = round(sum(d['distancia'] for d in tabela_dados) / len(tabela_dados), 2)
        tempo_medio = round(sum(d['tempo'] for d in tabela_dados) / len(tabela_dados))
    else:
        menor_dist, media_dist, tempo_medio = None, None, None

    painel_metricas = _criar_painel_metricas(
        total_filtrados=len(tabela_dados),
        total_frota=len(todos_entregadores),
        menor_dist=menor_dist,
        media_dist=media_dist,
        tempo_medio=tempo_medio,
        runtime_ms=runtime_ms
    )

    return msg_atual, marcadores, tabela_dados, [lat_r, lon_r], painel_metricas

if __name__ == '__main__':
    geo_rotas.carregar_grafo()
    app.run(debug=True, use_reloader=False, port=8050)