from flask import Blueprint, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from bs4 import BeautifulSoup
import requests
from threading import Thread
from utils.helpers import carregar_dados_json, salvar_dados_json, item_existe

filmes_bp = Blueprint('filmes', __name__)

# Caminhos dos arquivos JSON
FILMES_PAGINA_JSON_PATH = 'CodeFilmesNomes.json'
FILMES_NOVOS_JSON_PATH = 'Novosfilmes.json'
FILMES_HOME_JSON_PATH = 'Filmes.json'

# Configuração do rate limiting
limiter = Limiter(
    get_remote_address,
    app=None  
)

# Aplica rate limiting para a rota /filmes/home
@filmes_bp.route('/filmes/home')
@limiter.limit("200 per hour")  
def filmes_home():
    filmes_cache = carregar_dados_json(FILMES_HOME_JSON_PATH)
    return jsonify(filmes_cache)

# Aplica rate limiting para a rota /filmes/novos
@filmes_bp.route('/filmes/novos')
@limiter.limit("450 per hour")  
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
            print(f"Erro ao fazer scraping de novos filmes: {e}")

    Thread(target=atualizar_filmes_novos).start()
    return jsonify(filmes_novos_atualizados)

# Aplica rate limiting para a rota /filmes/pagina
@filmes_bp.route('/filmes/pagina')
@limiter.limit("500 per hour")  # Limite de 200 requisições por hora para filmes por página
def filmes_pagina():
    filmes_cache = carregar_dados_json(FILMES_PAGINA_JSON_PATH)
    pagina = int(request.args.get('pagina', 1))
    filmes_por_pagina = 50
    inicio = (pagina - 1) * filmes_por_pagina
    fim = inicio + filmes_por_pagina
    filmes_paginados = filmes_cache[inicio:fim]
    return jsonify(filmes_paginados)

# Aplica rate limiting para a rota /filmes/pagina/atualizar
@filmes_bp.route('/filmes/pagina/atualizar')
@limiter.limit("300 per hour")  # Limite de 100 requisições por hora para atualizar filmes por página
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
            print(f"Erro ao atualizar filmes por página: {e}")

    Thread(target=atualizar_filmes).start()
    return jsonify(filmes_atualizados)
