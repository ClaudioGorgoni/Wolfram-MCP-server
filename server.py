import os
import json
import time
import requests
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Autorise Mistral à se connecter

WOLFRAM_API_KEY = os.environ.get("WOLFRAM_API_KEY")

@app.route('/health')
def health():
    return jsonify({"status": "ok", "key_configured": bool(WOLFRAM_API_KEY)})

@app.route('/sse')
def sse():
    def generate():
        # IMPORTANT : On dit à Mistral où envoyer les messages POST
        root_url = request.url_root.rstrip('/')
        yield f"event: endpoint\ndata: {root_url}/messages\n\n"
        
        while True:
            time.sleep(15)
            yield ": ping\n\n"
            
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/messages', methods=['POST'])
def messages():
    body = request.json
    method = body.get("method")
    msg_id = body.get("id")

    # 1. INITIALIZE (Mistral vérifie les capacités ici)
    if method == "initialize":
        return jsonify({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "logging": {}
                },
                "serverInfo": {
                    "name": "wolfram-mcp",
                    "version": "1.0.0"
                }
            }
        })

    # 2. TOOLS LIST (C'est ici que Mistral valide le connecteur)
    if method == "tools/list":
        return jsonify({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [{
                    "name": "query_wolfram",
                    "description": "Interroge Wolfram Alpha pour des calculs, de la physique ou des données.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "La question ou le calcul"
                            }
                        },
                        "required": ["query"]
                    }
                }]
            }
        })

    # 3. INITIALIZED (Notification de fin de handshake)
    if method == "notifications/initialized":
        return "", 204

    return jsonify({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Method not found"}})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))