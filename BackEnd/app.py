import os
import json
import logging
import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask import abort
from threading import Thread, Lock
from urllib.parse import urljoin
from functools import wraps

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

CORS(app, resources={r"/*": {
    "origins": "https://filmes-frontend.vercel.app",
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"]
}})


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
    'FILMES_ENCONTRADOS_DIR': 'Filmes_Encontrados',
    'RATE_LIMIT_REQUESTS': 5,  # Máximo de 5 requisições por segundo
    'RATE_LIMIT_PERIOD': 1.0,  # Período de 1 segundo
    'API_KEY': os.getenv('SUPERFLIX_API_KEY', 'aW9!7sd9e8e98jzK$p3Rt6yU*IUHhusdhibH2nCvE8q') 
}

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('Authorization') or request.args.get('key')
        if key != CONFIG['API_KEY']:
            logger.warning("Acesso negado: chave de API inválida")
            abort(401, description="Chave de API inválida ou ausente")
        return f(*args, **kwargs)
    return decorated

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
        logger.warning(f"Arquivo {caminho} não encontrado")
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

async def extrair_detalhes_item(session, url_detalhes, semaphore):
    """Extrai detalhes adicionais de um filme ou série a partir da página de detalhes (assíncrono)."""
    async with semaphore:
        try:
            headers = {'User-Agent': CONFIG['USER_AGENT']}
            async with session.get(url_detalhes, headers=headers) as response:
                response.raise_for_status()
                content = await response.text()

            soup = BeautifulSoup(content, 'html.parser')

            # Extrair título original
            titulo_original_elem = soup.find('span', class_='original-title') or soup.find('h2', class_='original-title')
            titulo_original = titulo_original_elem.get_text(strip=True) if titulo_original_elem else None

            # Extrair descrição
            descricao_elem = soup.find('div', class_='description') or soup.find('p', class_='synopsis')
            descricao = descricao_elem.get_text(strip=True) if descricao_elem else ""

            # Extrair gêneros
            generos_elem = soup.find('div', class_='genres') or soup.find('ul', class_='genres-list')
            generos = []
            if generos_elem:
                generos = [g.get_text(strip=True) for g in generos_elem.find_all(['span', 'li'])]
            generos = generos if generos else []

            # Atraso para respeitar o rate limit
            await asyncio.sleep(CONFIG['RATE_LIMIT_PERIOD'] / CONFIG['RATE_LIMIT_REQUESTS'])

            return {
                'titulo_original': titulo_original,
                'descricao': descricao,
                'generos': generos
            }
        except aiohttp.ClientError as e:
            logger.error(f"Erro ao extrair detalhes de {url_detalhes}: {e}")
            return {
                'titulo_original': None,
                'descricao': "",
                'generos': []
            }

async def atualizar_dados(url, cache_path, tipo='filmes'):
    """Função genérica para atualizar filmes ou séries via scraping assíncrono."""
    cache = carregar_dados_json(cache_path)
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': CONFIG['USER_AGENT']}
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                content = await response.text()

            soup = BeautifulSoup(content, 'html.parser')
            novos_itens = []
            detalhes_tasks = []

            # Criar um semáforo para limitar requisições simultâneas
            semaphore = asyncio.Semaphore(CONFIG['RATE_LIMIT_REQUESTS'])

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
                        # Agendar a extração de detalhes
                        detalhes_tasks.append(extrair_detalhes_item(session, url_detalhes, semaphore))
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
                # Executar todas as tarefas de detalhes em paralelo
                detalhes_results = await asyncio.gather(*detalhes_tasks, return_exceptions=True)
                for i, detalhes in enumerate(detalhes_results):
                    if isinstance(detalhes, dict):
                        novos_itens[i].update({
                            'titulo_original': detalhes['titulo_original'],
                            'descricao': detalhes['descricao'],
                            'generos': detalhes['generos']
                        })

                cache.extend(novos_itens)
                salvar_dados_json(cache_path, cache)
                logger.info(f"{len(novos_itens)} novos {tipo} adicionados ao cache")
            else:
                logger.info(f"Nenhum novo {tipo} encontrado")

    except aiohttp.ClientError as e:
        logger.error(f"Erro ao atualizar {tipo} de {url}: {e}")

def run_async_in_thread(coro):
    """Executa uma corrotina assíncrona em uma thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()

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
@require_api_key
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
@require_api_key
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
@require_api_key
def codigos_series():
    """Retorna códigos de séries, com cache."""
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
        return jsonify({'error': 'Erro ao carregar códigos de séries'}), 500

@app.route('/codigos/filmes')
@require_api_key
def codigos_filmes():
    """Retorna códigos de filmes, com cache."""
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
        return jsonify({'error': 'Erro ao carregar códigos de filmes'}), 500

@app.route('/filmes/novos')
@require_api_key
def filmes_novos():
    """Retorna novos filmes, com atualização em segundo plano."""
    wait = request.args.get('wait', 'false').lower() == 'true'
    cache = carregar_dados_json(JSON_PATHS['filmes_novos'])

    thread = Thread(
        target=run_async_in_thread,
        args=(atualizar_dados(urljoin(CONFIG['BASE_URL'], '/filmes'), JSON_PATHS['filmes_novos'], 'filmes'),)
    )
    thread.start()

    if wait:
        thread.join()
        cache = carregar_dados_json(JSON_PATHS['filmes_novos'])

    return jsonify(cache)

@app.route('/filmes/home')
@require_api_key
def filmes_home():
    """Retorna filmes da página inicial."""
    cache = carregar_dados_json(JSON_PATHS['filmes_home'])
    return jsonify(cache)

@app.route('/filmes/pagina')
@require_api_key
def filmes_pagina():
    """Retorna filmes paginados com metadados."""
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
@require_api_key
def filmes_pagina_atualizar():
    """Atualiza a lista de filmes em segundo plano."""
    wait = request.args.get('wait', 'false').lower() == 'true'
    cache = carregar_dados_json(JSON_PATHS['filmes_pagina'])

    thread = Thread(
        target=run_async_in_thread,
        args=(atualizar_dados(urljoin(CONFIG['BASE_URL'], '/filmes'), JSON_PATHS['filmes_pagina'], 'filmes'),)
    )
    thread.start()

    if wait:
        thread.join()
        cache = carregar_dados_json(JSON_PATHS['filmes_pagina'])

    return jsonify(cache)

@app.route('/series/pagina')
@require_api_key
def series_pagina():
    """Retorna séries paginadas com metadados."""
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
@require_api_key
def series():
    """Retorna séries, com atualização em segundo plano."""
    wait = request.args.get('wait', 'false').lower() == 'true'
    cache = carregar_dados_json(JSON_PATHS['series'])

    thread = Thread(
        target=run_async_in_thread,
        args=(atualizar_dados(urljoin(CONFIG['BASE_URL'], '/series'), JSON_PATHS['series'], 'séries'),)
    )
    thread.start()

    if wait:
        thread.join()
        cache = carregar_dados_json(JSON_PATHS['series'])

    return jsonify(cache)

@app.route('/buscar')
@require_api_key
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

@app.route('/buscar_por_genero')
@require_api_key
def buscar_por_genero():
    """Busca filmes e séries por gênero, com paginação."""
    genero = request.args.get('genero', '').lower()
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
        if isinstance(filme.get('generos'), list) and any(genero.lower() in g.lower() for g in filme.get('generos', []))
    ]
    resultados_series = [
        serie for serie in series
        if isinstance(serie.get('generos'), list) and any(genero.lower() in g.lower() for g in serie.get('generos', []))
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
@require_api_key
def buscar_generos():
    """Retorna sugestões de gêneros com base no termo de busca."""
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
@require_api_key
def serve_static(path):
    """Serve arquivos estáticos."""
    return send_from_directory(app.static_folder, path)

def atualizar_codigos_inicial():
    """Atualiza códigos de filmes e séries na inicialização e pré-carrega filmes populares."""
    with app.app_context():
        codigos_filmes()
        codigos_series()
        # Pré-carregar filmes populares
        run_async_in_thread(
            atualizar_dados(
                urljoin(CONFIG['BASE_URL'], '/filmes'),
                JSON_PATHS['filmes_pagina'],
                'filmes'
            )
        )
        run_async_in_thread(
            atualizar_dados(
                urljoin(CONFIG['BASE_URL'], '/series'),
                JSON_PATHS['series_nomes'],
                'séries'
            )
        )
        logger.info("Códigos iniciais e filmes/séries populares atualizados")

if __name__ == '__main__':
    atualizar_codigos_inicial()
    app.run(debug=True, port=5001)