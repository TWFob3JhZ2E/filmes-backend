from flask import Flask, request, jsonify
from flask_cors import CORS

from filmes import filmes_bp
from series import series_bp
from codigos import codigos_bp

from config import *
from utils import carregar_dados_json

app = Flask(__name__)
CORS(app)

# Registrar blueprints
app.register_blueprint(filmes_bp)
app.register_blueprint(series_bp)
app.register_blueprint(codigos_bp)

@app.route('/buscar')
def buscar_nomes():
    termo = request.args.get('q', '').lower()
    filmes = carregar_dados_json(FILMES_PAGINA_JSON_PATH)
    series = carregar_dados_json(CODE_SERIES_NOMES_PATH)
    resultados_filmes = [f for f in filmes if termo in f['titulo'].lower()]
    resultados_series = [s for s in series if termo in s['titulo'].lower()]
    return jsonify((resultados_filmes + resultados_series)[:10])

if __name__ == '__main__':
    app.run(debug=True, port=5001)
