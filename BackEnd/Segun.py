import os
from flask import jsonify, request
from functools import wraps
import logging
import hmac
import hashlib

# Configuração de logging para o módulo de segurança
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('security.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configurações de segurança
SECURITY_CONFIG = {
    'API_KEY': os.getenv('API_KEY', 'GHSGhjsfKFGfhgdrdcyYURr5465YUclycoCGHHVGHx'),  # Defina via variável de ambiente
    'ALLOWED_ORIGINS': ['https://filmes-frontend.vercel.app'],
}

def require_api_key(f):
    """Decorator para exigir uma API key válida nos endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            logger.warning("Tentativa de acesso sem API key")
            return jsonify({"erro": "API key não fornecida"}), 401
        
        if not hmac.compare_digest(
            hmac.new(SECURITY_CONFIG['API_KEY'].encode(), digestmod=hashlib.sha256).hexdigest(),
            hmac.new(api_key.encode(), digestmod=hashlib.sha256).hexdigest()
        ):
            logger.warning(f"API key inválida: {api_key}")
            return jsonify({"erro": "API key inválida"}), 401
        
        return f(*args, **kwargs)
    return decorated

def check_origin(f):
    """Decorator para verificar a origem da requisição."""
    @wraps(f)
    def decorated(*args, **kwargs):
        origin = request.headers.get('Origin')
        if origin not in SECURITY_CONFIG['ALLOWED_ORIGINS']:
            logger.warning(f"Origem não permitida: {origin}")
            return jsonify({"erro": "Origem não autorizada"}), 403
        return f(*args, **kwargs)
    return decorated