import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, g, send_from_directory
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "public"))
DATABASE = os.environ.get("FAREWISE_DATABASE_PATH") or os.path.join(
    "/tmp" if os.environ.get("VERCEL") == "1" else BASE_DIR,
    "farewise.db",
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FAREWISE_SECRET_KEY", "dev-only-change-this-key")

# Demo locations. Coordinates are approximate city landmarks, not exact pickup points.
LOCATIONS = {
    "abuja_city_gate": {"label": "Abuja City Gate, Abuja", "city": "Abuja", "lat": 9.0579, "lon": 7.4951},
    "abuja_area1": {"label": "Area 1, Abuja", "city": "Abuja", "lat": 9.0369, "lon": 7.4860},
    "abuja_airport": {"label": "Nnamdi Azikiwe International Airport, Abuja", "city": "Abuja", "lat": 9.0068, "lon": 7.2631},
    "lagos_tbs": {"label": "Tafawa Balewa Square, Lagos", "city": "Lagos", "lat": 6.4500, "lon": 3.3830},
    "lagos_ikeja": {"label": "Ikeja Bus Stop, Lagos", "city": "Lagos", "lat": 6.6018, "lon": 3.3515},
    "lagos_lekki": {"label": "Lekki Phase 1, Lagos", "city": "Lagos", "lat": 6.4474, "lon": 3.4737},
    "kano_centre": {"label": "Kano City Centre, Kano", "city": "Kano", "lat": 12.0022, "lon": 8.5920},
    "kano_airport": {"label": "Mallam Aminu Kano International Airport, Kano", "city": "Kano", "lat": 12.0476, "lon": 8.5246},
    "ibadan_mokola": {"label": "Mokola, Ibadan", "city": "Ibadan", "lat": 7.4070, "lon": 3.9000},
    "ibadan_ui": {"label": "University of Ibadan, Ibadan", "city": "Ibadan", "lat": 7.4410, "lon": 3.9000},
    "ph_gra": {"label": "GRA, Port Harcourt", "city": "Port Harcourt", "lat": 4.8156, "lon": 7.0498},
    "ph_airport": {"label": "Port Harcourt International Airport", "city": "Port Harcourt", "lat": 5.0155, "lon": 6.9496},
    "umuahia_abia": {"label": "Umuahia, Abia", "city": "Umuahia", "lat": 5.5249, "lon": 7.4946},
    "yola_adamawa": {"label": "Yola, Adamawa", "city": "Yola", "lat": 9.2035, "lon": 12.4954},
    "uyo_akwa_ibom": {"label": "Uyo, Akwa Ibom", "city": "Uyo", "lat": 5.0377, "lon": 7.9128},
    "awka_anambra": {"label": "Awka, Anambra", "city": "Awka", "lat": 6.2104, "lon": 7.0723},
    "bauchi_bauchi": {"label": "Bauchi, Bauchi", "city": "Bauchi", "lat": 10.3103, "lon": 9.8439},
    "yenagoa_bayelsa": {"label": "Yenagoa, Bayelsa", "city": "Yenagoa", "lat": 4.9267, "lon": 6.2676},
    "makurdi_benue": {"label": "Makurdi, Benue", "city": "Makurdi", "lat": 7.7322, "lon": 8.5391},
    "maiduguri_borno": {"label": "Maiduguri, Borno", "city": "Maiduguri", "lat": 11.8333, "lon": 13.1500},
    "calabar_cross_river": {"label": "Calabar, Cross River", "city": "Calabar", "lat": 4.9757, "lon": 8.3417},
    "asaba_delta": {"label": "Asaba, Delta", "city": "Asaba", "lat": 6.1989, "lon": 6.7319},
    "abakaliki_ebonyi": {"label": "Abakaliki, Ebonyi", "city": "Abakaliki", "lat": 6.3249, "lon": 8.1137},
    "benin_city_edo": {"label": "Benin City, Edo", "city": "Benin City", "lat": 6.3350, "lon": 5.6037},
    "ado_ekiti": {"label": "Ado-Ekiti, Ekiti", "city": "Ado-Ekiti", "lat": 7.6233, "lon": 5.2209},
    "enugu_city": {"label": "Enugu, Enugu", "city": "Enugu", "lat": 6.4584, "lon": 7.5464},
    "gombe_city": {"label": "Gombe, Gombe", "city": "Gombe", "lat": 10.2897, "lon": 11.1673},
    "owerri_imo": {"label": "Owerri, Imo", "city": "Owerri", "lat": 5.4850, "lon": 7.0350},
    "dutse_jigawa": {"label": "Dutse, Jigawa", "city": "Dutse", "lat": 11.7594, "lon": 9.3380},
    "kaduna_city": {"label": "Kaduna, Kaduna", "city": "Kaduna", "lat": 10.5167, "lon": 7.4333},
    "katsina_city": {"label": "Katsina, Katsina", "city": "Katsina", "lat": 12.9908, "lon": 7.6018},
    "birnin_kebbi": {"label": "Birnin Kebbi, Kebbi", "city": "Birnin Kebbi", "lat": 12.4539, "lon": 4.1975},
    "lokoja_kogi": {"label": "Lokoja, Kogi", "city": "Lokoja", "lat": 7.8023, "lon": 6.7333},
    "ilorin_kwara": {"label": "Ilorin, Kwara", "city": "Ilorin", "lat": 8.4966, "lon": 4.5421},
    "lafia_nasarawa": {"label": "Lafia, Nasarawa", "city": "Lafia", "lat": 8.4939, "lon": 8.5153},
    "minna_niger": {"label": "Minna, Niger", "city": "Minna", "lat": 9.6139, "lon": 6.5569},
    "abeokuta_ogun": {"label": "Abeokuta, Ogun", "city": "Abeokuta", "lat": 7.1475, "lon": 3.3619},
    "akure_ondo": {"label": "Akure, Ondo", "city": "Akure", "lat": 7.2571, "lon": 5.2058},
    "osogbo_osun": {"label": "Osogbo, Osun", "city": "Osogbo", "lat": 7.7827, "lon": 4.5418},
    "jos_plateau": {"label": "Jos, Plateau", "city": "Jos", "lat": 9.8965, "lon": 8.8583},
    "sokoto_city": {"label": "Sokoto, Sokoto", "city": "Sokoto", "lat": 13.0059, "lon": 5.2476},
    "jalingo_taraba": {"label": "Jalingo, Taraba", "city": "Jalingo", "lat": 8.8937, "lon": 11.3596},
    "damaturu_yobe": {"label": "Damaturu, Yobe", "city": "Damaturu", "lat": 11.7469, "lon": 11.9608},
    "gusau_zamfara": {"label": "Gusau, Zamfara", "city": "Gusau", "lat": 12.1704, "lon": 6.6641},
}

# Estimated sample fare rates. Replace with verified local fares before public launch.
TRANSPORT = [
    {"name": "Bus / shared minibus", "rate": 120, "base": 100, "speed_kmh": 25, "icon": "🚌"},
    {"name": "Shared taxi", "rate": 220, "base": 250, "speed_kmh": 30, "icon": "🚕"},
    {"name": "Private taxi", "rate": 500, "base": 700, "speed_kmh": 35, "icon": "🚗"},
]

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            distance_km REAL,
            created_at TEXT NOT NULL
        )
    """)
    db.commit()
    db.close()

def get_road_route(origin, destination):
    """Try OSRM for road distance and driving duration; return None if unavailable."""
    a, b = LOCATIONS[origin], LOCATIONS[destination]
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{a['lon']},{a['lat']};{b['lon']},{b['lat']}"
    )
    try:
        response = requests.get(
            url,
            params={"overview": "false", "alternatives": "true", "steps": "false"},
            timeout=7,
            headers={"User-Agent": "FareWiseDemo/1.0"}
        )
        response.raise_for_status()
        payload = response.json()
        routes = payload.get("routes", [])
        if routes:
            # The first route is OSRM's recommended route. Alternatives may be available.
            route = routes[0]
            return {
                "distance_km": route["distance"] / 1000,
                "drive_minutes": route["duration"] / 60,
                "source": "OSRM road-route estimate",
                "alternatives": len(routes)
            }
    except (requests.RequestException, ValueError, KeyError, TypeError):
        pass
    return None

def estimate_straight_distance(origin, destination):
    # Haversine fallback, multiplied by 1.3 to approximate road distance.
    from math import radians, sin, cos, sqrt, atan2
    a, b = LOCATIONS[origin], LOCATIONS[destination]
    earth_km = 6371
    lat1, lat2 = radians(a["lat"]), radians(b["lat"])
    dlat = lat2 - lat1
    dlon = radians(b["lon"] - a["lon"])
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * earth_km * atan2(sqrt(h), sqrt(1 - h)) * 1.3

@app.route("/", methods=["GET", "POST"])
def index():
    results = None
    error = None
    origin = request.form.get("origin", "abuja_city_gate")
    destination = request.form.get("destination", "abuja_area1")

    if request.method == "POST":
        if origin not in LOCATIONS or destination not in LOCATIONS:
            error = "Please choose a valid starting point and destination."
        elif origin == destination:
            error = "Choose two different locations to compare a journey."
        else:
            road = get_road_route(origin, destination)
            if road:
                distance_km = road["distance_km"]
                drive_minutes = road["drive_minutes"]
                source = road["source"]
                alternatives = road["alternatives"]
            else:
                distance_km = estimate_straight_distance(origin, destination)
                drive_minutes = (distance_km / 30) * 60
                source = "Approximate fallback (road-routing service unavailable)"
                alternatives = 0

            options = []
            for mode in TRANSPORT:
                # Simple demo fare model, not a real quote from a transport operator.
                fare = round(mode["base"] + distance_km * mode["rate"], -1)
                minutes = max(5, round((distance_km / mode["speed_kmh"]) * 60 + 8))
                options.append({
                    "name": mode["name"],
                    "icon": mode["icon"],
                    "fare": int(fare),
                    "minutes": minutes,
                })

            cheapest = min(options, key=lambda item: item["fare"])
            fastest = min(options, key=lambda item: item["minutes"])
            results = {
                "origin": LOCATIONS[origin],
                "destination": LOCATIONS[destination],
                "distance_km": round(distance_km, 1),
                "drive_minutes": round(drive_minutes),
                "source": source,
                "alternatives": alternatives,
                "options": options,
                "cheapest": cheapest["name"],
                "fastest": fastest["name"],
            }
            db = get_db()
            db.execute(
                "INSERT INTO searches (origin, destination, distance_km, created_at) VALUES (?, ?, ?, ?)",
                (LOCATIONS[origin]["label"], LOCATIONS[destination]["label"],
                 round(distance_km, 1), datetime.now().isoformat(timespec="seconds"))
            )
            db.commit()

    history = get_db().execute(
        "SELECT origin, destination, distance_km, created_at FROM searches ORDER BY id DESC LIMIT 5"
    ).fetchall()

    return render_template(
        "index.html",
        locations=LOCATIONS,
        results=results,
        error=error,
        origin=origin,
        destination=destination,
        history=history
    )

@app.route("/health")
def health():
    return {"status": "ok", "app": "FareWise"}

@app.route("/manifest.webmanifest")
def web_manifest():
    return send_from_directory(
        PUBLIC_DIR,
        "manifest.webmanifest",
        mimetype="application/manifest+json",
    )

@app.route("/service-worker.js")
def service_worker():
    return send_from_directory(PUBLIC_DIR, "service-worker.js")

@app.route("/app.js")
def app_script():
    return send_from_directory(PUBLIC_DIR, "app.js")

@app.route("/icons/<path:filename>")
def app_icon(filename):
    return send_from_directory(os.path.join(PUBLIC_DIR, "icons"), filename)

init_db()

if __name__ == "__main__":
    app.run(debug=True)
