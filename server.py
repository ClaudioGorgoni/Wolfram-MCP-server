#!/usr/bin/env python3
import os
import json
from flask import Flask, request, jsonify, Response
import requests
import time
import urllib.parse

app = Flask(__name__)

# Configuration
WOLFRAM_API_KEY = os.environ.get("WOLFRAM_API_KEY")
PORT = int(os.environ.get("PORT", 8000))

# Endpoint de l'API LLM de Wolfram
WOLFRAM_LLM_API_URL = "https://www.wolframalpha.com/api/v1/llm-api"

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de santé pour Render"""
    return jsonify({
        "status": "healthy",
        "service": "wolfram-mcp-server",
        "api_key_configured": bool(WOLFRAM_API_KEY)
    })

@app.route('/mcp', methods=['POST'])
def mcp_endpoint():
    """Endpoint principal MCP"""
    try:
        data = request.json
        method = data.get('method')
        
        if method == 'tools/list':
            return jsonify({
                "tools": [
                    {
                        "name": "query_wolfram",
                        "description": "Interroge Wolfram Alpha pour des calculs mathématiques complexes, conversions d'unités, données scientifiques, statistiques, résolution d'équations, graphiques, faits encyclopédiques, etc. Optimisé pour l'intégration avec les LLM.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "La question, le calcul ou la requête à soumettre à Wolfram Alpha. Peut être en langage naturel."
                                },
                                "maxchars": {
                                    "type": "integer",
                                    "description": "Limite optionnelle de caractères dans la réponse (défaut: 6800)",
                                    "default": 6800
                                }
                            },
                            "required": ["query"]
                        }
                    }
                ]
            })
        
        elif method == 'tools/call':
            tool_name = data.get('params', {}).get('name')
            arguments = data.get('params', {}).get('arguments', {})
            
            if tool_name == 'query_wolfram':
                query = arguments.get('query')
                maxchars = arguments.get('maxchars', 6800)
                
                if not WOLFRAM_API_KEY:
                    return jsonify({
                        "content": [{
                            "type": "text",
                            "text": "❌ Erreur: Clé API Wolfram Alpha non configurée sur le serveur."
                        }],
                        "isError": True
                    })
                
                if not query:
                    return jsonify({
                        "content": [{
                            "type": "text",
                            "text": "❌ Erreur: Le paramètre 'query' est obligatoire."
                        }],
                        "isError": True
                    })
                
                # Appel à l'API Wolfram LLM avec paramètres optimisés
                params = {
                    "appid": WOLFRAM_API_KEY,
                    "input": query,
                    "maxchars": maxchars
                }
                
                try:
                    response = requests.get(
                        WOLFRAM_LLM_API_URL, 
                        params=params, 
                        timeout=20
                    )
                    
                    # Gestion détaillée des codes d'erreur selon la documentation
                    if response.status_code == 200:
                        result = response.text.strip()
                        
                        if not result:
                            result = "⚠️ Wolfram Alpha n'a pas pu fournir de réponse pour cette requête."
                        elif "Wolfram Alpha did not understand your input" in result:
                            result = "⚠️ Wolfram Alpha n'a pas compris la requête. Essayez de reformuler ou simplifier la question."
                    
                    elif response.status_code == 400:
                        result = "❌ Erreur 400: Le paramètre 'input' est manquant ou mal formaté."
                    
                    elif response.status_code == 403:
                        error_text = response.text.lower()
                        if "invalid" in error_text:
                            result = "🔒 Erreur 403: Clé API Wolfram invalide. Vérifiez votre AppID."
                        elif "missing" in error_text:
                            result = "🔒 Erreur 403: AppID manquant dans la requête."
                        else:
                            result = "🔒 Erreur 403: Problème d'authentification avec Wolfram Alpha."
                    
                    elif response.status_code == 501:
                        result = "⚠️ Erreur 501: Wolfram Alpha ne peut pas interpréter cette requête. Suggestions:\n"
                        result += "- Vérifiez l'orthographe\n"
                        result += "- Simplifiez la question\n"
                        result += "- Utilisez des mots-clés plutôt que des phrases longues\n"
                        result += f"\nRéponse brute: {response.text[:200]}"
                    
                    else:
                        result = f"❌ Erreur HTTP {response.status_code}: {response.text[:200]}"
                    
                    return jsonify({
                        "content": [{
                            "type": "text",
                            "text": result
                        }]
                    })
                    
                except requests.Timeout:
                    return jsonify({
                        "content": [{
                            "type": "text",
                            "text": "⏱️ Timeout (20s): Wolfram Alpha met trop de temps à répondre. Essayez avec une requête plus simple."
                        }],
                        "isError": True
                    })
                    
                except requests.ConnectionError:
                    return jsonify({
                        "content": [{
                            "type": "text",
                            "text": "🌐 Erreur de connexion: Impossible de joindre Wolfram Alpha. Vérifiez votre connexion internet."
                        }],
                        "isError": True
                    })
                    
                except requests.RequestException as e:
                    return jsonify({
                        "content": [{
                            "type": "text",
                            "text": f"❌ Erreur de requête HTTP: {str(e)}"
                        }],
                        "isError": True
                    })
                    
                except Exception as e:
                    return jsonify({
                        "content": [{
                            "type": "text",
                            "text": f"❌ Erreur inattendue: {str(e)}"
                        }],
                        "isError": True
                    })
        
        return jsonify({"error": "Méthode MCP non supportée"}), 400
        
    except json.JSONDecodeError:
        return jsonify({"error": "JSON invalide dans la requête"}), 400
    except Exception as e:
        return jsonify({"error": f"Erreur serveur: {str(e)}"}), 500

@app.route('/mcp/sse', methods=['GET'])
def mcp_sse():
    """Endpoint SSE pour MCP (optionnel)"""
    def generate():
        yield f"data: {json.dumps({'type': 'connected', 'service': 'wolfram-mcp-server'})}\n\n"
        
        while True:
            time.sleep(30)
            yield f"data: {json.dumps({'type': 'ping', 'timestamp': time.time()})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/', methods=['GET'])
def root():
    """Page d'accueil informative"""
    return jsonify({
        "service": "Wolfram Alpha MCP Server",
        "version": "1.1",
        "status": "running",
        "api_configured": bool(WOLFRAM_API_KEY),
        "endpoints": {
            "/": "Informations sur le service",
            "/health": "Vérification de l'état du serveur",
            "/mcp": "Endpoint MCP principal (POST)",
            "/mcp/sse": "Server-Sent Events (GET)"
        },
        "documentation": "https://products.wolframalpha.com/llm-api/documentation"
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint non trouvé",
        "available_endpoints": ["/", "/health", "/mcp", "/mcp/sse"]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Erreur interne du serveur",
        "message": str(error)
    }), 500

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Wolfram Alpha MCP Server")
    print("=" * 50)
    
    if not WOLFRAM_API_KEY:
        print("⚠️  ATTENTION: Variable d'environnement WOLFRAM_API_KEY non définie!")
        print("   Le serveur démarrera mais les requêtes échoueront.")
    else:
        print("✅ Clé API Wolfram configurée")
    
    print(f"📍 Port: {PORT}")
    print(f"🌐 Endpoints:")
    print(f"   - Health: http://0.0.0.0:{PORT}/health")
    print(f"   - MCP: http://0.0.0.0:{PORT}/mcp")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=PORT, debug=False)