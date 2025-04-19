from flask import Blueprint, jsonify, request
import requests
from bs4 import BeautifulSoup
from threading import Thread

from config import *
from utils import carregar_dados_json, salvar_dados_json, item_existe

series_bp = Blueprint('series', __name__)

@series_bp.route('/series')
def series():
    series_cache = carregar_dados_json(SERIES_JSON_PATH)
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
                    salvar_dados_json(SERIES_JSON_PATH, series_cache)

        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar séries: {e}")

    Thread(target=atualizar_series).start()
    return jsonify(series_atualizadas)

@series_bp.route('/series/pagina')
def series_pagina():
    series_cache = carregar_dados_json(CODE_SERIES_NOMES_PATH)
    pagina = int(request.args.get('pagina', 1))
    por_pagina = 50
    return jsonify(series_cache[(pagina-1)*por_pagina : pagina*por_pagina])
