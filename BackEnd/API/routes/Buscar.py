from flask import Blueprint, request, jsonify
from utils.helpers import carregar_dados_json

buscar_bp = Blueprint('buscar', __name__)

@buscar_bp.route('/buscar')
def buscar_nomes():
    termo = request.args.get('q', '').lower()
    filmes = carregar_dados_json('CodeFilmesNomes.json')
    series = carregar_dados_json('CodeSeriesNomes.json')

    resultados_filmes = [f for f in filmes if termo in f['titulo'].lower()]
    resultados_series = [s for s in series if termo in s['titulo'].lower()]

    resultados = resultados_filmes + resultados_series

    return jsonify(resultados[:10])
