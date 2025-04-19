from flask import Blueprint, jsonify, request
import requests
from bs4 import BeautifulSoup
from threading import Thread

from config import *
from utils import carregar_dados_json, salvar_dados_json, item_existe

filmes_bp = Blueprint('filmes', __name__)

@filmes_bp.route('/filmes/novos')
def filmes_novos():
    filmes_novos_cache = carregar_dados_json(FILMES_NOVOS_JSON_PATH)
    filmes_novos_atualizados = filmes_novos_cache.copy()

    def atualizar_filmes_novos():
        try:
            url = "https://superflixapi.co/filmes"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                novos_filmes = []

                for poster in soup.find_all('div', class_='poster'):
                    titulo = poster.find('span', class_='title').get_text(strip=True)
                    qualidade = poster.find('span', class_='year').get_text(strip=True)
                    imagem = poster.find('img')['src']
                    link = poster.find('a', class_='btn')['href']
                    filme_id = link.split('/')[-1]

                    if not item_existe(filmes_novos_cache, filme_id):
                        novos_filmes.append({
                            'titulo': titulo,
                            'qualidade': qualidade,
                            'capa': imagem,
                            'id': filme_id
                        })

                if novos_filmes:
                    filmes_novos_cache.extend(novos_filmes)
                    salvar_dados_json(FILMES_NOVOS_JSON_PATH, filmes_novos_cache)

        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar filmes: {e}")

    Thread(target=atualizar_filmes_novos).start()
    return jsonify(filmes_novos_atualizados)

@filmes_bp.route('/filmes/home')
def filmes_home():
    return jsonify(carregar_dados_json(FILMES_HOME_JSON_PATH))

@filmes_bp.route('/filmes/pagina')
def filmes_pagina():
    filmes_cache = carregar_dados_json(FILMES_PAGINA_JSON_PATH)
    pagina = int(request.args.get('pagina', 1))
    filmes_por_pagina = 50
    inicio = (pagina - 1) * filmes_por_pagina
    fim = inicio + filmes_por_pagina
    return jsonify(filmes_cache[inicio:fim])

@filmes_bp.route('/filmes/pagina/atualizar')
def filmes_pagina_atualizar():
    filmes_cache = carregar_dados_json(FILMES_PAGINA_JSON_PATH)
    filmes_atualizados = filmes_cache.copy()

    def atualizar_filmes():
        try:
            url = "https://superflixapi.co/filmes"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                novos_filmes = []

                for poster in soup.find_all('div', class_='poster'):
                    titulo = poster.find('span', class_='title').get_text(strip=True)
                    qualidade = poster.find('span', class_='year').get_text(strip=True)
                    imagem = poster.find('img')['src']
                    link = poster.find('a', class_='btn')['href']
                    filme_id = link.split('/')[-1]

                    if not item_existe(filmes_cache, filme_id):
                        novos_filmes.append({
                            'titulo': titulo,
                            'qualidade': qualidade,
                            'capa': imagem,
                            'id': filme_id
                        })

                if novos_filmes:
                    filmes_cache.extend(novos_filmes)
                    salvar_dados_json(FILMES_PAGINA_JSON_PATH, filmes_cache)

        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar filmes: {e}")

    Thread(target=atualizar_filmes).start()
    return jsonify(filmes_atualizados)
