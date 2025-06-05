import os
import json
import logging
import asyncio
import aiohttp
import requests
import unicodedata
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, send_from_directory, has_request_context
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, generate_csrf
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

# Inicializar o Flask uma única vez
app = Flask(__name__, static_folder='static')

# Configurar chave secreta para CSRF e sessões
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-testing')

# Configurar chave de API
API_KEY = os.environ.get('API_KEY', 'x9k3m7p2q8w4z6t1')  # Valor padrão para testes locais

# Inicializar CSRF protection
csrf = CSRFProtect(app)

# Configurar CORS
CORS(app, resources={r"/*": {
    "origins": ["https://mystarmovies.online", "https://www.mystarmovies.online"],
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization", "X-CSRF-Token", "X-API-Key"]
}})

# Lock para sincronizar acesso a arquivos JSON
json_lock = Lock()

# Configurações centralizadas
CONFIG = {
    'BASE_URL': 'https://superflixapi.wales',
    'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'ITEMS_PER_PAGE': 50,
    'JSON_INDENT': 4,
    'BASE_DIR': os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
    'TEMP_DIR': 'temp',
    'FILMES_ENCONTRADOS_DIR': 'Filmes_Encontrados',
    'RATE_LIMIT_REQUESTS': 5,  # Máximo de 5 requisições por segundo
    'RATE_LIMIT_PERIOD': 1.0  # Período de 1 segundo
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
    'animes': os.path.join(TEMP_DIR, 'CodeAnimes.json'),
    'animes_nomes': os.path.join(FILMES_ENCONTRADOS_DIR, 'CodeAnimesNomes.json'),
    'filmes_novos': os.path.join(TEMP_DIR, 'Novosfilmes.json'),
    'series': os.path.join(TEMP_DIR, 'series.json'),
    'filmes_home': os.path.join(TEMP_DIR, 'Filmes.json'),
    'code_filmes': os.path.join(TEMP_DIR, 'CodeFilmes.json'),
    'code_series': os.path.join(TEMP_DIR, 'CodeSeries.json')
}

# Função para verificar a chave de API
def check_api_key():
    # Pular verificação se não houver contexto de requisição (ex.: inicialização)
    if not has_request_context():
        return None
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != API_KEY:
        logger.warning(f"Chave de API inválida ou ausente: {api_key}")
        return jsonify({'erro': 'Chave de API inválida ou ausente'}), 401
    return None

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
            logger.info(f"Tentando salvar dados em {caminho}")
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
    """Função genérica para atualizar filmes, séries ou animes via scraping assíncrono."""
    cache = carregar_dados_json(cache_path)
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': CONFIG['USER_AGENT'],
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5'
            }
            logger.info(f"Tentando acessar URL: {url}")
            async with session.get(url, headers=headers) as response:
                logger.info(f"Status da resposta: {response.status}")
                response.raise_for_status()
                content = await response.text()
                logger.info(f"Primeiros 500 caracteres do conteúdo: {content[:500]}")

            soup = BeautifulSoup(content, 'html.parser')
            novos_itens = []
            detalhes_tasks = []

            # Criar um semáforo para limitar requisições simultâneas
            semaphore = asyncio.Semaphore(CONFIG['RATE_LIMIT_REQUESTS'])

            logger.info(f"Procurando pôsteres na página de {tipo}")
            posters = soup.find_all('div', class_='poster')
            logger.info(f"Encontrados {len(posters)} pôsteres")

            for poster in posters:
                try:
                    titulo = poster.find('span', class_='title')
                    qualidade = poster.find('span', class_='year')
                    imagem = poster.find('img')
                    link = poster.find('a', class_='btn')

                    if not all([titulo, qualidade, imagem, link]):
                        logger.warning(f"Pôster incompleto encontrado: {poster.get_text(strip=True)[:100]}")
                        continue

                    titulo = titulo.get_text(strip=True)
                    qualidade = qualidade.get_text(strip=True)
                    imagem = urljoin(CONFIG['BASE_URL'], imagem['src'])
                    item_id = link['href'].split('/')[-1]
                    url_detalhes = urljoin(CONFIG['BASE_URL'], link['href'])

                    if not item_existe(cache, item_id):
                        logger.info(f"Novo {tipo} encontrado: {titulo} (ID: {item_id})")
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
                logger.info(f"Extraindo detalhes de {len(novos_itens)} {tipo}")
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

def normalize_text(text):
    """Normaliza texto removendo acentos e convertendo para minúsculas."""
    if not text:
        return ''
    # Remove acentos e converte para minúsculas
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('ascii')
    return text.lower().strip()



@app.route('/animes/pagina')
def animes_pagina():
    """Retorna animes paginados com metadados."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    pagina = validar_pagina(request.args.get('pagina', 1))
    animes = carregar_dados_json(JSON_PATHS['animes_nomes'])

    if not animes:
        logger.info("Nenhum anime encontrado")
        return jsonify({
            'resultados': [],
            'total': 0,
            'total_paginas': 1,
            'pagina_atual': pagina
        }), 200

    # Paginação
    inicio = (pagina - 1) * CONFIG['ITEMS_PER_PAGE']
    fim = inicio + CONFIG['ITEMS_PER_PAGE']
    animes_paginados = animes[inicio:fim]

    total_itens = len(animes)
    total_paginas = (total_itens + CONFIG['ITEMS_PER_PAGE'] - 1) // CONFIG['ITEMS_PER_PAGE']

    logger.info(f"Retornando {len(animes_paginados)} animes da página {pagina}/{total_paginas}")

    return jsonify({
        'resultados': animes_paginados,
        'total': total_itens,
        'total_paginas': total_paginas,
        'pagina_atual': pagina
    })


@app.route('/codigos/animes')
def codigos_animes():
    """Retorna códigos de animes, com cache."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    cache = carregar_dados_json(JSON_PATHS['animes'])
    if cache:
        logger.info(f"Retornando {len(cache.get('codigos', []))} códigos do cache")
        return jsonify({"codigos": ", ".join(cache.get("codigos", []))})

    try:
        url = urljoin(CONFIG['BASE_URL'], '/animes/export/')
        headers = {
            'User-Agent': CONFIG['USER_AGENT'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }
        logger.info(f"Tentando acessar URL: {url}")
        response = requests.get(url, headers=headers, timeout=5)
        logger.info(f"Status da resposta: {response.status_code}")
        response.raise_for_status()

        # Extrair o texto bruto
        content = response.text
        logger.info(f"Primeiros 500 caracteres do conteúdo: {content[:500]}")

        # Dividir por <br> e limpar os códigos
        raw_codigos = content.split('<br>')
        logger.info(f"Encontrados {len(raw_codigos)} códigos brutos")
        codigos = [codigo.strip() for codigo in raw_codigos if codigo.strip().isdigit()]
        logger.info(f"Encontrados {len(codigos)} códigos válidos após validação")

        if not codigos:
            logger.warning("Nenhum código válido encontrado no conteúdo")

        cache = {"codigos": codigos}
        salvar_dados_json(JSON_PATHS['animes'], cache)
        logger.info("Códigos de animes atualizados")
        return jsonify({"codigos": ", ".join(codigos)})

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao carregar códigos de animes: {e}")
        return jsonify({'error': 'Erro ao carregar códigos de animes'}), 500
    

@app.route('/health', methods=['GET'])
def health_check():
    """Rota para verificar se o servidor está ativo."""
    return jsonify({"status": "ok"}), 200

@app.route('/get-csrf-token', methods=['GET'])
def get_csrf_token():
    """Retorna um token CSRF para o frontend."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error
    token = generate_csrf()
    return jsonify({'csrf_token': token})

@app.route('/filme/detalhes')
def filme_detalhes():
    """Retorna detalhes de um filme pelo ID."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

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
    auth_error = check_api_key()
    if auth_error:
        return auth_error

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
    auth_error = check_api_key()
    if auth_error:
        return auth_error

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
def codigos_filmes():
    """Retorna códigos de filmes, com cache."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

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
def filmes_novos():
    """Retorna novos filmes, com atualização em segundo plano."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

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
def filmes_home():
    """Retorna filmes da página inicial."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    cache = carregar_dados_json(JSON_PATHS['filmes_home'])
    return jsonify(cache)

@app.route('/filmes/pagina')
def filmes_pagina():
    """Retorna filmes paginados com metadados."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

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
def filmes_pagina_atualizar():
    """Atualiza a lista de filmes em segundo plano."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

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
def series_pagina():
    """Retorna séries paginadas com metadados."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

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
def series():
    """Retorna séries, com atualização em segundo plano."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

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
def buscar_nomes():
    """Busca filmes e séries por termo, com suporte à paginação."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    termo = request.args.get('q', '').strip()
    pagina = validar_pagina(request.args.get('pagina', 1))

    if not termo or len(termo) < 2:
        logger.warning(f"Termo de busca inválido: {termo}")
        return jsonify({'erro': 'Termo de busca inválido ou muito curto'}), 400

    termo_normalizado = normalize_text(termo)

    filmes = carregar_dados_json(JSON_PATHS['filmes_pagina'])
    series = carregar_dados_json(JSON_PATHS['series_nomes'])

    # Busca parcial com normalização
    resultados_filmes = [
        f for f in filmes
        if termo_normalizado in normalize_text(f.get('titulo', ''))
        or termo_normalizado in normalize_text(f.get('titulo_original', ''))
    ]
    resultados_series = [
        s for s in series
        if termo_normalizado in normalize_text(s.get('titulo', ''))
        or termo_normalizado in normalize_text(s.get('titulo_original', ''))
    ]
    resultados = resultados_filmes + resultados_series

    if not resultados:
        logger.info(f"Nenhum filme ou série encontrado para o termo: {termo}")
        return jsonify({
            'resultados': [],
            'total': 0,
            'total_paginas': 1,
            'pagina_atual': pagina
        }), 200

    # Paginação
    inicio = (pagina - 1) * CONFIG['ITEMS_PER_PAGE']
    fim = inicio + CONFIG['ITEMS_PER_PAGE']
    resultados_paginados = resultados[inicio:fim]

    total_itens = len(resultados)
    total_paginas = (total_itens + CONFIG['ITEMS_PER_PAGE'] - 1) // CONFIG['ITEMS_PER_PAGE']

    logger.info(f"Busca por '{termo}' retornou {total_itens} resultados, página {pagina}/{total_paginas}")

    return jsonify({
        'resultados': resultados_paginados,
        'total': total_itens,
        'total_paginas': total_paginas,
        'pagina_atual': pagina
    })

@app.route('/buscar_por_genero')
def buscar_por_genero():
    """Busca filmes e séries por gênero, com paginação."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

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
def buscar_generos():
    """Retorna sugestões de gêneros com base no termo de busca."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

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
    """Serve arquivos estáticos."""
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    return send_from_directory(app.static_folder, path)

def atualizar_codigos_inicial():
    """Atualiza códigos de filmes, séries e animes na inicialização e pré-carrega dados populares."""
    with app.app_context():
        codigos_filmes()
        codigos_series()
        codigos_animes()  # Chama a nova rota
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