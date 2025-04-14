from flask import jsonify
from bs4 import BeautifulSoup
import requests
import re

from utils import carregar_dados_json, salvar_dados_json, caminho_json
from routes import codigos_bp

CODE_FILMES_JSON_PATH = caminho_json('CodeFilmes.json')
CODE_SERIES_JSON_PATH = caminho_json('CodeSeries.json')

@codigos_bp.route('/codigos/filmes')
def codigos_filmes():
    cache = carregar_dados_json(CODE_FILMES_JSON_PATH)
    if cache:
        return jsonify({"codigos": ", ".join(cache.get("codigos", []))})

    try:
        url = "https://superflixapi.co/filmes/lista/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            texto = soup.get_text()
            codigos = re.findall(r'tt\\d+', texto)
            salvar_dados_json(CODE_FILMES_JSON_PATH, {"codigos": codigos})
            return jsonify({"codigos": ", ".join(codigos)})
        return jsonify({'error': 'Erro ao obter códigos de filmes'}), 500
    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({'error': 'Erro interno'}), 500

@codigos_bp.route('/codigos/series')
def codigos_series():
    cache = carregar_dados_json(CODE_SERIES_JSON_PATH)
    if cache:
        return jsonify({"codigos": ", ".join(cache.get("codigos", []))})

    try:
        url = "https://superflixapi.co/series/lista/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            raw_codigos = soup.decode_contents().split('<br/>')
            codigos = [codigo.strip() for codigo in raw_codigos if codigo.strip().isdigit()]
            salvar_dados_json(CODE_SERIES_JSON_PATH, {"codigos": codigos})
            return jsonify({"codigos": ", ".join(codigos)})
        return jsonify({'error': 'Erro ao obter códigos de séries'}), 500
    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({'error': 'Erro interno'}), 500
