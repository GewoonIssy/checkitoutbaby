from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup
import os
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("API_KEY", "dev-placeholder")

FLEET_KEYWORDS = ["fleetowner"]
POLICE_KEYWORDS = ["politie", "undercover"]

def fetch_finnik_html(kenteken):
    # Gratis historie pagina
    url = f"https://finnik.nl/kenteken/{kenteken}/gratis#historie"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise Exception(f"Failed to fetch Finnik page, status {r.status_code}")
    return r.text

def parse_owners(soup):
    owners = []
    history_section = soup.select_one('section[data-sectiontype="History"]')
    if history_section:
        value_divs = history_section.select('div.col-6.col-sm-7.value')
        for div in value_divs:
            text = div.get_text(strip=True)
            if text:
                owners.append({"raw": text, "name": f"Huidige eigenaar {text}", "dates": []})
    return owners

def classify(owners, basic_label=None):
    classification = "Unclear / likely private"
    confidence = 0.18
    last_owner_name = ""
    reasons = []
    if owners:
        last_owner_name = owners[-1]["name"]
        if any(k.lower() in owners[-1]["raw"].lower() for k in FLEET_KEYWORDS):
            classification = "Likely undercover/fleetowner"
            confidence = 0.95
            reasons.append("Eigenaarstype expliciet aangegeven als Fleetowner")
        else:
            classification = "Likely private"
            confidence = 0.85
    else:
        reasons.append("Geen eigenarenhistorie gevonden (gratis Finnik gebruikt)")
        if basic_label:
            reasons.append(f"Finnik label: {basic_label}")
    return {"classification": classification, "confidence": confidence, "last_owner_name": last_owner_name, "reasons": reasons, "score": 10 if classification=="Likely undercover/fleetowner" else 2}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["GET"])
def analyze():
    key = request.headers.get("X-API-Key") or request.args.get("api_key")
    if key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    kenteken = request.args.get("kenteken")
    if not kenteken:
        return jsonify({"error":"kenteken required"}), 400
    try:
        html = fetch_finnik_html(kenteken)
    except Exception as e:
        return jsonify({"error":"Failed to fetch Finnik", "detail": str(e)}), 500
    soup = BeautifulSoup(html, "html.parser")
    basic_label = soup.select_one('div#basic-info')  # fallback, kan leeg
    basic_label_text = basic_label.get_text(strip=True) if basic_label else "Onbekend"
    owners = parse_owners(soup)
    result = classify(owners, basic_label_text)
    payload = {"kenteken": kenteken, "basic": {"finnik_label": basic_label_text}, "owners_raw": owners, "analysis": result}
    return jsonify(payload), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup
import os
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("API_KEY", "dev-placeholder")

FLEET_KEYWORDS = ["fleetowner"]

def fetch_finnik_html(kenteken):
    url = f"https://finnik.nl/kenteken/{kenteken}/gratis#historie"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise Exception(f"Failed to fetch Finnik page, status {r.status_code}")
    return r.text

def parse_owners(soup):
    owners = []
    history_section = soup.select_one('section[data-sectiontype="History"]')
    if history_section:
        value_divs = history_section.select('div.col-6.col-sm-7.value')
        for div in value_divs:
            text = div.get_text(strip=True)
            if text:
                owners.append({"raw": text, "name": f"Huidige eigenaar {text}", "dates": []})
    return owners

def classify(owners, basic_label=None):
    classification = "Unclear / likely private"
    confidence = 0.18
    last_owner_name = ""
    reasons = []
    if owners:
        last_owner_name = owners[-1]["name"]
        if any(k.lower() in owners[-1]["raw"].lower() for k in FLEET_KEYWORDS):
            classification = "Likely undercover/fleetowner"
            confidence = 0.95
            reasons.append("Eigenaarstype expliciet aangegeven als Fleetowner")
        else:
            classification = "Likely private"
            confidence = 0.85
    else:
        reasons.append("Geen eigenarenhistorie gevonden (gratis Finnik gebruikt)")
        if basic_label:
            reasons.append(f"Finnik label: {basic_label}")
    return {"classification": classification, "confidence": confidence, "last_owner_name": last_owner_name, "reasons": reasons, "score": 10 if classification=="Likely undercover/fleetowner" else 2}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["GET"])
def analyze():
    key = request.headers.get("X-API-Key") or request.args.get("api_key")
    if key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    kenteken = request.args.get("kenteken")
    if not kenteken:
        return jsonify({"error":"kenteken required"}), 400
    try:
        html = fetch_finnik_html(kenteken)
    except Exception as e:
        return jsonify({"error":"Failed to fetch Finnik", "detail": str(e)}), 500
    soup = BeautifulSoup(html, "html.parser")
    basic_label_text = "Onbekend"
    owners = parse_owners(soup)
    result = classify(owners, basic_label_text)
    payload = {"kenteken": kenteken, "basic": {"finnik_label": basic_label_text}, "owners_raw": owners, "analysis": result}
    return jsonify(payload), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
