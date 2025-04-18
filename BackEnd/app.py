from flask import Flask
from flask_cors import CORS
from routes import registrar_rotas, atualizar_codigos_inicial

# Criação da aplicação Flask
app = Flask(__name__)
CORS(app)

# Registrando as rotas
registrar_rotas(app)

# Função para atualizar os códigos no início
if __name__ == '__main__':
    atualizar_codigos_inicial(app)
    app.run(debug=True, port=5001)
