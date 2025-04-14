from flask import Flask
from flask_cors import CORS
from BackEnd.routes import blueprints  # importa a lista de blueprints

app = Flask(__name__)
CORS(app)

# Registrar todos os blueprints definidos em routes/__init__.py
for bp in blueprints:
    app.register_blueprint(bp)

@app.route('/')
def home():
    return {'status': 'API funcionando 🎬'}

if __name__ == '__main__':
    app.run(debug=True, port=5001)
