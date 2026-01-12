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

    # Log pour voir ce que Mistral envoie (visible dans les logs Render)
    print(f"Méthode reçue : {method}")

    if method == "initialize":
        return jsonify({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "wolfram-mcp", "version": "1.0.0"}
            }
        })

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

    if method == "tools/call":
        query = body.get("params", {}).get("arguments", {}).get("query")
        # Appel à Wolfram
        r = requests.get(f"https://www.wolframalpha.com/api/v1/llm-api?input={query}&appid={WOLFRAM_API_KEY}")
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