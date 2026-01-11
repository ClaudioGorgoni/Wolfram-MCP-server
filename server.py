#!/usr/bin/env python3
import os
import json
import requests
from flask import Flask, request, jsonify, Response
import time

app = Flask(__name__)

WOLFRAM_API_KEY = os.environ.get("WOLFRAM_API_KEY")
PORT = os.environ.get("PORT", 10000)

# Ajoutez cette fonction pour supporter /mcp ET /sse
@app.route('/mcp', methods=['GET'])
def mcp_sse():
    """Endpoint MCP pour Mistral (support /mcp et /sse)"""
    return sse()

@app.route('/sse', methods=['GET'])
def sse():
    """Endpoint SSE - fournit les outils disponibles"""
    def generate():
        # Liste des outils
        yield f"data: {json.dumps({
            'jsonrpc': '2.0',
            'id': 1,
            'result': {
                'tools': [{
                    'name': 'query_wolfram',
                    'description': 'Query Wolfram Alpha for mathematics, science, conversions, data analysis, etc.',
                    'inputSchema': {
                        'type': 'object',
                        'properties': {
                            'query': {
                                'type': 'string',
                                'description': 'Your question or calculation for Wolfram Alpha'
                            },
                            'maxchars': {
                                'type': 'integer',
                                'description': 'Maximum characters in response',
                                'default': 6800
                            }
                        },
                        'required': ['query']
                    }
                }]
            }
        })}\n\n"
        
        # Garde la connexion active
        while True:
            time.sleep(30)
            yield f"data: {json.dumps({'jsonrpc': '2.0', 'method': 'ping'})}\n\n"
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    )

@app.route('/.well-known/mcp.json', methods=['GET'])
def mcp_manifest():
    """Manifest MCP - pointe vers /mcp pour compatibilité"""
    return jsonify({
        "name": "wolfram-alpha",
        "description": "Wolfram Alpha computational intelligence",
        "version": "1.0.0",
        "protocol_version": "2024-11-05",
        "capabilities": {
            "tools": {}
        },
        "endpoints": {
            "mcp": {
                "type": "sse",
                "url": "https://wolfram-mcp-server.onrender.com/mcp"
            }
        }
    })

# Gardez le reste de votre code (query_wolfram, /tools/call, etc.)
@app.route('/tools/call', methods=['POST'])
def tools_call():
    """Endpoint pour exécuter les outils"""
    try:
        data = request.json
        
        if data.get('method') == 'tools/call':
            tool_name = data.get('params', {}).get('name')
            args = data.get('params', {}).get('arguments', {})
            
            if tool_name == 'query_wolfram':
                query = args.get('query')
                if not query:
                    return jsonify({
                        'jsonrpc': '2.0',
                        'error': {'code': -32602, 'message': 'Missing query parameter'},
                        'id': data.get('id')
                    })
                
                # Fonction query_wolfram à définir
                maxchars = args.get('maxchars', 6800)
                result = query_wolfram(query, maxchars)
                
                return jsonify({
                    'jsonrpc': '2.0',
                    'id': data.get('id'),
                    'result': {
                        'content': [{
                            'type': 'text',
                            'text': result
                        }]
                    }
                })
        
        return jsonify({
            'jsonrpc': '2.0',
            'error': {'code': -32601, 'message': 'Method not found'},
            'id': data.get('id')
        })
    
    except Exception as e:
        return jsonify({
            'jsonrpc': '2.0',
            'error': {'code': -32603, 'message': f'Server error: {str(e)}'},
            'id': data.get('id')
        })

def query_wolfram(query, maxchars=6800):
    """Fonction pour interroger Wolfram Alpha API"""
    if not WOLFRAM_API_KEY:
        return "Erreur: Clé API Wolfram non configurée"
    
    url = "https://www.wolframalpha.com/api/v1/llm-api"
    params = {
        'input': query,
        'appid': WOLFRAM_API_KEY,
        'maxchars': maxchars
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            return response.text.strip()
        else:
            return f"Erreur Wolfram (HTTP {response.status_code})"
    except Exception as e:
        return f"Erreur de connexion: {str(e)}"

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'endpoints': {
            'mcp_sse': 'https://wolfram-mcp-server.onrender.com/mcp',
            'sse': 'https://wolfram-mcp-server.onrender.com/sse',
            'tools': 'https://wolfram-mcp-server.onrender.com/tools/call'
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(PORT), debug=False)