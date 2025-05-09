import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from threading import Thread, Lock
from urllib.parse import urljoin, urlparse
import bleach
from functools import wraps
from collections import defaultdict
from time import time

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

app = Flask(__name__, static_folder='static')
app.config.update(
    SESSION_COOKIE_SECURE=True,  # Cookies only sent over HTTPS
    SESSION_COOKIE_HTTPONLY=True,  # Prevent JavaScript access
    SESSION_COOKIE_SAMESITE='Lax'  # Mitigate CSRF
)

# Restrict CORS to specific origins
ALLOWED_ORIGINS = [
    "https://filmes-flask.onrender.com",  # Your Render frontend URL
    "http://localhost:3000",  # Local development
    "http://127.0.0.1:3000"
]
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

# In-memory rate limit storage
RATE_LIMITS = defaultdict(list)
REQUEST_LIMIT = 50  # Max requests per IP
TIME_WINDOW = 60  # 60 seconds

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        now = time()
        # Remove requests older than TIME_WINDOW
        RATE_LIMITS[client_ip] = [t for t in RATE_LIMITS[client_ip] if now - t < TIME_WINDOW]
        # Check if limit is exceeded
        if len(RATE_LIMITS[client_ip]) >= REQUEST_LIMIT:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return jsonify({'erro': 'Limite de requisições excedido. Tente novamente mais tarde.'}), 429
        # Add current request timestamp
        RATE_LIMITS[client_ip].append(now)
        return f(*args, **kwargs)
    return decorated_function

# Lock para sincronizar acesso a arquivos JSON
json_lock = Lock()

# Configurações centralizadas
CONFIG = {
    'BASE_URL': 'https://superflixapi.nexus/filmes',
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

# Garante que os diretórios existem com permissões seguras
os.makedirs(TEMP_DIR, mode=0o700, exist_ok=True)
os.makedirs(FILMES_ENCONTRADOS_DIR, mode=0o700, exist_ok=True)

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

def is_safe_path(filepath):
    """Verifica se o caminho está dentro do diretório base."""
    base_dir = CONFIG['BASE_DIR']
    abs_filepath = os.path.abspath(filepath)
    return abs_filepath.startswith(os.path.abspath(base_dir))

def carregar_dados_json(caminho):
    """Carrega dados de um arquivo JSON com sincronização."""
    if not is_safe_path(caminho):
        logger.error(f"Tentativa de acesso a caminho inválido: {caminho}")
        return []
    with json_lock:
        if os.path.exists(caminho):
            try:
                with open(caminho, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao decodificar {caminho}: {e}")
                return []
        logger.warning(f"Arquivo {caminho} não encontrado")
        return []

def salvar_dados_json(caminho, dados):
    """Salva dados em um arquivo JSON com sincronização."""
    if not is_safe_path(caminho):
        logger.error(f"Tentativa de escrita em caminho inválido: {caminho}")
        return
    with json_lock:
        try:
            with open(caminho, 'w', encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=CONFIG['JSON_INDENT'])
            os.chmod(caminho, 0o600)  # Read/write for owner only
            logger.info(f"Arquivo {caminho} salvo com sucesso")
        except Exception as e:
            logger.error(f"Erro ao salvar {caminho}: {e}")

def item_existe(lista, item_id):
    """Verifica se um item com o ID existe na lista."""
    return any(item.get('id') == item_id for item in lista)

def extrair_detalhes_item(url_detalhes):
    """Extrai detalhes adicionais de um filme ou série a partir da página de detalhes."""
    parsed_url = urlparse(url_detalhes)
    expected_netloc = urlparse(CONFIG['BASE_URL']).netloc
    if parsed_url.netloc != expected_netloc:
        logger.error(f"URL inválida para detalhes: {url_detalhes}")
        return {'titulo_original': None, 'descricao': "", 'generos': []}

    try:
        headers = {'User-Agent': CONFIG['USER_AGENT']}
        response = requests.get(url_detalhes, headers=headers, timeout=5)
        response.raise_for_status()

        if 'text/html' not in response.headers.get('Content-Type', ''):
            logger.error(f"Resposta não é HTML: {url_detalhes}")
            return {'titulo_original': None, 'descricao': "", 'generos': []}

        soup = BeautifulSoup(response.content, 'html.parser')
        titulo_original_elem = soup.find('span', class_='original-title') or soup.find('h2', class_='original-title')
        titulo_original = titulo_original_elem.get_text(strip=True) if titulo_original_elem else None
        descricao_elem = soup.find('div', class_='description') or soup.find('p', class_='synopsis')
        descricao = descricao_elem.get_text(strip=True) if descricao_elem else ""
        generos_elem = soup.find('div', class_='genres') or soup.find('ul', class_='genres-list')
        generos = [g.get_text(strip=True) for g in generos_elem.find_all(['span', 'li'])] if generos_elem else []

        return {
            'titulo_original': titulo_original,
            'descricao': descricao,
            'generos': generos
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao extrair detalhes de {url_detalhes}: {e}")
        return {'titulo_original': None, 'descricao': "", 'generos': []}

def atualizar_dados(url, cache_path, tipo='filmes'):
    """Função genérica para atualizar filmes ou séries via scraping."""
    cache = carregar_dados_json(cache_path)
    try:
        headers = {'User-Agent': CONFIG['USER_AGENT']}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        novos_itens = []

        for poster in soup.find_all('div', class_='poster'):
            try:
                titulo = poster.find('span', class_='title')
                qualidade = poster.find('span', class_='year')
                imagem = poster.find('img')
                link = poster.find('a', class_='btn')

                if not all([titulo, qualidade, imagem, link]):
                    continue

                titulo = titulo.get_text(strip=True)
                qualidade = qualidade.get_text(strip=True)
                imagem = urljoin(CONFIG['BASE_URL'], imagem['src'])
                item_id = link['href'].split('/')[-1]
                url_detalhes = urljoin(CONFIG['BASE_URL'], link['href'])

                if not item_existe(cache, item_id):
                    detalhes = extrair_detalhes_item(url_detalhes)
                    novos_itens.append({
                        'titulo': titulo,
                        'titulo_original': detalhes['titulo_original'],
                        'qualidade': qualidade,
                        'capa': imagem,
                        'id': item_id,
                        'descricao': detalhes['descricao'],
                        'generos': detalhes['generos']
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

    except requests.exceptions.Timeout:
        logger.error(f"Timeout ao atualizar {tipo} de {url}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao atualizar {tipo} de {url}: {e}")

def validar_id(item_id):
    """Valida se o ID é alfanumérico, não vazio e tem comprimento razoável."""
    return bool(item_id and item_id.isalnum() and len(item_id) <= 50)

def validar_pagina(pagina):
    """Valida e converte o número da página."""
    try:
        return max(1, int(pagina))
    except (ValueError, TypeError):
        return 1

@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f"Erro não tratado: {str(error)}", exc_info=True)
    return jsonify({'erro': 'Erro interno do servidor. Tente novamente mais tarde.'}), 500

@app.route('/')
def home():
    return jsonify({"mensagem": "API Superflix está online 🚀"})

@app.route('/filme/detalhes')
@rate_limit
def filme_detalhes():
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
@rate_limit
def serie_detalhes():
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
@rate_limit
def codigos_series():
    cache = carregar_dados_json(JSON_PATHS['code_series'])
    if cache:
        return jsonify({"codigos": ", ".join(cache.get("codigos", []))})

    try:
        url = urljoin(CONFIG['BASE_URL'], '/series/lista/')
        headers = {'User-Agent': CONFIG['USER_AGENT']}
        response = requests.get(url, headers=headers, timeout=5)
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
        return jsonify({'erro': 'Não foi possível carregar os códigos de séries'}), 500

@app.route('/codigos/filmes')
@rate_limit
def codigos_filmes():
    cache = carregar_dados_json(JSON_PATHS['code_filmes'])
    if cache:
        return jsonify({"codigos": ", ".join(cache.get("codigos", []))})

    try:
        url = urljoin(CONFIG['BASE_URL'], '/filmes/lista/')
        headers = {'User-Agent': CONFIG['USER_AGENT']}
        response = requests.get(url, headers=headers, timeout=5)
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
        return jsonify({'erro': 'Não foi possível carregar os códigos de filmes'}), 500

@app.route('/filmes/novos')
@rate_limit
def filmes_novos():
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
@rate_limit
def filmes_home():
    cache = carregar_dados_json(JSON_PATHS['filmes_home'])
    return jsonify(cache)

@app.route('/filmes/pagina')
@rate_limit
def filmes_pagina():
    pagina = validar_pagina(request.args.get('pagina', 1))
    cache = carregar_dados_json(JSON_PATHS['filmes_pagina'])

    inicio = (pagina - 1) * CONFIG['ITEMS_PER_PAGE']
    fim = inicio + CONFIG['ITEMS_PER_PAGE']
    filmes_paginados = cache[inicio:fim]

    total_itens = len(cache)
    total_paginas = (total_itens + CONFIG['ITEMS_PER_PAGE'] - 1) // CONFIG['ITEMS_PER_PAGE']

    return jsonify({
        'filmes': filmes_paginados,
        'total_itens': total_itens,
        'total_paginas': total_paginas,
        'pagina_atual': pagina
    })

@app.route('/filmes/pagina/atualizar')
@rate_limit
def filmes_pagina_atualizar():
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
@rate_limit
def series_pagina():
    pagina = validar_pagina(request.args.get('pagina', 1))
    cache = carregar_dados_json(JSON_PATHS['series_nomes'])

    inicio = (pagina - 1) * CONFIG['ITEMS_PER_PAGE']
    fim = inicio + CONFIG['ITEMS_PER_PAGE']
    series_paginadas = cache[inicio:fim]

    total_itens = len(cache)
    total_paginas = (total_itens + CONFIG['ITEMS_PER_PAGE'] - 1) // CONFIG['ITEMS_PER_PAGE']

    return jsonify({
        'series': series_paginadas,
        'total_itens': total_itens,
        'total_paginas': total_paginas,
        'pagina_atual': pagina
    })

@app.route('/series')
@rate_limit
def series():
    wait = request.args.get('wait', 'false').lower() == 'true'
    cache = carregar_dados_json(JSON_PATHS['series'])

    thread = Thread(
        target=atualizar_dados,
        args=(urljoin(CONFIG['BASE_URL'], '/series'), JSON_PATHS['series'], 'séries')
    )
    thread.start()

    if wait:
        thread.join()
        cache = carregar_dados_json(JSON_PATHS['series'])

    return jsonify(cache)

@app.route('/buscar')
@rate_limit
def buscar_nomes():
    termo = request.args.get('q', '').lower()
    termo = bleach.clean(termo, tags=[], strip=True)
    if not termo or len(termo) < 2:
        logger.warning(f"Termo de busca inválido: {termo}")
        return jsonify({'erro': 'Termo de busca inválido ou muito curto'}), 400

    filmes = carregar_dados_json(JSON_PATHS['filmes_pagina'])
    series = carregar_dados_json(JSON_PATHS['series_nomes'])

    resultados_filmes = [f for f in filmes if termo in f.get('titulo', '').lower()]
    resultados_series = [s for s in series if termo in s.get('titulo', '').lower()]
    resultados = resultados_filmes + resultados_series

    return jsonify(resultados[:10])

@app.route('/buscar_por_genero')
@rate_limit
def buscar_por_genero():
    genero = request.args.get('genero', '').lower()
    genero = bleach.clean(genero, tags=[], strip=True)
    pagina = validar_pagina(request.args.get('pagina', 1))

    if not genero:
        logger.warning("Gênero não fornecido")
        return jsonify({'erro': 'Gênero não fornecido'}), 400

    filmes = carregar_dados_json(JSON_PATHS['filmes_pagina'])
    series = carregar_dados_json(JSON_PATHS['series_nomes'])

    for filme in filmes:
        if 'generos' not in filme or not filme['generos']:
            logger.warning(f"Filme sem gêneros: {filme.get('titulo', 'Desconhecido')} (ID: {filme.get('id', 'N/A')})")
    for serie in series:
        if 'generos' not in serie or not serie['generos']:
            logger.warning(f"Série sem gêneros: {serie.get('titulo', 'Desconhecido')} (ID: {serie.get('id', 'N/A')})")

    resultados_filmes = [
        filme for filme in filmes
        if (isinstance(filme.get('generos'), list) and any(genero.lower() in g.lower() for g in filme.get('generos', [])))
        or (isinstance(filme.get('generos'), str) and genero.lower() in filme.get('generos', '').lower())
    ]
    resultados_series = [
        serie for serie in series
        if (isinstance(serie.get('generos'), list) and any(genero.lower() in g.lower() for g in serie.get('generos', [])))
        or (isinstance(serie.get('generos'), str) and genero.lower() in serie.get('generos', '').lower())
    ]

    resultados = resultados_filmes + resultados_series

    if not resultados:
        logger.info(f"Nenhum filme ou série encontrado para o gênero: {genero}")
        return jsonify({
            'mensagem': f'Nenhum resultado para o gênero {genero}',
            'resultados': [],
            'total': 0,
            'total_paginas': 0,
            'pagina_atual': pagina
        }), 200

    inicio = (pagina - 1) * CONFIG['ITEMS_PER_PAGE']
    fim = inicio + CONFIG['ITEMS_PER_PAGE']
    resultados_paginados = resultados[inicio:fim]

    total_itens = len(resultados)
    total_paginas = (total_itens + CONFIG['ITEMS_PER_PAGE'] - 1) // CONFIG['ITEMS_PER_PAGE']

    return jsonify({
        'resultados': resultados_paginados,
        'total': total_itens,
        'total_paginas': total_paginas,
        'pagina_atual': pagina
    })

@app.route('/buscar_generos')
@rate_limit
def buscar_generos():
    termo = request.args.get('q', '').lower()
    generos = [
        "Action", "Animation", "Adventure", "Comedy", "Crime", "Drama", "Family",
        "Fantasy", "Western", "Science", "war", "History",
        "Lançamentos", "Mystery", "Music", "Nacional", "Romance", "Suspense", "Horror",
    ]

    if not termo:
        return jsonify(generos)

    sugestoes = [g for g in generos if termo in g.lower()]
    return jsonify(sugestoes)

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

def atualizar_codigos_inicial():
    with app.app_context():
        codigos_filmes()
        codigos_series()
        atualizar_dados(
            urljoin(CONFIG['BASE_URL'], '/filmes'),
            JSON_PATHS['filmes_pagina'],
            'filmes'
        )
        atualizar_dados(
            urljoin(CONFIG['BASE_URL'], '/series'),
            JSON_PATHS['series_nomes'],
            'séries'
        )
        logger.info("Códigos iniciais e filmes/séries populares atualizados")

if __name__ == '__main__':
    debug = os.getenv('FLASK_ENV') == 'development'
    atualizar_codigos_inicial()
    app.run(debug=debug, port=5001)