from flask import jsonify, request
from threading import Thread
from bs4 import BeautifulSoup
import requests

from utils import carregar_dados_json, salvar_dados_json, item_existe, caminho_json
from routes import series_bp

SERIES_JSON = caminho_json('series.json')
CODE_SERIES_NOMES_PATH = caminho_json('CodeSeriesNomes.json')

@series_bp.route('/series')
def series():
    series_cache = carregar_dados_json(SERIES_JSON)
    series_atualizadas = series_cache.copy()

    def atualizar_series():
        try:
            url = "https://superflixapi.co/series"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                novas_series = []

                for poster in soup.find_all('div', class_='poster'):
                    titulo = poster.find('span', class_='title').get_text(strip=True)
                    qualidade = poster.find('span', class_='year').get_text(strip=True)
                    imagem = poster.find('img')['src']
                    link = poster.find('a', class_='btn')['href']
                    serie_id = link.split('/')[-1]

                    if not item_existe(series_cache, serie_id):
                        novas_series.append({
                            'titulo': titulo,
                            'qualidade': qualidade,
                            'capa': imagem,
                            'id': serie_id
                        })

                if novas_series:
                    series_cache.extend(novas_series)
                    salvar_dados_json(SERIES_JSON, series_cache)
        except Exception as e:
            print(f"Erro ao atualizar séries: {e}")

    Thread(target=atualizar_series).start()
    return jsonify(series_atualizadas)

@series_bp.route('/series/pagina')
def series_pagina():
    series_cache = carregar_dados_json(CODE_SERIES_NOMES_PATH)
    pagina = int(request.args.get('pagina', 1))
    series_por_pagina = 50
    inicio = (pagina - 1) * series_por_pagina
    fim = inicio + series_por_pagina
    return jsonify(series_cache[inicio:fim])
