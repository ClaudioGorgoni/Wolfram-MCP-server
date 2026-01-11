#!/usr/bin/env python3
import os
import json
import requests
from flask import Flask, request, jsonify, Response
import time

app = Flask(__name__)

# Configuration
WOLFRAM_APP_ID = os.environ.get("WOLFRAM_APP_ID")
PORT = os.environ.get("PORT", 10000)

@app.route('/.well-known/mcp.json', methods=['GET'])
def mcp_manifest():
    """Manifest MCP pour Mistral"""
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
                "url": f"/sse"
            }
        }
    })

@app.route('/sse', methods=['GET'])
def sse():
    """Endpoint SSE pour MCP"""
    def generate():
        # Envoi initial des outils disponibles
        yield f"data: {json.dumps({
            'jsonrpc': '2.0',
            'id': 1,
            'result': {
                'tools': [{
                    'name': 'query_wolfram',
                    'description': 'Query Wolfram Alpha for math, science, conversions, etc.',
                    'inputSchema': {
                        'type': 'object',
                        'properties': {
                            'query': {
                                'type': 'string',
                                'description': 'Question for Wolfram Alpha'
                            },
                            'maxchars': {
                                'type': 'integer',
                                'description': 'Max characters in response',
                                'default': 6800
                            }
                        },
                        'required': ['query']
                    }
                }]
            }
        })}\n\n"
        
        # Garder la connexion active
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

@app.route('/tools/call', methods=['POST'])
def tool_call():
    """Endpoint pour appeler Wolfram Alpha"""
    try:
        data = request.json
        method = data.get('method')
        
        if method == 'tools/call':
            params = data.get('params', {})
            tool_name = params.get('name')
            args = params.get('arguments', {})
            
            if tool_name == 'query_wolfram':
                query = args.get('query')
                maxchars = args.get('maxchars', 6800)
                
                if not query:
                    return jsonify({
                        'jsonrpc': '2.0',
                        'error': {
                            'code': -32602,
                            'message': 'Missing required parameter: query'
                        },
                        'id': data.get('id')
                    })
                
                if not WOLFRAM_APP_ID:
                    return jsonify({
                        'jsonrpc': '2.0',
                        'error': {
                            'code': -32603,
                            'message': 'Wolfram APP ID not configured'
                        },
                        'id': data.get('id')
                    })
                
                # Appel à l'API Wolfram
                url = "https://www.wolframalpha.com/api/v1/llm-api"
                params = {
                    'input': query,
                    'appid': WOLFRAM_APP_ID,
                    'maxchars': maxchars
                }
                
                response = requests.get(url, params=params, timeout=30)
                
                if response.status_code == 200:
                    result = response.text
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
                else:
                    return jsonify({
                        'jsonrpc': '2.0',
                        'id': data.get('id'),
                        'error': {
                            'code': response.status_code,
                            'message': f"Wolfram API error: {response.text[:100]}"
                        }
                    })
        
        return jsonify({
            'jsonrpc': '2.0',
            'error': {
                'code': -32601,
                'message': 'Method not found'
            },
            'id': data.get('id')
        })
    
    except Exception as e:
        return jsonify({
            'jsonrpc': '2.0',
            'error': {
                'code': -32603,
                'message': f"Internal error: {str(e)}"
            },
            'id': data.get('id')
        })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'wolfram_configured': bool(WOLFRAM_APP_ID)
    })

@app.route('/')
def index():
    return jsonify({
        'name': 'Wolfram Alpha MCP Server',
        'version': '1.0',
        'endpoints': {
            '/.well-known/mcp.json': 'MCP Manifest',
            '/sse': 'SSE endpoint',
            '/tools/call': 'Tool call endpoint',
            '/health': 'Health check'
        }
    })

if __name__ == '__main__':
    print(f"🚀 Wolfram Alpha MCP Server starting...")
    print(f"📡 Port: {PORT}")
    print(f"🔑 Wolfram APP ID: {'Configured' if WOLFRAM_APP_ID else 'NOT CONFIGURED'}")
    app.run(host='0.0.0.0', port=int(PORT), debug=False)