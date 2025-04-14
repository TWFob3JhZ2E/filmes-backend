from flask import Blueprint, jsonify
import requests
from bs4 import BeautifulSoup
import re
from utils.helpers import carregar_dados_json, salvar_dados_json

codigos_bp = Blueprint('codigos', __name__)

CODE_FILMES_JSON_PATH = 'CodeFilmes.json'
CODE_SERIES_JSON_PATH = 'CodeSeries.json'

@codigos_bp.route('/codigos/filmes')
def codigos_filmes():
    codigos_filmes_cache = carregar_dados_json(CODE_FILMES_JSON_PATH)

    if codigos_filmes_cache:
        codigos_formatados = ", ".join(codigos_filmes_cache.get("codigos", []))
        return jsonify({"codigos": codigos_formatados})

    try:
        url = "https://superflixapi.co/filmes/lista/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            dados_bagunçados = soup.get_text()
            codigos = re.findall(r'tt\d+', dados_bagunçados)

            codigos_filmes_cache = {"codigos": codigos}
            salvar_dados_json(CODE_FILMES_JSON_PATH, codigos_filmes_cache)

            codigos_formatados = ", ".join(codigos)
            return jsonify({"codigos": codigos_formatados})
        else:
            return jsonify({'error': 'Não foi possível carregar os códigos de filmes'}), 500

    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar códigos de filmes: {e}")
        return jsonify({'error': 'Erro ao tentar carregar os códigos de filmes'}), 500


@codigos_bp.route('/codigos/series')
def codigos_series():
    codigos_series_cache = carregar_dados_json(CODE_SERIES_JSON_PATH)

    if codigos_series_cache:
        codigos_formatados = ", ".join(codigos_series_cache.get("codigos", []))
        return jsonify({"codigos": codigos_formatados})

    try:
        url = "https://superflixapi.co/series/lista/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            raw_codigos = soup.decode_contents().split('<br/>')
            codigos = [codigo.strip() for codigo in raw_codigos if codigo.strip().isdigit()]

            codigos_series_cache = {"codigos": codigos}
            salvar_dados_json(CODE_SERIES_JSON_PATH, codigos_series_cache)

            codigos_formatados = ", ".join(codigos)
            return jsonify({"codigos": codigos_formatados})
        else:
            return jsonify({'error': 'Não foi possível carregar os códigos de séries'}), 500

    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar códigos de séries: {e}")
        return jsonify({'error': 'Erro ao tentar carregar os códigos de séries'}), 500
