from flask import Flask
from flask_cors import CORS
from routes.filmes import filmes_bp
from routes.series import series_bp
from routes.codigos import codigos_bp

app = Flask(__name__)
CORS(app)

# Registrar Blueprints
app.register_blueprint(filmes_bp)
app.register_blueprint(series_bp)
app.register_blueprint(codigos_bp)

@app.route('/')
def home():
    return {'status': 'API funcionando 🎬'}

if __name__ == '__main__':
    app.run(debug=True, port=5001)
