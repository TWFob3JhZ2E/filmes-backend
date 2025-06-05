import requests
from bs4 import BeautifulSoup
import json
import os

# 🔑 Insira sua chave da API do TMDb aqui
TMDB_API_KEY = "5152effba7d64a5e995301fdcdba9bcc"

# Diretórios
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # volta uma pasta (de Codes pra Back)
temp_dir = os.path.join(base_dir, "temp")
saida_dir = os.path.join(base_dir, "Filmes_Encontrados")

# Garante que a pasta de saída existe
os.makedirs(saida_dir, exist_ok=True)

# --------------- FILMES - IMDb ---------------
def obter_dados_imdb(filme_id):
    if not filme_id.startswith("tt") or len(filme_id) < 9:
        print(f"ID inválido: {filme_id}")
        return None

    url = f"https://www.imdb.com/pt/title/{filme_id}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.encoding = 'utf-8'

    print(f"Status Code para {url}: {response.status_code}")

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        titulo = soup.find('span', class_='hero__primary-text')
        titulo_texto = titulo.get_text(strip=True) if titulo else None

        titulo_original = soup.find('div', class_='sc-ec65ba05-1 fUCCIx')
        titulo_original_texto = titulo_original.get_text(strip=True).replace('Título original: ', '') if titulo_original else None

        capa_imagem = soup.find('meta', property='og:image')
        capa_url = capa_imagem['content'] if capa_imagem else None

        descricao_tag = soup.find('span', attrs={'data-testid': 'plot-l'})
        descricao = descricao_tag.get_text(strip=True) if descricao_tag else None

        qualidade = None
        if "4K" in response.text:
            qualidade = "4K"
        elif "HD" in response.text:
            qualidade = "HD"
        elif "SD" in response.text:
            qualidade = "SD"

        # Obtendo os dois primeiros gêneros
        generos_tag = soup.find_all('span', class_='ipc-chip__text')
        generos = [genero.get_text(strip=True) for genero in generos_tag][:2]  # Limita para os dois primeiros

        return {
            "titulo": titulo_texto,
            "titulo_original": titulo_original_texto,
            "capa": capa_url,
            "qualidade": qualidade,
            "descricao": descricao,
            "generos": generos
        }
    else:
        print(f"Erro ao acessar {url}")
        return None

# --------------- Carregar arquivos de ID ---------------
def carregar_ids_filmes():
    try:
        with open(os.path.join(temp_dir, 'CodeFilmes.json'), 'r', encoding='utf-8') as file:
            return json.load(file).get('codigos', [])
    except Exception as e:
        print(f"Erro ao carregar filmes: {e}")
        return []

def carregar_ids_series():
    try:
        with open(os.path.join(temp_dir, 'CodeSeries.json'), 'r', encoding='utf-8') as file:
            return json.load(file).get('codigos', [])
    except Exception as e:
        print(f"Erro ao carregar séries: {e}")
        return []

def carregar_ids_animes():
    try:
        with open(os.path.join(temp_dir, 'CodeAnimes.json'), 'r', encoding='utf-8') as file:
            return json.load(file).get('codigos', [])
    except Exception as e:
        print(f"Erro ao carregar animes: {e}")
        return []

# --------------- SÉRIES e ANIMES - TMDb ---------------
def buscar_dados_tmdb(item_id, tipo='tv'):
    url = f"https://api.themoviedb.org/3/{tipo}/{item_id}?api_key={TMDB_API_KEY}&language=pt-BR"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            dados = response.json()
            # Obtendo os dois primeiros gêneros
            generos = [genero['name'] for genero in dados.get('genres', [])][:2]  # Limita para os dois primeiros

            return {
                "titulo": dados.get("name"),
                "titulo_original": dados.get("original_name"),
                "id": str(item_id),
                "capa": f"https://image.tmdb.org/t/p/w500{dados.get('poster_path')}" if dados.get("poster_path") else None,
                "qualidade": "HD",
                "descricao": dados.get("overview"),
                "generos": generos
            }
        else:
            print(f"Erro ao buscar {tipo} de ID {item_id}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Erro na requisição TMDb para ID {item_id}: {e}")
        return None

# --------------- Suporte para salvar ---------------
def carregar_json_existente(nome_arquivo):
    caminho = os.path.join(saida_dir, nome_arquivo)
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            print(f"Erro ao carregar {caminho}: {e}")
    return []

def salvar_json_incremental(nome_arquivo, dados):
    caminho = os.path.join(saida_dir, nome_arquivo)
    try:
        with open(caminho, 'w', encoding='utf-8') as file:
            json.dump(dados, file, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Erro ao salvar {caminho}: {e}")

# --------------- MAIN ---------------
def main():
    filmes_ids = carregar_ids_filmes()
    series_ids = carregar_ids_series()
    animes_ids = carregar_ids_animes()

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
                print(f"🔍 Buscando filme: {filme_id}")
                dados = obter_dados_imdb(filme_id)
                if dados:
                    novo_filme = {
                        "titulo": dados["titulo"],
                        "titulo_original": dados["titulo_original"],
                        "id": filme_id,
                        "capa": dados["capa"],
                        "qualidade": dados["qualidade"],
                        "descricao": dados["descricao"],
                        "generos": dados["generos"]
                    }
                    filmes_nomes.append(novo_filme)
                    salvar_json_incremental('CodeFilmesNomes.json', filmes_nomes)
            else:
                print(f"⏩ Filme já processado: {filme_id}")

        # Série
        if i_series < len(series_ids):
            serie_id = series_ids[i_series]
            i_series += 1

            if str(serie_id) not in series_ids_processados:
                print(f"🔍 Buscando série: {serie_id}")
                dados = buscar_dados_tmdb(serie_id, tipo='tv')
                if dados:
                    series_nomes.append(dados)
                    salvar_json_incremental('CodeSeriesNomes.json', series_nomes)
            else:
                print(f"⏩ Série já processada: {serie_id}")

        # Anime
        if i_animes < len(animes_ids):
            anime_id = animes_ids[i_animes]
            i_animes += 1

            if str(anime_id) not in animes_ids_processados:
                print(f"🔍 Buscando anime: {anime_id}")
                dados = buscar_dados_tmdb(anime_id, tipo='tv')
                if dados:
                    animes_nomes.append(dados)
                    salvar_json_incremental('CodeAnimesNomes.json', animes_nomes)
            else:
                print(f"⏩ Anime já processado: {anime_id}")

    print("\n✅ Processamento finalizado!")
    print(f"Arquivos atualizados em: {saida_dir}")

if __name__ == "__main__":
    main()