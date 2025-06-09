import json
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Diretórios
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # volta uma pasta
saida_dir = os.path.join(base_dir, "Filmes_Encontrados")

# Garante que a pasta de saída existe
os.makedirs(saida_dir, exist_ok=True)

# Função para carregar JSON
def carregar_json(nome_arquivo):
    caminho = os.path.join(saida_dir, nome_arquivo)
    try:
        with open(caminho, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logging.error(f"Erro ao carregar {caminho}: {e}")
        return []

# Função para extrair gêneros únicos
def extrair_generos_unicos(dados):
    generos = set()
    for item in dados:
        if 'generos' in item and isinstance(item['generos'], list):
            generos.update(item['generos'])
    return sorted(list(generos))

# Função para salvar JSON
def salvar_json(nome_arquivo, dados):
    caminho = os.path.join(saida_dir, nome_arquivo)
    try:
        with open(caminho, 'w', encoding='utf-8') as file:
            json.dump(dados, file, indent=4, ensure_ascii=False)
        logging.info(f"Arquivo salvo: {caminho}")
    except IOError as e:
        logging.error(f"Erro ao salvar {caminho}: {e}")

# Main
def main():
    # Carregar os arquivos JSON
    filmes = carregar_json('CodeFilmesNomes.json')
    series = carregar_json('CodeSeriesNomes.json')
    animes = carregar_json('CodeAnimesNomes.json')

    # Extrair gêneros únicos
    generos_filmes = extrair_generos_unicos(filmes)
    generos_series = extrair_generos_unicos(series)
    generos_animes = extrair_generos_unicos(animes)

    # Estrutura do JSON final
    generos_todos = {
        "filmes": generos_filmes,
        "series": generos_series,
        "animes": generos_animes
    }

    # Salvar o resultado
    salvar_json('generosTodos.json', generos_todos)
    logging.info("✅ Extração de gêneros finalizada!")

if __name__ == "__main__":
    main()