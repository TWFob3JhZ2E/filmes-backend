import os
import json
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Rate limiting
limiter = Limiter(app=app, key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

# Directories
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
FILMES_ENCONTRADOS_DIR = os.path.join(BASE_DIR, 'Filmes_Encontrados')
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(FILMES_ENCONTRADOS_DIR, exist_ok=True)

# JSON file paths
JSON_PATHS = {
    'filmes_pagina': os.path.join(FILMES_ENCONTRADOS_DIR, 'CodeFilmesNomes.json'),
    'series_nomes': os.path.join(FILMES_ENCONTRADOS_DIR, 'CodeSeriesNomes.json'),
    'filmes_novos': os.path.join(TEMP_DIR, 'Novosfilmes.json'),
    'series': os.path.join(TEMP_DIR, 'series.json'),
    'filmes_home': os.path.join(TEMP_DIR, 'Filmes.json'),
    'code_filmes': os.path.join(TEMP_DIR, 'CodeFilmes.json'),
    'code_series': os.path.join(TEMP_DIR, 'CodeSeries.json'),
}

# Cache TTL (1 hour)
CACHE_TTL = timedelta(hours=1)

def carregar_dados_json(caminho):
    """Load JSON data from file with cache validation."""
    if not os.path.exists(caminho):
        return {'data': [], 'timestamp': None}
    
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            data = json.load(f)
            timestamp = data.get('timestamp')
            if timestamp and (datetime.now() - datetime.fromisoformat(timestamp)) > CACHE_TTL:
                logger.info(f"Cache expired for {caminho}")
                return {'data': [], 'timestamp': None}
            return data
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error decoding JSON {caminho}: {e}")
        return {'data': [], 'timestamp': None}

def salvar_dados_json(caminho, dados):
    """Save JSON data to file with timestamp."""
    try:
        data = {
            'data': dados,
            'timestamp': datetime.now().isoformat()
        }
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.info(f"Saved file {caminho}")
    except Exception as e:
        logger.error(f"Error saving JSON {caminho}: {e}")

def item_existe(lista, item_id):
    """Check if item exists in list by ID."""
    return any(item['id'] == item_id for item in lista)

async def fetch_url(url):
    """Fetch URL content asynchronously."""
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.text()
                logger.error(f"Failed to fetch {url}: Status {response.status}")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

@app.route('/')
def home():
    """API home endpoint."""
    return jsonify({"mensagem": "API Superflix está online 🚀"})

@app.route('/filme/detalhes')
@limiter.limit("10 per minute")
def filme_detalhes():
    """Get movie details by ID."""
    filme_id = request.args.get('id')
    if not filme_id:
        return jsonify({'erro': 'ID do filme é obrigatório'}), 400
    
    filmes = carregar_dados_json(JSON_PATHS['filmes_pagina'])['data']
    for filme in filmes:
        if filme['id'] == filme_id:
            return jsonify(filme)
    
    return jsonify({'erro': 'Filme não encontrado'}), 404

@app.route('/serie/detalhes')
@limiter.limit("10 per minute")
def serie_detalhes():
    """Get series details by ID."""
    serie_id = request.args.get('id')
    if not serie_id:
        return jsonify({'erro': 'ID da série é obrigatório'}), 400
    
    series = carregar_dados_json(JSON_PATHS['series_nomes'])['data']
    for serie in series:
        if serie['id'] == serie_id:
            return jsonify(serie)
    
    return jsonify({'erro': 'Série não encontrada'}), 404

async def fetch_codigos(url, cache_path, is_series=False):
    """Fetch and cache codes for movies or series."""
    cache = carregar_dados_json(cache_path)
    if cache['data']:
        return cache['data'].get("codigos", [])
    
    content = await fetch_url(url)
    if not content:
        return []
    
    soup = BeautifulSoup(content, 'html.parser')
    if is_series:
        raw_codigos = soup.decode_contents().split('<br/>')
        codigos = [codigo.strip() for codigo in raw_codigos if codigo.strip().isdigit()]
    else:
        import re
        codigos = re.findall(r'tt\d+', soup.get_text())
    
    salvar_dados_json(cache_path, {"codigos": codigos})
    return codigos

@app.route('/codigos/series')
@limiter.limit("5 per minute")
def codigos_series():
    """Get series codes."""
    async def get_codigos():
        codigos = await fetch_codigos(
            "https://superflixapi.in/series/lista/",
            JSON_PATHS['code_series'],
            is_series=True
        )
        return ", ".join(codigos)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    codigos = loop.run_until_complete(get_codigos())
    loop.close()
    
    return jsonify({"codigos": codigos}) if codigos else jsonify({'error': 'Erro ao carregar códigos de séries'}), 500

@app.route('/codigos/filmes')
@limiter.limit("5 per minute")
def codigos_filmes():
    """Get movie codes."""
    async def get_codigos():
        codigos = await fetch_codigos(
            "https://superflixapi.in/filmes/lista/",
            JSON_PATHS['code_filmes']
        )
        return ", ".join(codigos)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    codigos = loop.run_until_complete(get_codigos())
    loop.close()
    
    return jsonify({"codigos": codigos}) if codigos else jsonify({'error': 'Erro ao carregar códigos de filmes'}), 500

async def atualizar_filmes_series(url, cache_path, is_series=False):
    """Update movies or series data."""
    cache = carregar_dados_json(cache_path)['data']
    content = await fetch_url(url)
    if not content:
        return cache
    
    soup = BeautifulSoup(content, 'html.parser')
    novos_itens = []
    for poster in soup.find_all('div', class_='poster'):
        titulo = poster.find('span', class_='title').get_text(strip=True)
        qualidade = poster.find('span', class_='year').get_text(strip=True)
        imagem = poster.find('img')['src']
        link = poster.find('a', class_='btn')['href']
        item_id = link.split('/')[-1]
        
        if not item_existe(cache, item_id):
            novos_itens.append({
                'titulo': titulo,
                'qualidade': qualidade,
                'capa': imagem,
                'id': item_id
            })
    
    if novos_itens:
        cache.extend(novos_itens)
        salvar_dados_json(cache_path, cache)
    
    return cache

@app.route('/filmes/novos')
@limiter.limit("10 per minute")
def filmes_novos():
    """Get new movies."""
    async def update():
        return await atualizar_filmes_series(
            "https://superflixapi.in/filmes",
            JSON_PATHS['filmes_novos']
        )
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    filmes = loop.run_until_complete(update())
    loop.close()
    
    return jsonify(filmes)

@app.route('/series')
@limiter.limit("10 per minute")
def series():
    """Get series."""
    async def update():
        return await atualizar_filmes_series(
            "https://superflixapi.in/series",
            JSON_PATHS['series'],
            is_series=True
        )
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    series = loop.run_until_complete(update())
    loop.close()
    
    return jsonify(series)

@app.route('/filmes/home')
@limiter.limit("10 per minute")
def filmes_home():
    """Get home movies."""
    filmes_cache = carregar_dados_json(JSON_PATHS['filmes_home'])['data']
    return jsonify(filmes_cache)

@app.route('/filmes/pagina')
@limiter.limit("10 per minute")
def filmes_pagina():
    """Get paginated movies."""
    try:
        pagina = int(request.args.get('pagina', 1))
        if pagina < 1:
            return jsonify({'erro': 'Página inválida'}), 400
    except ValueError:
        return jsonify({'erro': 'Página deve ser um número'}), 400
    
    filmes_cache = carregar_dados_json(JSON_PATHS"['data']
    filmes_por_pagina = 50
    inicio = (pagina - 1) * filmes_por_pagina
    fim = inicio + filmes_por_pagina
    filmes_paginados = filmes_cache[inicio:fim]
    return jsonify(filmes_paginados)

@app.route('/filmes/pagina/atualizar')
@limiter.limit("5 per minute")
def filmes_pagina_atualizar():
    """Update paginated movies."""
    async def update():
        return await atualizar_filmes_series(
            "https://superflixapi.in/filmes",
            JSON_PATHS['filmes_pagina']
        )
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    filmes = loop.run_until_complete(update())
    loop.close()
    
    return jsonify(filmes)

@app.route('/buscar')
@limiter.limit("10 per minute")
def buscar_nomes():
    """Search movies and series by term."""
    termo = request.args.get('q', '').lower()
    if not termo:
        return jsonify({'erro': 'Termo de busca é obrigatório'}), 400
    
    filmes = carregar_dados_json(JSON_PATHS['filmes_pagina'])['data']
    series = carregar_dados_json(JSON_PATHS['series_nomes'])['data']
    
    resultados_filmes = [f for f in filmes if termo in f['titulo'].lower()]
    resultados_series = [s for s in series if termo in s['titulo'].lower()]
    
    return jsonify(resultados_filmes + resultados_series[:10])

async def atualizar_codigos_inicial():
    """Initial codes update."""
    await asyncio.gather(
        fetch_codigos("https://superflixapi.in/filmes/lista/", JSON_PATHS['code_filmes']),
        fetch_codigos("https://superflixapi.in/series/lista/", JSON_PATHS['code_series'], is_series=True)
    )

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(atualizar_codigos_inicial())
    app.run(debug=True, port=5001)