# app.py
import warnings
warnings.filterwarnings("ignore", module="urllib3")

import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import busca
import enderecos
from geohash import codificar, decodificar_bbox
from trie import ArvoreTrie
from simulador import SimuladorFrota
from geometria import GeometriaRotas

motor_trie = ArvoreTrie()
simulador = SimuladorFrota()  # lê dados/bares.csv a partir da raiz do projeto
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

# Índice de busca normalizado (nome fantasia, razão social, rua, número, bairro) de TODOS os
# restaurantes; as opções do menu são calculadas no servidor conforme o usuário digita.
indice_busca = enderecos.indice_de_busca(simulador.restaurantes)
LIMITE_OPCOES = 50
MIN_LETRAS_BUSCA = 2
PREFIXO_ENDERECO_LIVRE = "livre:"
# Cada entregador vira um marcador no navegador; acima disso o mapa fica pesado demais.
MAX_ENTREGADORES = 10000

def _legenda():
    itens = [
        ("#0d6efd", "Restaurante e círculo do raio"),
        ("#dc3545", "Entregador dentro do raio"),
        ("#6c757d", "Entregador fora do raio"),
        ("#adb5bd", "Células geohash consultadas na Trie"),
    ]
    return html.Div([
        html.Span([
            html.Span(style={'display': 'inline-block', 'width': '12px', 'height': '12px', 'borderRadius': '50%',
                             'backgroundColor': cor, 'marginRight': '6px'}),
            texto,
        ], className="me-3 small") for cor, texto in itens
    ], className="mt-2")


def _camadas_da_busca(lat, lon, raio_km, prefixos):
    """Círculo do raio e retângulos das células geohash consultadas."""
    camadas = []
    for prefixo in prefixos:
        sul, norte, oeste, leste = decodificar_bbox(prefixo)
        camadas.append(dl.Rectangle(bounds=[[sul, oeste], [norte, leste]], color="#adb5bd", weight=1,
                                    fillOpacity=0.03, children=[dl.Tooltip(f"Célula {prefixo}")]))
    camadas.append(dl.Circle(center=[lat, lon], radius=raio_km * 1000.0, color="#0d6efd", weight=2,
                             fillOpacity=0.07))
    return camadas


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
                    dbc.Input(id='input-n', type='number', value=100, min=1, max=MAX_ENTREGADORES, step=1, className="mb-1"),
                    html.Small(f"Máximo de {MAX_ENTREGADORES:,} entregadores (cada um é um marcador no navegador).".replace(",", "."),
                               className="text-muted d-block mb-3"),
                    dbc.Button('Gerar Entregadores', id='btn-gerar', color="success", className="w-100 fw-bold"),
                    dcc.Loading(type="circle", children=html.Div(id='msg-geracao', className="mt-3 text-success fw-bold text-center"))
                ])
            ], className="mb-4 shadow-sm border-0"),

            # Painel 2: Filtros
            dbc.Card([
                dbc.CardHeader(html.H5("2. Consulta e Filtros", className="mb-0 fw-bold")),
                dbc.CardBody([
                    dbc.Label("Restaurante / Ponto de Coleta:", className="fw-semibold"),
                    dcc.Dropdown(
                        id='dropdown-restaurante',
                        options=[],
                        placeholder="Digite o nome ou o endereço...",
                        className="mb-1"
                    ),
                    html.Small("Digite ao menos 2 letras. A busca cobre todos os restaurantes do CSV (nome fantasia, "
                               "razão social, rua, número e bairro). Se não achar, escolha \"Buscar o endereço digitado\".",
                               className="text-muted d-block mb-4"),
                    dbc.Label("Raio de Atendimento (km):", className="fw-semibold"),
                    dcc.Slider(
                        id='slider-raio', min=0.5, max=10.0, step=0.5, value=2.0, 
                        marks={i: f"{i}" for i in range(1, 11)},
                        tooltip={"placement": "bottom", "always_visible": True},
                        className="mb-4"
                    ),
                    dbc.Button('Buscar Entregadores', id='btn-buscar', color="primary", className="w-100 fw-bold"),
                    html.Small("A primeira busca por um restaurante consulta o Nominatim (~1 s por tentativa); "
                               "as seguintes usam o cache.", className="text-muted d-block mt-2")
                ])
            ], className="shadow-sm border-0")
        ], md=4), # Ocupa 4 de 12 colunas no grid

        # Coluna da Direita: Visualização de Dados
        dbc.Col([
            # Painel do Mapa
            dbc.Card([
                dbc.CardBody([
                    dcc.Loading(type="circle", children=dl.Map(
                        id='mapa-interativo', center=[-19.916681, -43.934493], zoom=13,
                        style={'width': '100%', 'height': '55vh', 'borderRadius': '8px'}, children=[
                            dl.TileLayer(),
                            dl.LayerGroup(id='camada-marcadores')
                        ])),
                    _legenda()
                ], className="p-2")
            ], className="mb-4 shadow-sm border-0"),

            # Painel da Tabela e Métricas Resumo
            dbc.Card([
                dbc.CardHeader(html.H5("Entregadores Disponíveis e Métricas Resumo", className="mb-0 fw-bold")),
                dbc.CardBody([
                    dcc.Loading(type="dot", children=html.Div(id='metricas-resumo', className="mb-3")),
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
                    ),
                    html.Small(f"Tempo estimado = distância em linha reta (Haversine) ÷ {busca.VELOCIDADE_KMH:.0f} km/h; "
                               "não considera o traçado das ruas nem o trânsito.", className="text-muted d-block mt-2")
                ])
            ], className="shadow-sm border-0")
        ], md=8) # Ocupa 8 de 12 colunas no grid
    ])
], fluid=True, className="bg-light pb-5")


def _cartao(titulo, valor, detalhe=None):
    corpo = [html.Small(titulo, className="d-block text-muted"), html.Strong(valor)]
    if detalhe:
        corpo.append(html.Small(detalhe, className="d-block text-muted"))
    return dbc.Col(dbc.Alert(corpo, color="light", className="p-2 mb-0 text-center border h-100"), xs=6, lg=True)


def _criar_painel_metricas(total_filtrados, total_frota, menor_dist, media_dist, tempo_medio, resultado):
    return dbc.Row([
        _cartao("No Raio / Frota", f"{total_filtrados} / {total_frota}"),
        _cartao("Candidatos da Trie", f"{resultado.candidatos}",
                f"{len(resultado.prefixos)} células, precisão {resultado.precisao}"),
        _cartao("Menor Distância", f"{menor_dist} km" if menor_dist is not None else "-"),
        _cartao("Distância / Tempo Médio", f"{media_dist} km ({tempo_medio} min)" if media_dist is not None else "-"),
        _cartao("Runtime da Busca", f"{resultado.ms_total:.2f} ms",
                f"Trie {resultado.ms_trie:.2f} + filtro {resultado.ms_filtro:.2f}"),
    ], className="g-2")


def _opcao(valor, busca_atual=""):
    """Opção do menu para um restaurante (índice do CSV) ou para um endereço livre."""
    if isinstance(valor, str) and valor.startswith(PREFIXO_ENDERECO_LIVRE):
        texto = valor[len(PREFIXO_ENDERECO_LIVRE):]
        return {'label': f"Buscar o endereço digitado: {texto}", 'value': valor, 'search': busca_atual or texto}
    rotulo = enderecos.rotulo_restaurante(simulador.restaurantes.loc[valor])
    return {'label': rotulo, 'value': int(valor), 'search': busca_atual or rotulo}


@app.callback(
    Output('dropdown-restaurante', 'options'),
    Input('dropdown-restaurante', 'search_value'),
    State('dropdown-restaurante', 'value'),
)
def atualizar_opcoes(termo, selecionado):
    termo = " ".join((termo or "").split())
    opcoes = []
    if len(termo) >= MIN_LETRAS_BUSCA:
        for idx in enderecos.buscar_restaurantes(indice_busca, termo, LIMITE_OPCOES):
            opcoes.append(_opcao(idx, termo))
        opcoes.append(_opcao(PREFIXO_ENDERECO_LIVRE + termo, termo))
    # mantém a opção escolhida na lista, senão o menu "esquece" a seleção ao limpar a digitação
    if selecionado is not None and all(o['value'] != selecionado for o in opcoes):
        opcoes.insert(0, _opcao(selecionado))
    return opcoes


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

        n_entregadores = int(n_entregadores)
        limitado = n_entregadores > MAX_ENTREGADORES
        n_entregadores = min(n_entregadores, MAX_ENTREGADORES)

        entregadores_gerados = simulador.gerar_entregadores(n_entregadores, geo_rotas)
        busca.indexar(motor_trie, entregadores_gerados)

        marcadores_novos = []
        for ent in entregadores_gerados:
            hash_str = codificar(ent['lat'], ent['lon'], precisao=8)
            marcadores_novos.append(dl.Marker(
                position=[ent['lat'], ent['lon']],
                icon=ICONE_CINZA,
                children=[dl.Tooltip(f"{ent['id']} (Geohash: {hash_str})")]
            ))

        centro_mapa = [-19.916681, -43.934493]
        if entregadores_gerados:
            centro_mapa = [entregadores_gerados[0]['lat'], entregadores_gerados[0]['lon']]

        msg = f"Frota de {n_entregadores} entregadores gerada com sucesso."
        if limitado:
            msg += f" (N limitado ao máximo de {MAX_ENTREGADORES}.)"
        resumo_inicial = dbc.Alert(
            f"Frota ativa: {len(entregadores_gerados)} entregadores indexados na Trie Compacta. Escolha um restaurante e clique em Buscar.",
            color="secondary", className="py-2 mb-0 text-center"
        )
        if not geo_rotas.ultima_projecao_aplicada:
            resumo_inicial = html.Div([
                dbc.Alert(geo_rotas.erro_malha or "Malha viária não carregada.", color="warning",
                          className="py-2 text-center"),
                resumo_inicial,
            ])
        return msg, marcadores_novos, [], centro_mapa, resumo_inicial

    # Ação 2: Buscar entregadores próximos ao restaurante selecionado
    if restaurante_idx is None:
        return msg_atual, dash.no_update, [], [-19.916681, -43.934493], dbc.Alert("Escolha um restaurante ou endereço para realizar a consulta.", color="warning", className="py-2 mb-0 text-center")

    if isinstance(restaurante_idx, str) and restaurante_idx.startswith(PREFIXO_ENDERECO_LIVRE):
        coordenada = simulador.geocodificar_texto(restaurante_idx[len(PREFIXO_ENDERECO_LIVRE):])
    else:
        coordenada = simulador.geocodificar(simulador.restaurantes.loc[restaurante_idx], restaurante_idx)

    todos_entregadores = motor_trie.buscar_prefixo("")
    if coordenada is None:
        marcadores_preservados = [
            dl.Marker(
                position=[ent['lat'], ent['lon']],
                icon=ICONE_CINZA,
                children=[dl.Tooltip(ent['id'])]
            )
            for ent in todos_entregadores
        ]
        motivo = simulador.ultimo_erro_geo or "Endereço não encontrado em Belo Horizonte."
        return msg_atual, marcadores_preservados, [], [-19.916681, -43.934493], dbc.Alert(
            f"Não foi possível geocodificar o endereço selecionado. {motivo}",
            color="danger", className="py-2 mb-0 text-center")

    lat_r, lon_r = coordenada.como_tupla()

    # Busca em duas etapas (Trie nas células que cobrem o círculo + Haversine); ver busca.py
    resultado = busca.buscar_no_raio(motor_trie, lat_r, lon_r, raio_km)
    tabela_dados = resultado.dentro
    filtrados_ids = {item['id'] for item in tabela_dados}

    marcadores = _camadas_da_busca(lat_r, lon_r, raio_km, resultado.prefixos) + [
        dl.Marker(
            position=[lat_r, lon_r],
            icon=ICONE_AZUL,
            children=[dl.Tooltip(f"Restaurante ({len(resultado.prefixos)} células, precisão {resultado.precisao})")]
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
        resultado=resultado
    )

    if coordenada.aproximada:
        aviso = dbc.Alert(
            f"Posição aproximada: só foi possível localizar {'a rua' if coordenada.precisao == 'rua' else 'o bairro'} do restaurante, "
            "então o ponto azul pode estar distante do endereço real.",
            color="warning", className="py-2 text-center")
        painel_metricas = html.Div([aviso, painel_metricas])

    return msg_atual, marcadores, tabela_dados, [lat_r, lon_r], painel_metricas

if __name__ == '__main__':
    if not geo_rotas.carregar_grafo():
        print("[App] Seguindo sem malha viária: os entregadores não serão projetados nas ruas.")
    app.run(debug=True, use_reloader=False, port=8050)
