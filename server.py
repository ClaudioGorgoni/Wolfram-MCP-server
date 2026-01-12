import os
import time
import json
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Autorise Mistral à communiquer avec Render

@app.route('/sse')
def sse():
    def generate():
        # 1. On récupère l'URL de base (ex: https://wolfram-mcp-server.onrender.com)
        host = request.url_root.rstrip('/')
        # 2. On envoie l'événement 'endpoint' (INDISPENSABLE pour Mistral)
        yield f"event: endpoint\ndata: {host}/messages\n\n"
        
        # Garde la connexion ouverte avec un ping
        while True:
            time.sleep(20)
            yield ": ping\n\n"
            
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/messages', methods=['POST'])
def messages():
    data = request.json
    method = data.get("method")
    msg_id = data.get("id")

    # Étape 1 : Initialisation
    if method == "initialize":
        return jsonify({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "wolfram", "version": "1.0.0"}
            }
        })
    
    # Étape 2 : Liste des outils (demandée juste après l'initialisation)
    if method == "tools/list":
        return jsonify({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [{
                    "name": "query_wolfram",
                    "description": "Calculs mathématiques et données Wolfram Alpha",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "La question en anglais"}
                        },
                        "required": ["query"]
                    }
                }]
            }
        })
    
    # Étape 3 : Exécution de l'outil
    if method == "tools/call":
        import requests
        query = data.get("params", {}).get("arguments", {}).get("query")
        appid = os.environ.get("WOLFRAM_API_KEY")
        
        r = requests.get(f"https://www.wolframalpha.com/api/v1/llm-api?input={query}&appid={appid}")
        return jsonify({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{"type": "text", "text": r.text}]
            }
        })

    return jsonify({"jsonrpc": "2.0", "id": msg_id, "result": {}})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))