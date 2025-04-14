import requests
from bs4 import BeautifulSoup
import json
import os

# 🔑 Insira sua chave da API do TMDb aqui
TMDB_API_KEY = "5152effba7d64a5e995301fdcdba9bcc"

# --------------- FILMES - IMDb ---------------

def obter_dados_imdb(filme_id):
    if not filme_id.startswith("tt") or len(filme_id) < 9:
        print(f"ID inválido: {filme_id}")
        return None

    url = f"https://www.imdb.com/pt/title/{filme_id}/"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers)
    response.encoding = 'utf-8'  # Corrige os caracteres especiais

    print(f"Status Code para {url}: {response.status_code}")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        titulo = soup.find('span', class_='hero__primary-text')
        if titulo:
            titulo_texto = titulo.get_text(strip=True)
        else:
            print(f"Título não encontrado para {filme_id}")
            return None
        
        titulo_original = soup.find('div', class_='sc-ec65ba05-1 fUCCIx')
        titulo_original_texto = (
            titulo_original.get_text(strip=True).replace('Título original: ', '')
            if titulo_original else None
        )

        capa_imagem = soup.find('meta', property='og:image')
        capa_url = capa_imagem['content'] if capa_imagem else None

        qualidade = None
        if "4K" in response.text:
            qualidade = "4K"
        elif "HD" in response.text:
            qualidade = "HD"
        elif "SD" in response.text:
            qualidade = "SD"

        return {
            "titulo": titulo_texto,
            "titulo_original": titulo_original_texto,
            "capa": capa_url,
            "qualidade": qualidade
        }
    else:
        print(f"Erro ao acessar {url}")
        return None

def carregar_ids_filmes():
    try:
        with open('Codefilmes.json', 'r', encoding='utf-8') as file:
            return json.load(file).get('codigos', [])
    except Exception as e:
        print(f"Erro ao carregar filmes: {e}")
        return []

# --------------- SÉRIES - TMDb ---------------

def carregar_ids_series():
    try:
        with open('CodeSeries.json', 'r', encoding='utf-8') as file:
            return json.load(file).get('codigos', [])
    except Exception as e:
        print(f"Erro ao carregar séries: {e}")
        return []

def buscar_dados_tmdb(serie_id):
    url = f"https://api.themoviedb.org/3/tv/{serie_id}?api_key={TMDB_API_KEY}&language=pt-BR"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            dados = response.json()
            return {
                "titulo": dados.get("name"),
                "titulo_original": dados.get("original_name"),
                "id": str(serie_id),
                "capa": f"https://image.tmdb.org/t/p/w500{dados.get('poster_path')}" if dados.get("poster_path") else None,
                "qualidade": "HD"
            }
        else:
            print(f"Erro ao buscar série {serie_id}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Erro na requisição TMDb para ID {serie_id}: {e}")
        return None

# --------------- SUPORTE PARA SALVAR INCREMENTALMENTE ---------------

def carregar_json_existente(caminho):
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            print(f"Erro ao carregar {caminho}: {e}")
    return []

def salvar_json_incremental(caminho, dados):
    try:
        with open(caminho, 'w', encoding='utf-8') as file:
            json.dump(dados, file, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar {caminho}: {e}")

# --------------- MAIN - Intercalado FILME -> SÉRIE -> FILME... ---------------

def main():
    # 🎬 Carregar dados existentes
    filmes_ids = carregar_ids_filmes()
    series_ids = carregar_ids_series()

    filmes_nomes = carregar_json_existente('CodeFilmesNomes.json')
    series_nomes = carregar_json_existente('CodeSeriesNomes.json')

    filmes_ids_processados = {filme['id'] for filme in filmes_nomes}
    series_ids_processados = {serie['id'] for serie in series_nomes}

    i_filme = i_serie = 0

    while i_filme < len(filmes_ids) or i_serie < len(series_ids):
        # Filme
        if i_filme < len(filmes_ids):
            filme_id = filmes_ids[i_filme]
            i_filme += 1

            if filme_id not in filmes_ids_processados:
                print(f"🔍 Buscando filme: {filme_id}")
                dados = obter_dados_imdb(filme_id)
                if dados:
                    novo_filme = {
                        "titulo": dados["titulo"],
                        "titulo_original": dados["titulo_original"],
                        "id": filme_id,
                        "capa": dados["capa"],
                        "qualidade": dados["qualidade"]
                    }
                    filmes_nomes.append(novo_filme)
                    salvar_json_incremental('CodeFilmesNomes.json', filmes_nomes)
            else:
                print(f"⏩ Filme já processado: {filme_id}")

        # Série
        if i_serie < len(series_ids):
            serie_id = series_ids[i_serie]
            i_serie += 1

            if str(serie_id) not in series_ids_processados:
                print(f"🔍 Buscando série: {serie_id}")
                dados = buscar_dados_tmdb(serie_id)
                if dados:
                    series_nomes.append(dados)
                    salvar_json_incremental('CodeSeriesNomes.json', series_nomes)
            else:
                print(f"⏩ Série já processada: {serie_id}")

    print("\n✅ Processamento finalizado!")
    print("Arquivos atualizados:")
    print("- CodeFilmesNomes.json")
    print("- CodeSeriesNomes.json")

if __name__ == "__main__":
    main()
