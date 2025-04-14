import os
import json

TEMP_DIR = 'temp'

def caminho_com_temp(caminho):
    if not caminho.startswith(TEMP_DIR + os.sep):
        return os.path.join(TEMP_DIR, caminho)
    return caminho

def carregar_dados_json(caminho):
    caminho = caminho_com_temp(caminho)
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Erro ao decodificar JSON {caminho}")
            return []
    return []

def salvar_dados_json(caminho, dados):
    caminho = caminho_com_temp(caminho)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    try:
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Erro ao salvar {caminho}: {e}")

def item_existe(lista, item_id):
    return any(item['id'] == item_id for item in lista)

def sincronizar_dados(origem_path, destino_path):
    origem_path = caminho_com_temp(origem_path)
    destino_path = caminho_com_temp(destino_path)

    dados_origem = carregar_dados_json(origem_path)
    dados_destino = carregar_dados_json(destino_path)

    novos_dados = [item for item in dados_origem if not item_existe(dados_destino, item['id'])]

    if novos_dados:
        dados_destino.extend(novos_dados)
        salvar_dados_json(destino_path, dados_destino)
        print(f"{len(novos_dados)} novos itens adicionados de {origem_path} para {destino_path}")
    else:
        print(f"Nenhum novo item para sincronizar de {origem_path} para {destino_path}")
        
# 1 para voltar 