from flask import Blueprint, jsonify
import requests
from bs4 import BeautifulSoup
import re

from config import *
from utils import carregar_dados_json, salvar_dados_json

codigos_bp = Blueprint('codigos', __name__)

@codigos_bp.route('/codigos/series')
def codigos_series():
    cache = carregar_dados_json(CODE_SERIES_JSON_PATH)
    if cache:
        return jsonify({"codigos": ", ".join(cache.get("codigos", []))})

    try:
        url = "https://superflixapi.co/series/lista/"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, 'html.parser')
            raw = soup.decode_contents().split('<br/>')
            codigos = [c.strip() for c in raw if c.strip().isdigit()]
            salvar_dados_json(CODE_SERIES_JSON_PATH, {"codigos": codigos})
            return jsonify({"codigos": ", ".join(codigos)})
    except Exception as e:
        print(f"Erro: {e}")
    return jsonify({'error': 'Erro ao carregar códigos de séries'}), 500

@codigos_bp.route('/codigos/filmes')
def codigos_filmes():
    cache = carregar_dados_json(CODE_FILMES_JSON_PATH)
    if cache:
        return jsonify({"codigos": ", ".join(cache.get("codigos", []))})

    try:
        url = "https://superflixapi.co/filmes/lista/"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            texto = BeautifulSoup(r.content, 'html.parser').get_text()
            codigos = re.findall(r'tt\d+', texto)
            salvar_dados_json(CODE_FILMES_JSON_PATH, {"codigos": codigos})
            return jsonify({"codigos": ", ".join(codigos)})
    except Exception as e:
        print(f"Erro: {e}")
    return jsonify({'error': 'Erro ao carregar códigos de filmes'}), 500
