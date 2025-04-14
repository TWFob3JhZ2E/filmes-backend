from BackEnd.routes.filmes import filmes_bp
from BackEnd.routes.series import series_bp
from BackEnd.routes.codigos import codigos_bp

# Lista de blueprints para facilitar registro no app.py
blueprints = [
    filmes_bp,
    series_bp,
    codigos_bp
]
