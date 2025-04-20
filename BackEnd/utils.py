import os
import json
import requests
from bs4 import BeautifulSoup

# Definição dos diretórios e caminhos de arquivos
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
FILMES_ENCONTRADOS_DIR = os.path.join(BASE_DIR, 'Filmes_Encontrados')

os.makedirs(TEMP_DIR, exist_ok=True)

FILMES_PAGINA_JSON_PATH = os.path.join(FILMES_ENCONTRADOS_DIR, 'CodeFilmesNomes.json')
CODE_SERIES_NOMES_PATH = os.path.join(FILMES_ENCONTRADOS_DIR, 'CodeSeriesNomes.json')
FILMES_NOVOS_JSON_PATH = os.path.join(TEMP_DIR, 'Novosfilmes.json')
SERIES_JSON_PATH = os.path.join(TEMP_DIR, 'series.json')
FILMES_HOME_JSON_PATH = os.path.join(TEMP_DIR, 'Filmes.json')
CODE_FILMES_JSON_PATH = os.path.join(TEMP_DIR, 'CodeFilmes.json')
CODE_SERIES_JSON_PATH = os.path.join(TEMP_DIR, 'CodeSeries.json')


def carregar_dados_json(caminho):
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Erro ao decodificar o arquivo JSON {caminho}, criando um novo arquivo.")
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


def obter_codigos_filmes():
    codigos_filmes_cache = carregar_dados_json(CODE_FILMES_JSON_PATH)

    if codigos_filmes_cache:
        return codigos_filmes_cache.get("codigos", [])

    try:
        url = "https://superflixapi.co/filmes/lista/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            dados_bagunçados = soup.get_text()

            import re
            codigos = re.findall(r'tt\d+', dados_bagunçados)

            salvar_dados_json(CODE_FILMES_JSON_PATH, {"codigos": codigos})
            return codigos
    except Exception as e:
        print(f"Erro ao buscar códigos de filmes: {e}")

    return []


def obter_codigos_series():
    codigos_series_cache = carregar_dados_json(CODE_SERIES_JSON_PATH)

    if codigos_series_cache:
        return codigos_series_cache.get("codigos", [])

    try:
        url = "https://superflixapi.co/series/lista/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            raw_codigos = soup.decode_contents().split('<br/>')
            codigos = [codigo.strip() for codigo in raw_codigos if codigo.strip().isdigit()]

            salvar_dados_json(CODE_SERIES_JSON_PATH, {"codigos": codigos})
            return codigos
    except Exception as e:
        print(f"Erro ao buscar códigos de séries: {e}")

    return []
