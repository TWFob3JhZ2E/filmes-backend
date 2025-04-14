from flask import Blueprint

# Blueprints para cada grupo de rota
filmes_bp = Blueprint('filmes', __name__)
series_bp = Blueprint('series', __name__)
codigos_bp = Blueprint('codigos', __name__)
