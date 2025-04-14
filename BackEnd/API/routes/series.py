from flask import Blueprint, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from bs4 import BeautifulSoup
import requests
from threading import Thread
from utils.helpers import carregar_dados_json, salvar_dados_json, item_existe

series_bp = Blueprint('series', __name__)

# Caminhos dos arquivos JSON
SERIES_JSON_PATH = 'series.json'
CODE_SERIES_NOMES_PATH = 'CodeSeriesNomes.json'

# Configuração do rate limiting
limiter = Limiter(
    get_remote_address,
    app=None  # Não precisa passar o app diretamente aqui, porque estamos no Blueprint
)

# Aplica rate limiting para a rota /series
@series_bp.route('/series')
@limiter.limit("150 per hour")  # Limite de 150 requisições por hora para séries
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
            print(f"Erro ao atualizar séries: {e}")

    Thread(target=atualizar_series).start()
    return jsonify(series_atualizadas)

# Aplica rate limiting para a rota /series/pagina
@series_bp.route('/series/pagina')
@limiter.limit("100 per hour")  # Limite de 100 requisições por hora para séries por página
def series_pagina():
    series_cache = carregar_dados_json(CODE_SERIES_NOMES_PATH)

    pagina = int(request.args.get('pagina', 1))
    series_por_pagina = 50
    inicio = (pagina - 1) * series_por_pagina
    fim = inicio + series_por_pagina
    series_paginadas = series_cache[inicio:fim]

    return jsonify(series_paginadas)
