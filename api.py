from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from data_engine import analyze

app = Flask(__name__, static_folder="static")
CORS(app)

@app.route("/")
def home():
    return send_from_directory("static", "index.html")

@app.route("/analyze", methods=["POST"])
def analyze_api():
    data = request.get_json(force=True)
    stocks = data.get("stocks", [])

    results = []
    for s in stocks:
        try:
            r = analyze(s)
            if r:
                results.append(r)
        except Exception as e:
            results.append({
                "Stock": s,
                "Verdict": "ERROR",
                "Score": 0,
                "Interpretation": str(e)
            })

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
