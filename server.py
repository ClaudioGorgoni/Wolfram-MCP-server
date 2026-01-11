#!/usr/bin/env python3
import os
import json
import requests
from flask import Flask, request, jsonify, Response
import time

app = Flask(__name__)

# Configuration - utilise WOLFRAM_API_KEY comme sur Render
WOLFRAM_API_KEY = os.environ.get("WOLFRAM_API_KEY")
PORT = os.environ.get("PORT", 10000)

def query_wolfram(query, maxchars=6800):
    """Fonction pour interroger Wolfram Alpha API"""
    if not WOLFRAM_API_KEY:
        return "Erreur: Clé API Wolfram non configurée (WOLFRAM_API_KEY manquante)"
    
    url = "https://www.wolframalpha.com/api/v1/llm-api"
    params = {
        'input': query,
        'appid': WOLFRAM_API_KEY,
        'maxchars': maxchars
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            result = response.text.strip()
            if not result or "Wolfram Alpha did not understand your input" in result:
                return "Wolfram Alpha n'a pas pu fournir une réponse claire. Essayez de reformuler votre question."
            return result
        elif response.status_code == 403:
            return "Erreur d'authentification Wolfram. Vérifiez votre APP ID."
        else:
            return f"Erreur Wolfram (HTTP {response.status_code})"
    except Exception as e:
        return f"Erreur de connexion: {str(e)}"

@app.route('/.well-known/mcp.json', methods=['GET'])
def mcp_manifest():
    """Manifest MCP pour Mistral Platform - URL ABSOLUE pour SSE"""
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
                # URL ABSOLUE - IMPORTANT pour Mistral
                "url": "https://wolfram-mcp-server.onrender.com/sse"
            }
        }
    })

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
                                'description': 'Maximum characters in response (default: 6800)',
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
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
    )

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

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de santé"""
    return jsonify({
        'status': 'healthy',
        'service': 'wolfram-mcp-server',
        'wolfram_configured': bool(WOLFRAM_API_KEY),
        'app_id_prefix': WOLFRAM_API_KEY[:4] + '...' if WOLFRAM_API_KEY else None,
        'endpoints': {
            'manifest': 'https://wolfram-mcp-server.onrender.com/.well-known/mcp.json',
            'sse': 'https://wolfram-mcp-server.onrender.com/sse',
            'tools': 'https://wolfram-mcp-server.onrender.com/tools/call'
        }
    })

@app.route('/')
def index():
    """Page d'accueil"""
    return jsonify({
        'service': 'Wolfram Alpha MCP Server',
        'version': '1.0',
        'status': 'running',
        'url': 'https://wolfram-mcp-server.onrender.com',
        'usage': {
            'mistral_platform': 'Use https://wolfram-mcp-server.onrender.com/.well-known/mcp.json as manifest URL',
            'test_query': 'curl -X POST https://wolfram-mcp-server.onrender.com/tools/call -H "Content-Type: application/json" -d \'{"jsonrpc":"2.0","method":"tools/call","params":{"name":"query_wolfram","arguments":{"query":"2+2"}},"id":1}\''
        }
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Wolfram Alpha MCP Server")
    print("=" * 60)
    print(f"📡 URL: https://wolfram-mcp-server.onrender.com")
    print(f"🔌 Port: {PORT}")
    
    if WOLFRAM_API_KEY:
        print(f"✅ WOLFRAM_API_KEY configurée: {WOLFRAM_API_KEY[:4]}...")
        print(f"🔗 Manifest: https://wolfram-mcp-server.onrender.com/.well-known/mcp.json")
    else:
        print("❌ WOLFRAM_API_KEY non configurée!")
        print("   Configurez la variable d'environnement sur Render")
    
    print("=" * 60)
    app.run(host='0.0.0.0', port=int(PORT), debug=False)