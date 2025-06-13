import requests
import json
import os
import logging
from ratelimit import limits, sleep_and_retry

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('buscanime.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 🔑 Chave da API do TMDb
TMDB_API_KEY = "5152effba7d64a5e995301fdcdba9bcc"

# Diretórios
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # Volta uma pasta (de Codes pra Back)
TEMP_DIR = os.path.join(BASE_DIR, "temp")
OUTPUT_FILE = os.path.join(TEMP_DIR, "animlist.json")

# Garante que a pasta temp existe
os.makedirs(TEMP_DIR, exist_ok=True)

# Limite de requisições por minuto (TMDb permite ~40 reqs/10s, ajustamos para segurança)
CALLS_PER_MINUTE = 30
PERIOD = 60

@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=PERIOD)
def buscar_nome_tmdb(anime_id):
    """Busca apenas o nome do anime no TMDb usando o ID."""
    url = f"https://api.themoviedb.org/3/tv/{anime_id}?api_key={TMDB_API_KEY}&language=pt-BR"
    try:
        response = requests.get(url, timeout=10)
        logging.info(f"🔍 Buscando anime ID {anime_id}: Status {response.status_code}")
        
        if response.status_code == 200:
            dados = response.json()
            nome = dados.get("name")
            if not nome:
                logging.warning(f"Nome não encontrado para ID {anime_id}")
                return None
            return {"id": str(anime_id), "nome": nome}
        else:
            logging.error(f"Erro ao buscar anime ID {anime_id}: Status {response.status_code}")
            return None
    except requests.Timeout:
        logging.error(f"Timeout ao acessar TMDb para ID {anime_id}")
        return None
    except requests.RequestException as e:
        logging.error(f"Erro na requisição TMDb para ID {anime_id}: {e}")
        return None

def carregar_ids_animes():
    """Carrega os IDs de animes do arquivo CodeAnimes.json."""
    caminho = os.path.join(TEMP_DIR, 'CodeAnimes.json')
    try:
        with open(caminho, 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data.get('codigos', [])
    except FileNotFoundError:
        logging.error(f"Arquivo {caminho} não encontrado")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Erro ao decodificar {caminho}: {e}")
        return []
    except Exception as e:
        logging.error(f"Erro ao carregar {caminho}: {e}")
        return []

def carregar_animlist_existente():
    """Carrega o animlist.json existente, se houver."""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            logging.error(f"Erro ao carregar {OUTPUT_FILE}: {e}")
    return []

def salvar_animlist(dados):
    """Salva os dados no animlist.json."""
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as file:
            json.dump(dados, file, indent=4, ensure_ascii=False)
        logging.info(f"✅ Dados salvos em {OUTPUT_FILE}")
    except IOError as e:
        logging.error(f"Erro ao salvar {OUTPUT_FILE}: {e}")

def main():
    """Função principal para processar IDs de animes e salvar nomes em animlist.json."""
    logging.info("🚀 Iniciando busca de nomes de animes...")
    
    # Carregar IDs de animes
    anime_ids = carregar_ids_animes()
    if not anime_ids:
        logging.error("Nenhum ID de anime encontrado. Encerrando.")
        return
    
    # Carregar animlist.json existente
    animlist = carregar_animlist_existente()
    ids_processados = {anime['id'] for anime in animlist}

    # Processar IDs
    for anime_id in anime_ids:
        if str(anime_id) in ids_processados:
            logging.info(f"⏩ Anime ID {anime_id} já processado, pulando...")
            continue
        
        dados = buscar_nome_tmdb(anime_id)
        if dados:
            animlist.append(dados)
            salvar_animlist(animlist)
            logging.info(f"✅ Adicionado: {dados['nome']} (ID: {anime_id})")
        else:
            logging.warning(f"⚠️ Falha ao processar ID {anime_id}")

    logging.info(f"🎉 Processamento concluído! Resultados salvos em {OUTPUT_FILE}")

if __name__ == "__main__":
    main()