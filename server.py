import os
import json
import time
import requests
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

WOLFRAM_API_KEY = os.environ.get("WOLFRAM_API_KEY")

# --- AJOUT : Route Racine pour éviter la 404 ---
@app.route('/')
def index():
    return jsonify({
        "status": "Wolfram MCP Server is Running",
        "endpoints": ["/sse", "/messages", "/health"]
    }), 200

@app.route('/health')
def health():
    return jsonify({"status": "ok", "key_configured": bool(WOLFRAM_API_KEY)})

@app.route('/sse')
def sse():
    def generate():
        host = request.url_root.rstrip('/')
        # On dit explicitement à Mistral où envoyer les POST
        yield f"event: endpoint\ndata: {host}/messages\n\n"
        while True:
            time.sleep(20)
            yield ": ping\n\n"
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/messages', methods=['POST'])
def messages():
    body = request.json
    if not body: return jsonify({"error": "No JSON"}), 400
    
    method = body.get("method")
    msg_id = body.get("id")

    # Log pour débugger dans Render
    print(f"--- Requête MCP reçue : {method} (ID: {msg_id}) ---")

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
        args = body.get("params", {}).get("arguments", {})
        query = args.get("query")
        r = requests.get(f"https://www.wolframalpha.com/api/v1/llm-api?input={query}&appid={WOLFRAM_API_KEY}")
        return jsonify({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"content": [{"type": "text", "text": r.text}]}
        })

    return jsonify({"jsonrpc": "2.0", "id": msg_id, "result": {}})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))