from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from redis import Redis

# Importa as rotas e funções auxiliares
from API.routes.filmes import filmes_bp
from API.routes.series import series_bp
from utils.helpers import sincronizar_dados

# Configuração do Redis
redis = Redis.from_url('redis://localhost:6379/0')  # Conectando ao Redis no localhost, banco de dados 0

# Inicializa o app Flask
app = Flask(__name__)

# Configuração CORS (permite acesso de diferentes origens)
CORS(app)

# 🔐 Limita requisições por IP usando Flask-Limiter e Redis como backend
limiter = Limiter(
    get_remote_address,  # Usa o endereço IP do cliente para limitar as requisições
    app=app,
    storage_uri="redis://localhost:6379/0"  # Configura Redis como o backend para o Flask-Limiter
)

# ✅ Registra as rotas
app.register_blueprint(filmes_bp, url_prefix="/filmes")
app.register_blueprint(series_bp, url_prefix="/series")

# 📁 Sincroniza os dados antes de iniciar o servidor
sincronizar_dados('Novosfilmes.json', 'CodeFilmesNomes.json')
sincronizar_dados('series.json', 'CodeSeriesNomes.json')

# 🚀 Inicializa o app com o debug DESATIVADO (para maior segurança)
if __name__ == '__main__':
    app.run(debug=False, port=5001)
