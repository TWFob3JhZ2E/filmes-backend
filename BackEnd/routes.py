import os
import json
import requests
from bs4 import BeautifulSoup
from flask import jsonify, request
from threading import Thread

# Diretórios e caminhos
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
FILMES_ENCONTRADOS_DIR = os.path.join(BASE_DIR, 'Filmes_Encontrados')

# Garante que a pasta 'temp' exista
os.makedirs(TEMP_DIR, exist_ok=True)

# Caminhos para os arquivos JSON
FILMES_PAGINA_JSON_PATH = os.path.join(FILMES_ENCONTRADOS_DIR, 'CodeFilmesNomes.json')
CODE_SERIES_NOMES_PATH = os.path.join(FILMES_ENCONTRADOS_DIR, 'CodeSeriesNomes.json')
FILMES_NOVOS_JSON_PATH = os.path.join(TEMP_DIR, 'Novosfilmes.json')
SERIES_JSON_PATH = os.path.join(TEMP_DIR, 'series.json')
FILMES_HOME_JSON_PATH = os.path.join(TEMP_DIR, 'Filmes.json')
CODE_FILMES_JSON_PATH = os.path.join(TEMP_DIR, 'CodeFilmes.json')
CODE_SERIES_JSON_PATH = os.path.join(TEMP_DIR, 'CodeSeries.json')

# Funções utilitárias
def carregar_dados_json(caminho):
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Erro ao decodificar o arquivo JSON {caminho}, criando um novo arquivo.")
            return []
    return []

def salvar_dados_json(caminho, dados):
    try:
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        print(f"Arquivo {caminho} salvo com sucesso!")
    except Exception as e:
        print(f"Erro ao salvar o arquivo {caminho}: {e}")

def item_existe(lista, item_id):
    return any(item['id'] == item_id for item in lista)

# Função para registrar as rotas
def registrar_rotas(app):

    @app.route('/codigos/series')
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
                return jsonify({"codigos": ", ".join(codigos)})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/filmes/novos')
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
            except Exception as e:
                print(f"Erro ao atualizar filmes: {e}")

        Thread(target=atualizar_filmes_novos).start()
        return jsonify(filmes_novos_atualizados)

    @app.route('/filmes/home')
    def filmes_home():
        filmes_cache = carregar_dados_json(FILMES_HOME_JSON_PATH)
        return jsonify(filmes_cache)

    @app.route('/filmes/pagina')
    def filmes_pagina():
        filmes_cache = carregar_dados_json(FILMES_PAGINA_JSON_PATH)
        pagina = int(request.args.get('pagina', 1))
        filmes_por_pagina = 50
        inicio = (pagina - 1) * filmes_por_pagina
        fim = inicio + filmes_por_pagina
        filmes_paginados = filmes_cache[inicio:fim]
        return jsonify(filmes_paginados)

    @app.route('/filmes/pagina/atualizar')
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
            except Exception as e:
                print(f"Erro ao atualizar filmes: {e}")

        Thread(target=atualizar_filmes).start()
        return jsonify(filmes_atualizados)

    @app.route('/buscar')
    def buscar_nomes():
        termo = request.args.get('q', '').lower()
        filmes = carregar_dados_json(FILMES_PAGINA_JSON_PATH)
        series = carregar_dados_json(CODE_SERIES_NOMES_PATH)

        resultados_filmes = [f for f in filmes if termo in f['titulo'].lower()]
        resultados_series = [s for s in series if termo in s['titulo'].lower()]

        resultados = resultados_filmes + resultados_series
        return jsonify(resultados[:10])  # Limita a 10 resultados

    @app.route('/series/pagina')
    def series_pagina():
        series_cache = carregar_dados_json(CODE_SERIES_NOMES_PATH)

        # Paginação
        pagina = int(request.args.get('pagina', 1))
        series_por_pagina = 50
        inicio = (pagina - 1) * series_por_pagina
        fim = inicio + series_por_pagina
        series_paginadas = series_cache[inicio:fim]

        return jsonify(series_paginadas)

    @app.route('/series')
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
            except Exception as e:
                print(f"Erro ao atualizar séries: {e}")

        Thread(target=atualizar_series).start()
        return jsonify(series_atualizadas)

    @app.route('/codigos/filmes')
    def codigos_filmes():
        codigos_filmes_cache = carregar_dados_json(CODE_FILMES_JSON_PATH)
        if codigos_filmes_cache:
            return jsonify({"codigos": ", ".join(codigos_filmes_cache.get("codigos", []))})

        try:
            url = "https://superflixapi.co/filmes/lista/"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                import re
                codigos = re.findall(r'tt\d+', soup.get_text())
                codigos_filmes_cache = {"codigos": codigos}
                salvar_dados_json(CODE_FILMES_JSON_PATH, codigos_filmes_cache)
                return jsonify({"codigos": ", ".join(codigos)})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

# Função para atualizar os códigos no início da aplicação
def atualizar_codigos_inicial(app):
    with app.app_context():
        try:
            app.test_client().get('/codigos/filmes')
            app.test_client().get('/codigos/series')
        except Exception as e:
            print("Erro ao atualizar os códigos iniciais:", e)
