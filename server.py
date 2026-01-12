#!/usr/bin/env python3
import os
import json
import requests
import logging
import time
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS  # Nouvelle importation critique

# Logs pour le débogage Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Autorise toutes les origines (requis pour Mistral)

WOLFRAM_API_KEY = os.environ.get("WOLFRAM_API_KEY")
PORT = os.environ.get("PORT", 10000)

@app.route('/sse', methods=['GET'])
def sse():
    """Endpoint de connexion persistante"""
    def generate():
        host = request.url_root.rstrip('/')
        endpoint_url = f"{host}/messages"
        logger.info(f"SSE Client connected. Sending endpoint: {endpoint_url}")
        
        # Envoi immédiat de l'endpoint
        yield f"event: endpoint\ndata: {endpoint_url}\n\n"
        
        # Ping régulier pour éviter le timeout (toutes les 15s)
        while True:
            time.sleep(15)
            yield ": ping\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no' # Critique pour Render
        }
    )

@app.route('/messages', methods=['POST'])
def handle_messages():
    """Endpoint principal JSON-RPC"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
            
        method = data.get('method')
        msg_id = data.get('id')
        logger.info(f"Message received: {method}")

        # 1. INITIALIZE
        if method == 'initialize':
            return jsonify({
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {
                        'tools': {} # Le serveur supporte les outils
                    },
                    'serverInfo': {
                        'name': 'wolfram-mcp',
                        'version': '1.0.0'
                    }
                }
            })

        # 2. TOOLS LIST
        if method == 'tools/list':
            return jsonify({
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': {
                    'tools': [{
                        'name': 'query_wolfram',
                        'description': 'Query Wolfram Alpha. Use for math, physics, chemistry, data analysis. Input should be a precise query in English.',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'query': {'type': 'string', 'description': 'The query for Wolfram Alpha'}
                            },
                            'required': ['query']
                        }
                    }]
                }
            })

        # 3. TOOLS CALL
        if method == 'tools/call':
            params = data.get('params', {})
            tool_name = params.get('name')
            args = params.get('arguments', {})
            
            if tool_name == 'query_wolfram':
                query = args.get('query')
                logger.info(f"Calling Wolfram with: {query}")
                result = call_wolfram_api(query)
                return jsonify({
                    'jsonrpc': '2.0',
                    'id': msg_id,
                    'result': {
                        'content': [{'type': 'text', 'text': result}]
                    }
                })

        # 4. Notifications (ignorer)
        if method and 'notifications' in method:
            return '', 200

        return jsonify({'jsonrpc': '2.0', 'error': {'code': -32601, 'message': 'Method not found'}, 'id': msg_id})

    except Exception as e:
        logger.error(f"Error in messages: {e}")
        return jsonify({'jsonrpc': '2.0', 'error': {'code': 500, 'message': str(e)}, 'id': data.get('id')})

def call_wolfram_api(query):
    if not WOLFRAM_API_KEY:
        return "Error: Wolfram API Key not configured on server."
    
    url = "https://www.wolframalpha.com/api/v1/llm-api"
    try:
        response = requests.get(url, params={'input': query, 'appid': WOLFRAM_API_KEY}, timeout=30)
        if response.status_code == 200:
            return response.text
        return f"Wolfram Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    # Local dev run
    app.run(host='0.0.0.0', port=int(PORT), debug=True)