import os

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
