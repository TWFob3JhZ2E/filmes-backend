import json
import os

def carregar_dados_json(caminho):
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Erro ao ler JSON: {caminho}")
            return []
    return []

def salvar_dados_json(caminho, dados):
    try:
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        print(f"Arquivo salvo com sucesso: {caminho}")
    except Exception as e:
        print(f"Erro ao salvar {caminho}: {e}")

def item_existe(lista, item_id):
    return any(item['id'] == item_id for item in lista)
