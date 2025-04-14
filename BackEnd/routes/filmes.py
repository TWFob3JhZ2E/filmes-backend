from flask import jsonify, request
from threading import Thread
from bs4 import BeautifulSoup
import requests

from BackEnd.utils import carregar_dados_json, salvar_dados_json, item_existe, caminho_json
from routes import filmes_bp

FILMES_JSON = caminho_json('Filmes.json')
NOVOS_FILMES_JSON = caminho_json('Novosfilmes.json')
FILMES_PAGINA_JSON = caminho_json('CodeFilmesNomes.json')

@filmes_bp.route('/filmes/home')
def filmes_home():
    filmes_cache = carregar_dados_json(FILMES_JSON)
    return jsonify(filmes_cache)

@filmes_bp.route('/filmes/novos')
def filmes_novos():
    filmes_novos_cache = carregar_dados_json(NOVOS_FILMES_JSON)
    filmes_novos_atualizados = filmes_novos_cache.copy()

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

                    if not item_existe(filmes_novos_cache, filme_id):
                        novos_filmes.append({
                            'titulo': titulo,
                            'qualidade': qualidade,
                            'capa': imagem,
                            'id': filme_id
                        })

                if novos_filmes:
                    filmes_novos_cache.extend(novos_filmes)
                    salvar_dados_json(NOVOS_FILMES_JSON, filmes_novos_cache)
        except Exception as e:
            print(f"Erro ao atualizar filmes: {e}")

    Thread(target=atualizar_filmes).start()
    return jsonify(filmes_novos_atualizados)
