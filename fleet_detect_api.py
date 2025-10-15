from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import re
import os
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("API_KEY", "dev-placeholder")

FLEET_KEYWORDS = ["lease","autolease","fleet","mobiliteit","leaseplan","athlon","arval","alphabet","pon","bentley","leasebedrijf","verhuur","maatschappij"]
POLICE_KEYWORDS = ["politie","ministerie","rijksoverheid","gemeente","municipal"]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FleetDetector/1.0; +https://example.org)"}

def require_api_key(req):
    key = req.headers.get("X-API-Key") or req.args.get("api_key")
    return key == API_KEY

def fetch_finnik_html(kenteken):
    url = f"https://finnik.nl/kenteken/{kenteken}/gratis#historie"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.text

def parse_finnik_basic(soup):
    data = {}
    title_elem = soup.select_one("h1") or soup.select_one("title")
    data['title'] = title_elem.get_text(strip=True) if title_elem else "Onbekend"
    label_elem = soup.find(text=re.compile(r"Voertuig is geregistreerd", re.I))
    data['finnik_label'] = label_elem.strip() if label_elem else None
    return data

def parse_owners(soup):
    owners = []
    history_section = soup.select_one('section[data-sectiontype="History"]')
    if history_section:
        value_divs = history_section.select('div.col-6.col-sm-7.value')
        for div in value_divs:
            text = div.get_text(strip=True)
            if text and ('fleetowner' in text.lower() or 'eigenaar' in text.lower()):
                owners.append({"raw": text, "name": f"Huidige eigenaar {text}", "dates": []})
    return owners

def keyword_detect(name):
    nm = (name or "").lower()
    for k in FLEET_KEYWORDS + POLICE_KEYWORDS:
        if k in nm:
            return k
    return None

def classify(owners_list, eigenaarstype_label):
    reasons = []
    score = 0
    last_owner_name = ""
    if not owners_list:
        return {"score":0, "confidence":0.0, "classification":"Unclear / no data",
                "reasons":["Geen relevante eigenaren gevonden"], "last_owner_name":last_owner_name}
    last_owner_name = owners_list[-1]['name']

    if any('fleetowner' in o['raw'].lower() for o in owners_list):
        score = 10
        reasons.append("Eigenaarstype expliciet aangegeven als Fleetowner")
        classification = "Likely undercover/fleetowner"
        confidence = 0.95
        return {"score":score, "confidence":confidence, "classification":classification,
                "reasons":reasons, "last_owner_name":last_owner_name}

    kw = keyword_detect(last_owner_name)
    if kw:
        if kw in POLICE_KEYWORDS:
            score += 8
            reasons.append(f"Police/government keyword found in owner name: {kw}")
        else:
            score += 5
            reasons.append(f"Fleet/lease keyword found in owner name: {kw}")

    if eigenaarstype_label and 'rechtspersoon' in eigenaarstype_label.lower():
        score += 2
        reasons.append("Finnik label is generiek 'rechtspersoon'")

    max_score = 10
    confidence = min(1.0, score / max_score)
    classification = "Likely undercover/fleetowner" if confidence >= 0.45 else "Unclear / likely private"
    return {"score":score, "confidence":round(confidence,2), "classification":classification,
            "reasons":reasons, "last_owner_name":last_owner_name}

@app.route("/analyze", methods=["GET"])
def analyze():
    if not require_api_key(request):
        return jsonify({"error": "Unauthorized"}), 401
    kenteken = request.args.get("kenteken")
    if not kenteken:
        return jsonify({"error":"kenteken required"}), 400
    try:
        html = fetch_finnik_html(kenteken)
    except Exception as e:
        return jsonify({"error":"Failed to fetch Finnik", "detail": str(e)}), 500
    soup = BeautifulSoup(html, "html.parser")
    basic = parse_finnik_basic(soup)
    owners = parse_owners(soup)
    result = classify(owners, basic.get("finnik_label"))
    payload = {"kenteken": kenteken, "basic": basic, "owners_raw": owners, "analysis": result}
    return jsonify(payload), 200

if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 3000))
    app.run(host=host, port=port)
