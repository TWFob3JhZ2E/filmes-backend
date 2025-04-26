import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from flask_cors import CORS
from threading import Thread, Lock
from urllib.parse import urljoin

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('superflix_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Lock para sincronizar acesso a arquivos JSON
json_lock = Lock()

# Configurações centralizadas (pode ser movido para .env com python-dotenv)
CONFIG = {
    'BASE_URL': 'https://superflixapi.in/filmes',
    'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'ITEMS_PER_PAGE': 50,
    'JSON_INDENT': 4,
    'BASE_DIR': os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
    'TEMP_DIR': 'temp',
    'FILMES_ENCONTRADOS_DIR': 'Filmes_Encontrados'
}

# Caminhos para diretórios
TEMP_DIR = os.path.join(CONFIG['BASE_DIR'], CONFIG['TEMP_DIR'])
FILMES_ENCONTRADOS_DIR = os.path.join(CONFIG['BASE_DIR'], CONFIG['FILMES_ENCONTRADOS_DIR'])

# Garante que os diretórios existem
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(FILMES_ENCONTRADOS_DIR, exist_ok=True)

# Caminhos para arquivos JSON
JSON_PATHS = {
    'filmes_pagina': os.path.join(FILMES_ENCONTRADOS_DIR, 'CodeFilmesNomes.json'),
    'series_nomes': os.path.join(FILMES_ENCONTRADOS_DIR, 'CodeSeriesNomes.json'),
    'filmes_novos': os.path.join(TEMP_DIR, 'Novosfilmes.json'),
    'series': os.path.join(TEMP_DIR, 'series.json'),
    'filmes_home': os.path.join(TEMP_DIR, 'Filmes.json'),
    'code_filmes': os.path.join(TEMP_DIR, 'CodeFilmes.json'),
    'code_series': os.path.join(TEMP_DIR, 'CodeSeries.json')
}

def carregar_dados_json(caminho):
    """Carrega dados de um arquivo JSON com sincronização."""
    with json_lock:
        if os.path.exists(caminho):
            try:
                with open(caminho, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao decodificar {caminho}: {e}")
                return []
        return []

def salvar_dados_json(caminho, dados):
    """Salva dados em um arquivo JSON com sincronização."""
    with json_lock:
        try:
            with open(caminho, 'w', encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=CONFIG['JSON_INDENT'])
            logger.info(f"Arquivo {caminho} salvo com sucesso")
        except Exception as e:
            logger.error(f"Erro ao salvar {caminho}: {e}")

def item_existe(lista, item_id):
    """Verifica se um item com o ID existe na lista."""
    return any(item.get('id') == item_id for item in lista)

def atualizar_dados(url, cache_path, tipo='filmes'):
    """Função genérica para atualizar filmes ou séries via scraping."""
    cache = carregar_dados_json(cache_path)
    try:
        headers = {'User-Agent': CONFIG['USER_AGENT']}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        novos_itens = []

        for poster in soup.find_all('div', class_='poster'):
            try:
                titulo = poster.find('span', Uclass_='title')
                qualidade = poster.find('span', class_='year')
                imagem = poster.find('img')
                link = poster.find('a', class_='btn')

                if not all([titulo, qualidade, imagem, link]):
                    continue

                titulo = titulo.get_text(strip=True)
                qualidade = qualidade.get_text(strip=True)
                imagem = urljoin(CONFIG['BASE_URL'], imagem['src'])
                item_id = link['href'].split('/')[-1]

                if not item_existe(cache, item_id):
                    novos_itens.append({
                        'titulo': titulo,
                        'qualidade': qualidade,
                        'capa': imagem,
                        'id': item_id
                    })
            except (AttributeError, KeyError) as e:
                logger.warning(f"Erro ao processar item em {url}: {e}")
                continue

        if novos_itens:
            cache.extend(novos_itens)
            salvar_dados_json(cache_path, cache)
            logger.info(f"{len(novos_itens)} novos {tipo} adicionados ao cache")
        else:
            logger.info(f"Nenhum novo {tipo} encontrado")

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao atualizar {tipo} de {url}: {e}")

def validar_id(item_id):
    """Valida se o ID é alfanumérico e não vazio."""
    return item_id and item_id.isalnum()

def validar_pagina(pagina):
    """Valida e converte o número da página."""
    try:
        return max(1, int(pagina))
    except (ValueError, TypeError):
        return 1

@app.route('/')
def home():
    """Endpoint inicial da API."""
    return jsonify({"mensagem": "API Superflix está online 🚀"})

@app.route('/filme/detalhes')
def filme_detalhes():
    """Retorna detalhes de um filme pelo ID."""
    filme_id = request.args.get('id')
    if not validar_id(filme_id):
        logger.warning(f"ID de filme inválido: {filme_id}")
        return jsonify({'erro': 'ID inválido'}), 400

    filmes = carregar_dados_json(JSON_PATHS['filmes_pagina'])
    for filme in filmes:
        if filme.get('id') == filme_id:
            return jsonify(filme)

    logger.info(f"Filme com ID {filme_id} não encontrado")
    return jsonify({'erro': 'Filme não encontrado'}), 404

@app.route('/serie/detalhes')
def serie_detalhes():
    """Retorna detalhes de uma série pelo ID."""
    serie_id = request.args.get('id')
    if not validar_id(serie_id):
        logger.warning(f"ID de série inválido: {serie_id}")
        return jsonify({'erro': 'ID inválido'}), 400

    series = carregar_dados_json(JSON_PATHS['series_nomes'])
    for serie in series:
        if serie.get('id') == serie_id:
            return jsonify(serie)

    logger.info(f"Série com ID {serie_id} não encontrada")
    return jsonify({'erro': 'Série não encontrada'}), 404

@app.route('/codigos/series')
def codigos_series():
    """Retorna códigos de séries, com cache."""
    cache = carregar_dados_json(JSON_PATHS['code_series'])
    if cache:
        return jsonify({"codigos": ", ".join(cache.get("codigos", []))})

    try:
        url = urljoin(CONFIG['BASE_URL'], '/series/lista/')
        headers = {'User-Agent': CONFIG['USER_AGENT']}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        raw_codigos = soup.decode_contents().split('<br/>')
        codigos = [codigo.strip() for codigo in raw_codigos if codigo.strip().isdigit()]

        cache = {"codigos": codigos}
        salvar_dados_json(JSON_PATHS['code_series'], cache)
        logger.info("Códigos de séries atualizados")
        return jsonify({"codigos": ", ".join(codigos)})

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao carregar códigos de séries: {e}")
        return jsonify({'error': 'Erro ao carregar códigos de séries'}), 500

@app.route('/codigos/filmes')
def codigos_filmes():
    """Retorna códigos de filmes, com cache."""
    cache = carregar_dados_json(JSON_PATHS['code_filmes'])
    if cache:
        return jsonify({"codigos": ", ".join(cache.get("codigos", []))})

    try:
        url = urljoin(CONFIG['BASE_URL'], '/filmes/lista/')
        headers = {'User-Agent': CONFIG['USER_AGENT']}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        dados = soup.get_text()
        import re
        codigos = re.findall(r'tt\d+', dados)

        cache = {"codigos": codigos}
        salvar_dados_json(JSON_PATHS['code_filmes'], cache)
        logger.info("Códigos de filmes atualizados")
        return jsonify({"codigos": ", ".join(codigos)})

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao carregar códigos de filmes: {e}")
        return jsonify({'error': 'Erro ao carregar códigos de filmes'}), 500

@app.route('/filmes/novos')
def filmes_novos():
    """Retorna novos filmes, com atualização em segundo plano."""
    wait = request.args.get('wait', 'false').lower() == 'true'
    cache = carregar_dados_json(JSON_PATHS['filmes_novos'])

    thread = Thread(
        target=atualizar_dados,
        args=(urljoin(CONFIG['BASE_URL'], '/filmes'), JSON_PATHS['filmes_novos'], 'filmes')
    )
    thread.start()

    if wait:
        thread.join()
        cache = carregar_dados_json(JSON_PATHS['filmes_novos'])

    return jsonify(cache)

@app.route('/filmes/home')
def filmes_home():
    """Retorna filmes da página inicial."""
    cache = carregar_dados_json(JSON_PATHS['filmes_home'])
    return jsonify(cache)

@app.route('/filmes/pagina')
def filmes_pagina():
    """Retorna filmes paginados."""
    pagina = validar_pagina(request.args.get('pagina', 1))
    cache = carregar_dados_json(JSON_PATHS['filmes_pagina'])

    inicio = (pagina - 1) * CONFIG['ITEMS_PER_PAGE']
    fim = inicio + CONFIG['ITEMS_PER_PAGE']
    filmes_paginados = cache[inicio:fim]

    return jsonify(filmes_paginados)

@app.route('/filmes/pagina/atualizar')
def filmes_pagina_atualizar():
    """Atualiza a lista de filmes em segundo plano."""
    wait = request.args.get('wait', 'false').lower() == 'true'
    cache = carregar_dados_json(JSON_PATHS['filmes_pagina'])

    thread = Thread(
        target=atualizar_dados,
        args=(urljoin(CONFIG['BASE_URL'], '/filmes'), JSON_PATHS['filmes_pagina'], 'filmes')
    )
    thread.start()

    if wait:
        thread.join()
        cache = carregar_dados_json(JSON_PATHS['filmes_pagina'])

    return jsonify(cache)

@app.route('/series/pagina')
def series_pagina():
    """Retorna séries paginadas."""
    pagina = validar_pagina(request.args.get('pagina', 1))
    cache = carregar_dados_json(JSON_PATHS['series_nomes'])

    inicio = (pagina - 1) * CONFIG['ITEMS_PER_PAGE']
    fim = inicio + CONFIG['ITEMS_PER_PAGE']
    series_paginadas = cache[inicio:fim]

    return jsonify(series_paginadas)

@app.route('/series')
def series():
    """Retorna séries, com atualização em segundo plano."""
    wait = request.args.get('wait', 'false').lower() == 'true'
    cache = carregar_dados_json(JSON_PATHS['series'])
    if not isinstance(cache, list):
        logger.warning(f"Cache de séries inválido, retornando array vazio")
        cache = []

    thread = Thread(
        target=atualizar_dados,
        args=(urljoin('https://superflixapi.in', '/series'), JSON_PATHS['series'], 'séries')
    )
    thread.start()

    if wait:
        thread.join()
        cache = carregar_dados_json(JSON_PATHS['series'])
        if not isinstance(cache, list):
            cache = []

    return jsonify(cache)

@app.route('/buscar')
def buscar_nomes():
    """Busca filmes e séries por termo."""
    termo = request.args.get('q', '').lower()
    if not termo or len(termo) < 2:
        logger.warning(f"Termo de busca inválido: {termo}")
        return jsonify({'erro': 'Termo de busca inválido ou muito curto'}), 400

    filmes = carregar_dados_json(JSON_PATHS['filmes_pagina'])
    series = carregar_dados_json(JSON_PATHS['series_nomes'])

    resultados_filmes = [f for f in filmes if termo in f.get('titulo', '').lower()]
    resultados_series = [s for s in series if termo in s.get('titulo', '').lower()]
    resultados = resultados_filmes + resultados_series

    return jsonify(resultados[:10])

def atualizar_codigos_inicial():
    """Atualiza códigos de filmes e séries na inicialização."""
    with app.app_context():
        codigos_filmes()
        codigos_series()
        logger.info("Códigos iniciais atualizados")

if __name__ == '__main__':
    atualizar_codigos_inicial()
    app.run(debug=True, port=5001)