import os
import json

TEMP_DIR = 'temp'
os.makedirs(TEMP_DIR, exist_ok=True)

def caminho_json(nome_arquivo):
    return os.path.join(TEMP_DIR, nome_arquivo)

def carregar_dados_json(caminho):
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Erro ao decodificar o arquivo JSON {caminho}, criando um novo.")
            return []
    return []

def salvar_dados_json(caminho, dados):
    try:
        if os.path.exists(caminho):
            print(f"O arquivo {caminho} já existe. Atualizando conteúdo.")
        else:
            print(f"Criando novo arquivo: {caminho}")
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        print(f"Arquivo {caminho} salvo com sucesso!")
    except Exception as e:
        print(f"Erro ao salvar o arquivo {caminho}: {e}")

def item_existe(lista, item_id):
    return any(item['id'] == item_id for item in lista)
