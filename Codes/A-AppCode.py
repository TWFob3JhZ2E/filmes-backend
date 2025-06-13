import requests
from bs4 import BeautifulSoup
import json
import os
import logging
from ratelimit import limits, sleep_and_retry
import time
from unidecode import unidecode  # Para limpar nomes no fallback

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('busca_principal.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 🔑 Chaves das APIs
TMDB_API_KEY = "5152effba7d64a5e995301fdcdba9bcc"
ANILIST_API_URL = "https://graphql.anilist.co"

# Diretórios
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # Volta uma pasta (de Codes pra Back)
TEMP_DIR = os.path.join(BASE_DIR, "temp")
SAIDA_DIR = os.path.join(BASE_DIR, "Filmes_Encontrados")

# Garante que as pastas existem
os.makedirs(SAIDA_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Limite de requisições por minuto
CALLS_PER_MINUTE = 20
PERIOD = 60

# Função para normalizar nomes de animes (automática)
def normalize_anime_name(nome_anime, tmdb_id):
    """Converte nomes para inglês automaticamente usando TMDb ou limpeza de texto."""
    # Tentar obter o título original do TMDb
    tmdb_data = buscar_dados_tmdb(tmdb_id, tipo='tv', normalize=True)
    if tmdb_data and tmdb_data.get('original_name'):
        normalized_name = tmdb_data['original_name']
        logging.info(f"Normalizado '{nome_anime}' para '{normalized_name}' via TMDb")
        # Verificar se é animação ocidental (não japonesa)
        if tmdb_data.get('original_language') != 'ja':
            logging.info(f"'{normalized_name}' não é anime japonês. Usando TMDb.")
            return normalized_name, True  # True indica que deve usar TMDb
        return normalized_name, False  # False indica que pode tentar AniList
    # Fallback: limpar o nome original
    normalized_name = unidecode(nome_anime).strip()
    if normalized_name != nome_anime:
        logging.info(f"Normalizado '{nome_anime}' para '{normalized_name}' via unidecode")
    else:
        logging.info(f"Nome '{nome_anime}' mantido (sem normalização)")
    return normalized_name, False  # Tentar AniList como padrão

# --------------- FILMES - IMDb ---------------
@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=PERIOD)
def obter_dados_imdb(filme_id):
    if not filme_id.startswith("tt") or len(filme_id) < 9:
        logging.error(f"ID inválido: {filme_id}")
        return None

    url = f"https://www.imdb.com/title/{filme_id}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        logging.info(f"Status Code para {url}: {response.status_code}")

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Título
            titulo = soup.find('span', class_='hero__primary-text')
            titulo_texto = titulo.get_text(strip=True) if titulo else None

            # Título original
            titulo_original = soup.find('div', class_='sc-ec65ba05-1 fUCCIx')
            titulo_original_texto = titulo_original.get_text(strip=True).replace('Título original: ', '') if titulo_original else None

            # Capa
            capa_imagem = soup.find('meta', property='og:image')
            capa_url = capa_imagem['content'] if capa_imagem else None

            # Descrição
            descricao_tag = soup.find('span', attrs={'data-testid': 'plot-xl'}) or soup.find('span', attrs={'data-testid': 'plot-l'})
            descricao = descricao_tag.get_text(strip=True) if descricao_tag else "Descrição não disponível"

            # Qualidade
            qualidade = None
            if "4K" in response.text:
                qualidade = "4K"
            elif "HD" in response.text:
                qualidade = "HD"
            elif "SD" in response.text:
                qualidade = "SD"
            else:
                qualidade = "Desconhecida"

            # Gêneros
            generos_tag = soup.find_all('span', class_='ipc-chip__text')
            generos = [genero.get_text(strip=True) for genero in generos_tag if genero.get_text(strip=True)]

            # Data de lançamento
            data_tag = soup.find('a', href=lambda x: x and '/releaseinfo' in x)
            data_lancamento = data_tag.get_text(strip=True) if data_tag else "Data não disponível"

            # Validação
            if not titulo_texto or not generos:
                logging.warning(f"Dados incompletos para filme {filme_id}: título={titulo_texto}, gêneros={generos}")
                return None

            return {
                "titulo": titulo_texto,
                "titulo_original": titulo_original_texto,
                "id": filme_id,
                "capa": capa_url,
                "qualidade": qualidade,
                "descricao": descricao,
                "generos": generos,
                "data_lancamento": data_lancamento
            }
        else:
            logging.error(f"Erro ao acessar {url}: Status {response.status_code}")
            return None
    except requests.Timeout:
        logging.error(f"Timeout ao acessar {url}")
        return None
    except requests.RequestException as e:
        logging.error(f"Erro na requisição para {url}: {e}")
        return None

# --------------- SÉRIES - TMDb ---------------
@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=PERIOD)
def buscar_dados_tmdb(item_id, tipo='tv', normalize=False):
    url = f"https://api.themoviedb.org/3/{tipo}/{item_id}?api_key={TMDB_API_KEY}&language=pt-BR"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            dados = response.json()
            generos = [genero['name'] for genero in dados.get('genres', [])]
            if not generos and not normalize:
                # Tentar obter palavras-chave
                keywords_url = f"https://api.themoviedb.org/3/{tipo}/{item_id}/keywords?api_key={TMDB_API_KEY}"
                keywords_response = requests.get(keywords_url, timeout=10)
                if keywords_response.status_code == 200:
                    generos = [kw['name'] for kw in keywords_response.json().get('results', [])][:3]
                if not generos:
                    generos = ["Animação", "Infantil"]  # Gêneros padrão para animações

            descricao = dados.get("overview") or "Descrição não disponível"
            data_estreia = dados.get("first_air_date", "Data não disponível")

            if not dados.get("name") and not normalize:
                logging.warning(f"Dados incompletos para {tipo} {item_id}: título={dados.get('name')}")
                return None

            return {
                "titulo": dados.get("name"),
                "titulo_original": dados.get("original_name"),
                "id": str(item_id),
                "capa": f"https://image.tmdb.org/t/p/w500{dados.get('poster_path')}" if dados.get('poster_path') else None,
                "qualidade": "HD",
                "descricao": descricao,
                "generos": generos,
                "data_estreia": data_estreia,
                "original_language": dados.get("original_language")  # Para verificar idioma
            }
        else:
            logging.error(f"Erro ao buscar {tipo} de ID {item_id}: Status {response.status_code}")
            return None
    except requests.Timeout:
        logging.error(f"Timeout ao acessar TMDb para ID {item_id}")
        return None
    except requests.RequestException as e:
        logging.error(f"Erro na requisição TMDb para ID {item_id}: {e}")
        return None

# --------------- ANIMES - AniList ---------------
@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=PERIOD)
def buscar_dados_anilist(nome_anime, tmdb_id):
    # Normalizar nome e verificar se é animação ocidental
    anime_nome, use_tmdb = normalize_anime_name(nome_anime, tmdb_id)
    if use_tmdb:
        return buscar_dados_tmdb(tmdb_id, tipo='tv')
    
    query = """
    query ($search: String) {
        Media(search: $search, type: ANIME) {
            id
            title { romaji english native }
            genres
            tags { name rank }
            description
            coverImage { large }
            startDate { year month day }
        }
    }
    """
    variables = {"search": anime_nome}
    try:
        response = requests.post(ANILIST_API_URL, json={'query': query, 'variables': variables}, timeout=10)
        logging.info(f"🔍 Buscando anime '{anime_nome}' na AniList: Status {response.status_code}")

        if response.status_code == 429:
            logging.warning(f"Limite de requisições atingido na AniList. Aguardando 10 segundos.")
            time.sleep(10)
            return buscar_dados_tmdb(tmdb_id, tipo='tv')

        if response.status_code == 200:
            dados = response.json().get('data', {}).get('Media')
            if not dados:
                logging.warning(f"Nenhum anime encontrado na AniList para '{anime_nome}'")
                return buscar_dados_tmdb(tmdb_id, tipo='tv')

            # Processar descrição
            descricao = dados.get('description') or "Descrição não disponível"
            if isinstance(descricao, str):
                descricao = descricao.replace('<br>', ' ').replace('<i>', '').replace('</i>', '')
            else:
                descricao = "Descrição não disponível"

            # Processar data de estreia com verificação de None
            start_date = dados.get('startDate', {})
            year = start_date.get('year')
            month = start_date.get('month')
            day = start_date.get('day')
            if year and month and day:
                try:
                    data_estreia = f"{year}-{month:02d}-{day:02d}"
                except (TypeError, ValueError):
                    logging.warning(f"Data inválida para '{anime_nome}': {start_date}")
                    data_estreia = "Data não disponível"
            else:
                logging.warning(f"Data incompleta para '{anime_nome}': {start_date}")
                data_estreia = "Data não disponível"

            # Filtrar tags
            tags = [tag['name'] for tag in dados.get('tags', []) if tag.get('rank', 0) >= 50]
            generos = dados.get('genres', []) + tags[:3]

            return {
                "titulo": dados['title'].get('romaji') or dados['title'].get('english') or anime_nome,
                "titulo_original": dados['title'].get('native') or dados['title'].get('romaji'),
                "id": str(tmdb_id),
                "capa": dados['coverImage'].get('large'),
                "qualidade": "HD",
                "descricao": descricao,
                "generos": generos or ["Animação"],
                "data_estreia": data_estreia
            }
        else:
            logging.error(f"Erro ao buscar '{anime_nome}' na AniList: Status {response.status_code}, Resposta: {response.text}")
            return buscar_dados_tmdb(tmdb_id, tipo='tv')
    except requests.Timeout:
        logging.error(f"Timeout ao acessar AniList para '{anime_nome}'")
        return buscar_dados_tmdb(tmdb_id, tipo='tv')
    except requests.RequestException as e:
        logging.error(f"Erro na requisição AniList para '{anime_nome}': {e}")
        return buscar_dados_tmdb(tmdb_id, tipo='tv')

# --------------- Carregar arquivos de ID ---------------
def carregar_ids_filmes():
    try:
        with open(os.path.join(TEMP_DIR, 'CodeFilmes.json'), 'r', encoding='utf-8') as file:
            return json.load(file).get('codigos', [])
    except Exception as e:
        logging.error(f"Erro ao carregar filmes: {e}")
        return []

def carregar_ids_series():
    try:
        with open(os.path.join(TEMP_DIR, 'CodeSeries.json'), 'r', encoding='utf-8') as file:
            return json.load(file).get('codigos', [])
    except Exception as e:
        logging.error(f"Erro ao carregar séries: {e}")
        return []

def carregar_ids_animes():
    try:
        with open(os.path.join(TEMP_DIR, 'CodeAnimes.json'), 'r', encoding='utf-8') as file:
            return json.load(file).get('codigos', [])
    except Exception as e:
        logging.error(f"Erro ao carregar animes: {e}")
        return []

def carregar_animlist():
    try:
        with open(os.path.join(TEMP_DIR, 'animlist.json'), 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logging.error(f"Erro ao carregar animlist.json: {e}")
        return []

# --------------- Suporte para salvar ---------------
def carregar_json_existente(nome_arquivo):
    caminho = os.path.join(SAIDA_DIR, nome_arquivo)
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            logging.error(f"Erro ao carregar {caminho}: {e}")
    return []

def salvar_json_incremental(nome_arquivo, dados):
    caminho = os.path.join(SAIDA_DIR, nome_arquivo)
    try:
        with open(caminho, 'w', encoding='utf-8') as file:
            json.dump(dados, file, indent=4, ensure_ascii=False)
    except IOError as e:
        logging.error(f"Erro ao salvar {caminho}: {e}")

# --------------- MAIN ---------------
def main():
    filmes_ids = carregar_ids_filmes()
    series_ids = carregar_ids_series()
    animes_ids = carregar_ids_animes()
    animlist = carregar_animlist()

    filmes_nomes = carregar_json_existente('CodeFilmesNomes.json')
    series_nomes = carregar_json_existente('CodeSeriesNomes.json')
    animes_nomes = carregar_json_existente('CodeAnimesNomes.json')

    filmes_ids_processados = {filme['id'] for filme in filmes_nomes}
    series_ids_processados = {serie['id'] for serie in series_nomes}
    animes_ids_processados = {anime['id'] for anime in animes_nomes}

    i_filmes = i_series = i_animes = 0

    while i_filmes < len(filmes_ids) or i_series < len(series_ids) or i_animes < len(animes_ids):
        # Filme
        if i_filmes < len(filmes_ids):
            filme_id = filmes_ids[i_filmes]
            i_filmes += 1

            if filme_id not in filmes_ids_processados:
                logging.info(f"🔍 Buscando filme: {filme_id}")
                dados = obter_dados_imdb(filme_id)
                if dados:
                    novo_filme = {
                        "titulo": dados["titulo"],
                        "titulo_original": dados["titulo_original"],
                        "id": filme_id,
                        "capa": dados["capa"],
                        "qualidade": dados["qualidade"],
                        "descricao": dados["descricao"],
                        "generos": dados["generos"],
                        "data_lancamento": dados["data_lancamento"]
                    }
                    filmes_nomes.append(novo_filme)
                    salvar_json_incremental('CodeFilmesNomes.json', filmes_nomes)
            else:
                logging.info(f"⏩ Filme já processado: {filme_id}")

        # Série
        if i_series < len(series_ids):
            serie_id = series_ids[i_series]
            i_series += 1

            if str(serie_id) not in series_ids_processados:
                logging.info(f"🔍 Buscando série: {serie_id}")
                dados = buscar_dados_tmdb(serie_id, tipo='tv')
                if dados:
                    series_nomes.append(dados)
                    salvar_json_incremental('CodeSeriesNomes.json', series_nomes)
            else:
                logging.info(f"⏩ Série já processada: {serie_id}")

        # Anime
        if i_animes < len(animes_ids):
            anime_id = animes_ids[i_animes]
            i_animes += 1

            if str(anime_id) not in animes_ids_processados:
                logging.info(f"🔍 Buscando anime ID: {anime_id}")
                # Buscar nome correspondente no animlist.json
                anime_nome = next((item['nome'] for item in animlist if item['id'] == str(anime_id)), None)
                if not anime_nome:
                    logging.warning(f"Nome não encontrado para anime ID {anime_id} em animlist.json")
                    dados = buscar_dados_tmdb(anime_id, tipo='tv')
                else:
                    dados = buscar_dados_anilist(anime_nome, anime_id)

                if dados:
                    animes_nomes.append(dados)
                    salvar_json_incremental('CodeAnimesNomes.json', animes_nomes)
            else:
                logging.info(f"⏩ Anime já processado: {anime_id}")

    logging.info("\n✅ Processamento finalizado!")
    logging.info(f"Arquivos atualizados em: {SAIDA_DIR}")

if __name__ == "__main__":
    main()