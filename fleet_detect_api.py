from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup
import os
from flask_cors import CORS
from dotenv import load_dotenv
import re

load_dotenv()
app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("API_KEY", "dev-placeholder")
FLEET_KEYWORDS = ["fleetowner"]
POLICE_KEYWORDS = ["politie", "undercover"]

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
            text = div.get_text(separator=" ", strip=True)
            if text and len(text) > 2:
                owners.append({"raw": text, "name": f"Huidige eigenaar {text}", "dates": []})
    return owners

def parse_car_summary(soup):
    # Fabrikant + model
    h2 = soup.select_one("div.carsummary h2.h1")
    if h2:
        manufacturer_model = h2.get_text(strip=True)
    else:
        manufacturer_model = "Onbekend"

    # Check of er een editionSelect is
    select = soup.select_one("select#editionSelect option[selected]")
    if select:
        edition = select.get_text(strip=True)
    else:
        # Anders check h4 (zoals Kia ProCeed)
        h4 = soup.select_one("div.carsummary h4")
        edition = h4.get_text(strip=True) if h4 else ""

    # Bouwjaar proberen te pakken uit de omschrijving
    summary_text = soup.select_one("div.carsummary").get_text(" ", strip=True)
    year_match = re.search(r"(\d{4})", summary_text)
    year = year_match.group(1) if year_match else ""

    result = f"{manufacturer_model} {edition}".strip()
    if year:
        result += f" ({year})"
    return result

def parse_car_specs(soup):
    specs = {}
    pk = None
    nm = None

    value_divs = soup.select('div.col-6.col-sm-7.value')
    for div in value_divs:
        text = div.get_text(strip=True)
        if not pk:
            pk_match = re.search(r"(\d{2,3})\s?PK", text)
            if pk_match:
                pk = pk_match.group(1)
        if not nm:
            nm_match = re.search(r"(\d{2,4})\s?Nm", text)
            if nm_match:
                nm = nm_match.group(1)

    if pk:
        specs["Vermogen"] = f"{pk}PK"
        if nm:
            specs["Vermogen"] += f" / {nm}Nm"

    # Overige specs
    specs_div = soup.select_one('div.mt-3.mb-3')
    if specs_div:
        text = specs_div.get_text(" ", strip=True)
        # Topsnelheid
        topspeed_match = re.search(r"[Tt]opsnelheid.*?(\d{2,3})\s?km", text)
        if not topspeed_match:
            topspeed_match = re.search(r"bereikt.*topsnelheid.*?(\d{2,3})\s?km", text)
        if topspeed_match:
            specs["Topsnelheid"] = f"{topspeed_match.group(1)} km/u"
        # 0-100 km/u
        sprint_match = re.search(r"de 100 km/u.*?in ([\d,\.]+) seconden", text)
        if sprint_match:
            specs["0-100 km/u"] = f"{sprint_match.group(1)} sec"
        # Motorinhoud
        engine_match = re.search(r"cilinderinhoud\s(?:van\s)?(\d{3,4})\s?cc", text, re.IGNORECASE)
        if engine_match:
            specs["Motorinhoud"] = f"{engine_match.group(1)} cc"
        # Brandstof
        fuel_match = re.search(r"(diesel|benzine|elektrisch|hybride)", text, re.IGNORECASE)
        if fuel_match:
            specs["Brandstof"] = fuel_match.group(1).capitalize()
    return specs

def classify(owners):
    classification = "Prive auto"
    confidence = 85
    reasons = []
    if owners:
        raw_texts = [o["raw"].lower() for o in owners]
        if any("fleetowner" in t for t in raw_texts):
            classification = "Hoogstwaarschijnlijk undercover"
            confidence = 95
            reasons.append("Eigenaarstype expliciet aangegeven als Fleetowner")
        elif any(k in t for t in raw_texts for k in POLICE_KEYWORDS):
            classification = "Hoogstwaarschijnlijk undercover"
            confidence = 90
            reasons.append("Keyword politie/undercover gevonden")
    else:
        reasons.append("Geen eigenarenhistorie gevonden (gratis Finnik gebruikt)")
    return {
        "classification": classification,
        "confidence": confidence,
        "reasons": reasons,
        "score": 10 if "undercover" in classification.lower() else 2
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/check", methods=["GET"])
def check():
    kenteken = request.args.get("kenteken")
    if not kenteken:
        return jsonify({"error":"kenteken required"}), 400
    try:
        html = fetch_finnik_html(kenteken)
    except Exception as e:
        return jsonify({"error":"Failed to fetch Finnik", "detail": str(e)}), 500

    soup = BeautifulSoup(html, "html.parser")
    owners = parse_owners(soup)
    result = classify(owners)
    vehicle_type = parse_car_summary(soup)
    specs = parse_car_specs(soup)

    payload = {
        "kenteken": kenteken,
        "vehicle_type": vehicle_type,
        "specs": specs,
        "owners_raw": owners,
        "analysis": result
    }
    return jsonify(payload), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
