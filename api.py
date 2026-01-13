import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from engine import analyze

app = Flask(__name__, static_folder="static")
CORS(app)

@app.route("/")
def home():
    return send_from_directory("static", "index.html")

@app.route("/analyze", methods=["POST"])
def analyze_api():
    stocks = request.json.get("stocks", [])
    results = []

    for s in stocks:
        r = analyze(s)
        if r:
            results.append(r)

    return jsonify(results)

if __name__ == "__main__":
    # ✅ REQUIRED FOR RENDER
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
