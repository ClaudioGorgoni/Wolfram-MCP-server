#!/usr/bin/env python3
import os
import json
import requests
import logging
from flask import Flask, request, jsonify, Response, stream_with_context
import time

# Configuration des logs pour voir ce qui se passe dans Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

WOLFRAM_API_KEY = os.environ.get("WOLFRAM_API_KEY")
PORT = os.environ.get("PORT", 10000)

# Définition de l'outil Wolfram
WOLFRAM_TOOL = {
    'name': 'query_wolfram',
    'description': 'Query Wolfram Alpha for mathematics, science, conversions, data analysis, etc.',
    'inputSchema': {
        'type': 'object',
        'properties': {
            'query': {
                'type': 'string',
                'description': 'Your question or calculation for Wolfram Alpha'
            }
        },
        'required': ['query']
    }
}

@app.route('/sse', methods=['GET'])
def sse():
    """Endpoint SSE - Point d'entrée de la connexion"""
    def generate():
        # ÉTAPE CRUCIALE : Dire au client où envoyer les requêtes POST
        # On utilise l'URL absolue pour éviter les ambiguïtés
        host = request.url_root.rstrip('/')
        endpoint_url = f"{host}/messages"
        
        logger.info(f"Connexion SSE ouverte. Envoi de l'endpoint: {endpoint_url}")
        
        # Format spécifique MCP : event: endpoint
        yield f"event: endpoint\ndata: {endpoint_url}\n\n"
        
        # Garde la connexion active
        while True:
            time.sleep(30)
            yield ": ping\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no' # Important pour Render/Nginx
        }
    )

@app.route('/messages', methods=['POST'])
def handle_messages():
    """Gère toutes les requêtes JSON-RPC (initialize, tools/list, tools/call)"""
    try:
        data = request.json
        method = data.get('method')
        msg_id = data.get('id')
        
        logger.info(f"Message reçu: {method}")

        # 1. Handshake : initialize
        if method == 'initialize':
            return jsonify({
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {
                        'tools': {} 
                    },
                    'serverInfo': {
                        'name': 'wolfram-server',
                        'version': '1.0.0'
                    }
                }
            })

        # 2. Handshake : notifications/initialized
        if method == 'notifications/initialized':
            # Pas de réponse attendue pour une notification, mais on log
            return '', 204

        # 3. Liste des outils : tools/list
        if method == 'tools/list':
            return jsonify({
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': {
                    'tools': [WOLFRAM_TOOL]
                }
            })

        # 4. Exécution : tools/call
        if method == 'tools/call':
            params = data.get('params', {})
            tool_name = params.get('name')
            args = params.get('arguments', {})
            
            if tool_name == 'query_wolfram':
                query = args.get('query')
                result_text = query_wolfram(query)
                
                return jsonify({
                    'jsonrpc': '2.0',
                    'id': msg_id,
                    'result': {
                        'content': [{
                            'type': 'text',
                            'text': result_text
                        }]
                    }
                })
            
            return jsonify({
                'jsonrpc': '2.0',
                'id': msg_id,
                'error': {'code': -32601, 'message': f'Tool {tool_name} not found'}
            })

        # Méthode inconnue
        return jsonify({
            'jsonrpc': '2.0',
            'id': msg_id,
            'error': {'code': -32601, 'message': 'Method not found'}
        })

    except Exception as e:
        logger.error(f"Erreur serveur: {e}")
        return jsonify({
            'jsonrpc': '2.0',
            'id': data.get('id') if data else None,
            'error': {'code': -32603, 'message': str(e)}
        })

def query_wolfram(query):
    """Interroge l'API Wolfram LLM"""
    if not WOLFRAM_API_KEY:
        return "Erreur de configuration : Clé API Wolfram manquante sur le serveur."
    
    # URL spécifique pour l'API LLM de Wolfram
    url = "https://www.wolframalpha.com/api/v1/llm-api"
    params = {
        'input': query,
        'appid': WOLFRAM_API_KEY,
        'maxchars': 6000
    }
    
    try:
        response = requests.get(url, params=params, timeout=45)
        if response.status_code == 200:
            return response.text.strip()
        elif response.status_code == 403:
            return "Erreur 403: Vérifiez votre App ID Wolfram."
        elif response.status_code == 501:
            return "Wolfram n'a pas pu traiter cette demande spécifique."
        else:
            return f"Erreur Wolfram (Code {response.status_code})"
    except Exception as e:
        return f"Erreur de connexion à Wolfram: {str(e)}"

# Compatibilité manifest (optionnel mais recommandé)
@app.route('/.well-known/mcp.json', methods=['GET'])
def mcp_manifest():
    host = request.url_root.rstrip('/')
    return jsonify({
        "name": "wolfram-alpha",
        "version": "1.0.0",
        "endpoints": {
            "mcp": {
                "type": "sse",
                "url": f"{host}/sse"
            }
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'wolfram_key_present': bool(WOLFRAM_API_KEY)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(PORT))