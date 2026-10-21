import os
import re
import secrets
import sqlite3
from functools import wraps
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE = os.environ.get("FAREWISE_DATABASE_PATH") or os.path.join(
    "/tmp" if os.environ.get("VERCEL") == "1" else BASE_DIR,
    "farewise.db",
)
SECRET_KEY = os.environ.get("FAREWISE_SECRET_KEY") or (
    None if os.environ.get("VERCEL") == "1" else "dev-only-change-this-key"
)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("VERCEL") == "1",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 12,
)

try:
    from psycopg import IntegrityError as PsycopgIntegrityError
    from psycopg.rows import dict_row
except ImportError:
    PsycopgIntegrityError = sqlite3.IntegrityError
    dict_row = None


class DatabaseConnection:
    def __init__(self, connection, postgres=False):
        self.connection = connection
        self.postgres = postgres

    def execute(self, statement, parameters=()):
        if self.postgres:
            cursor = self.connection.cursor()
            cursor.execute(statement.replace("?", "%s"), parameters)
            return cursor
        return self.connection.execute(statement, parameters)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def connect_database():
    if DATABASE_URL:
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError(
                "Install the psycopg dependency to use DATABASE_URL."
            ) from error
        connection = psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
            sslmode="require",
        )
        return DatabaseConnection(connection, postgres=True)

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return DatabaseConnection(connection)

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

# Amadeus searches airport pairs; only cities with a known airport code are supported.
AIRPORT_CODES = {
    "Abuja": "ABV",
    "Lagos": "LOS",
    "Kano": "KAN",
    "Ibadan": "IBA",
    "Port Harcourt": "PHC",
    "Yola": "YOL",
    "Uyo": "QUO",
    "Bauchi": "BCU",
    "Maiduguri": "MIU",
    "Calabar": "CBQ",
    "Asaba": "ABB",
    "Benin City": "BNI",
    "Enugu": "ENU",
    "Gombe": "GMO",
    "Owerri": "QOW",
    "Kaduna": "KAD",
    "Ilorin": "ILR",
    "Minna": "MXJ",
    "Akure": "AKR",
    "Jos": "JOS",
    "Sokoto": "SKO",
}

def get_db():
    if "db" not in g:
        g.db = connect_database()
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = connect_database()
    if db.postgres:
        db.execute("""
            CREATE TABLE IF NOT EXISTS farewise_users (
                id BIGSERIAL PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'subscriber'
                    CHECK (role IN ('subscriber', 'admin')),
                subscription_status TEXT NOT NULL DEFAULT 'free'
                    CHECK (subscription_status IN ('free', 'active', 'suspended')),
                subscription_plan TEXT NOT NULL DEFAULT 'free'
                    CHECK (subscription_plan IN ('free', 'monthly', 'yearly')),
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id BIGSERIAL PRIMARY KEY,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                distance_km DOUBLE PRECISION,
                created_at TEXT NOT NULL,
                user_id BIGINT REFERENCES farewise_users(id) ON DELETE SET NULL,
                guest_id TEXT
            )
        """)
        db.execute("""
            ALTER TABLE searches
            ADD COLUMN IF NOT EXISTS user_id BIGINT
            REFERENCES farewise_users(id) ON DELETE SET NULL
        """)
        db.execute("""
            ALTER TABLE searches
            ADD COLUMN IF NOT EXISTS guest_id TEXT
        """)
        db.execute(
            "CREATE INDEX IF NOT EXISTS searches_user_history "
            "ON searches (user_id, id DESC)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS searches_guest_history "
            "ON searches (guest_id, id DESC)"
        )
    else:
        db.execute("""
            CREATE TABLE IF NOT EXISTS farewise_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'subscriber'
                    CHECK (role IN ('subscriber', 'admin')),
                subscription_status TEXT NOT NULL DEFAULT 'free'
                    CHECK (subscription_status IN ('free', 'active', 'suspended')),
                subscription_plan TEXT NOT NULL DEFAULT 'free'
                    CHECK (subscription_plan IN ('free', 'monthly', 'yearly')),
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                distance_km REAL,
                created_at TEXT NOT NULL,
                user_id INTEGER REFERENCES farewise_users(id) ON DELETE SET NULL,
                guest_id TEXT
            )
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(searches)")}
        if "user_id" not in columns:
            db.execute(
                "ALTER TABLE searches ADD COLUMN user_id INTEGER "
                "REFERENCES farewise_users(id) ON DELETE SET NULL"
            )
        if "guest_id" not in columns:
            db.execute("ALTER TABLE searches ADD COLUMN guest_id TEXT")
        db.execute(
            "CREATE INDEX IF NOT EXISTS searches_user_history "
            "ON searches (user_id, id DESC)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS searches_guest_history "
            "ON searches (guest_id, id DESC)"
        )
    db.commit()
    db.close()


def auth_setup_ready():
    if os.environ.get("VERCEL") == "1":
        return bool(DATABASE_URL and app.config["SECRET_KEY"])
    return True


def csrf_token():
    if not app.config["SECRET_KEY"]:
        return ""
    token = session.get("_csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def valid_csrf():
    token = request.form.get("csrf_token", "")
    return bool(token and secrets.compare_digest(token, session.get("_csrf_token", "")))


def current_user():
    if "current_user" not in g:
        user_id = session.get("user_id")
        g.current_user = (
            get_db().execute(
                "SELECT id, email, role, subscription_status, subscription_plan "
                "FROM farewise_users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if user_id
            else None
        )
    return g.current_user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user()["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def auth_unavailable_response():
    return (
        "Account features are not configured. Set DATABASE_URL and "
        "FAREWISE_SECRET_KEY in the deployment environment.",
        503,
    )


@app.context_processor
def inject_account_context():
    return {
        "current_user": current_user(),
        "csrf_token": csrf_token,
        "auth_enabled": auth_setup_ready(),
    }

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

def get_live_flight_offers(origin, destination, departure_date, adults):
    """Fetch current one-way offers; return an explicit message when unavailable."""
    origin_code = AIRPORT_CODES.get(LOCATIONS[origin]["city"])
    destination_code = AIRPORT_CODES.get(LOCATIONS[destination]["city"])
    if not origin_code or not destination_code:
        return None, "Live flight prices are not available for one or both selected cities."
    if origin_code == destination_code:
        return None, "These locations use the same airport, so there is no flight route to price."

    client_id = os.environ.get("AMADEUS_CLIENT_ID")
    client_secret = os.environ.get("AMADEUS_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None, (
            "Live flight prices are not connected yet. Add Amadeus API credentials "
            "to the deployment environment to enable them."
        )

    base_url = os.environ.get(
        "AMADEUS_API_URL", "https://api.amadeus.com"
    ).rstrip("/")
    try:
        token_response = requests.post(
            f"{base_url}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]

        offer_response = requests.get(
            f"{base_url}/v2/shopping/flight-offers",
            params={
                "originLocationCode": origin_code,
                "destinationLocationCode": destination_code,
                "departureDate": departure_date,
                "adults": adults,
                "currencyCode": "NGN",
                "max": 5,
            },
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=12,
        )
        offer_response.raise_for_status()
        payload = offer_response.json()
        raw_offers = payload.get("data")
        if not isinstance(raw_offers, list):
            raise ValueError("Amadeus response did not contain an offers list.")

        offers = []
        for offer in raw_offers:
            price = offer.get("price", {})
            try:
                total = Decimal(price["total"])
            except (KeyError, InvalidOperation, TypeError):
                continue
            if not total.is_finite() or total <= 0:
                continue

            itineraries = offer.get("itineraries", [])
            segments = itineraries[0].get("segments", []) if itineraries else []
            duration = itineraries[0].get("duration", "") if itineraries else ""
            duration_match = re.fullmatch(
                r"PT(?:(\d+)H)?(?:(\d+)M)?", duration
            )
            duration_minutes = (
                int(duration_match.group(1) or 0) * 60
                + int(duration_match.group(2) or 0)
                if duration_match
                else None
            )
            offers.append({
                "total": total,
                "currency": price.get("currency", "NGN"),
                "airlines": ", ".join(offer.get("validatingAirlineCodes", [])),
                "stops": max(0, len(segments) - 1),
                "duration_minutes": duration_minutes,
            })

        offers.sort(key=lambda item: item["total"])
        return offers, None
    except (
        requests.RequestException,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
    ) as error:
        app.logger.warning("Live Amadeus flight search failed: %s", error)
        return None, "We couldn't retrieve live flight prices right now. Please try again."

@app.route("/register", methods=["GET", "POST"])
def register():
    if not auth_setup_ready():
        return auth_unavailable_response()
    if request.method == "POST":
        if not valid_csrf():
            abort(400, description="Your form expired. Please try again.")

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
            flash("Enter a valid email address.", "error")
        elif len(password) < 10 or len(password) > 256:
            flash("Use a password between 10 and 256 characters.", "error")
        else:
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO farewise_users "
                    "(email, password_hash, created_at) VALUES (?, ?, ?)",
                    (
                        email,
                        generate_password_hash(password, method="scrypt"),
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                db.commit()
            except (sqlite3.IntegrityError, PsycopgIntegrityError):
                get_db().rollback()
                flash("An account with that email already exists. Please log in.", "error")
            else:
                flash("Your free subscriber account is ready. You can now log in.", "success")
                return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if not auth_setup_ready():
        return auth_unavailable_response()
    if request.method == "POST":
        if not valid_csrf():
            abort(400, description="Your form expired. Please try again.")

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT id, email, password_hash, subscription_status "
            "FROM farewise_users WHERE email = ?",
            (email,),
        ).fetchone()
        if (
            user is None
            or len(password) > 256
            or not check_password_hash(user["password_hash"], password)
        ):
            flash("Email or password is incorrect.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            if user["subscription_status"] == "suspended":
                flash("Your account is suspended. Contact support for help.", "error")
            return redirect(url_for("index"))

    return render_template("login.html")


@app.post("/logout")
@login_required
def logout():
    if not valid_csrf():
        abort(400, description="Your form expired. Please try again.")
    session.clear()
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    user = current_user()
    return render_template("account.html", user=user)


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin_dashboard():
    if not auth_setup_ready():
        return auth_unavailable_response()
    db = get_db()
    if request.method == "POST":
        if not valid_csrf():
            abort(400, description="Your form expired. Please try again.")

        try:
            subscriber_id = int(request.form.get("subscriber_id", ""))
        except ValueError:
            abort(400, description="Invalid subscriber.")

        status = request.form.get("subscription_status", "")
        plan = request.form.get("subscription_plan", "")
        if status not in {"free", "active", "suspended"} or plan not in {
            "free", "monthly", "yearly"
        }:
            abort(400, description="Invalid subscription change.")

        update = db.execute(
            "UPDATE farewise_users SET subscription_status = ?, subscription_plan = ? "
            "WHERE id = ? AND role = 'subscriber'",
            (status, plan, subscriber_id),
        )
        if update.rowcount != 1:
            db.rollback()
            abort(404, description="Subscriber not found.")
        db.commit()
        flash("Subscriber access updated.", "success")
        return redirect(url_for("admin_dashboard"))

    subscribers = db.execute(
        "SELECT id, email, subscription_status, subscription_plan, created_at "
        "FROM farewise_users WHERE role = 'subscriber' ORDER BY created_at DESC"
    ).fetchall()
    return render_template("admin.html", subscribers=subscribers)


@app.route("/", methods=["GET", "POST"])
def index():
    results = None
    error = None
    origin = request.form.get("origin", "abuja_city_gate")
    destination = request.form.get("destination", "abuja_area1")
    departure_date = request.form.get(
        "departure_date", (date.today() + timedelta(days=1)).isoformat()
    )
    adults = request.form.get("adults", "1")
    user = current_user()

    if request.method == "POST":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", departure_date):
            parsed_departure_date = None
        else:
            try:
                parsed_departure_date = date.fromisoformat(departure_date)
            except ValueError:
                parsed_departure_date = None

        if user and user["subscription_status"] == "suspended":
            error = "Your account is suspended. Contact support for help."
        elif origin not in LOCATIONS or destination not in LOCATIONS:
            error = "Please choose a valid starting point and destination."
        elif origin == destination:
            error = "Choose two different locations to compare a journey."
        elif parsed_departure_date is None or parsed_departure_date < date.today():
            error = "Choose today or a future departure date."
        elif adults not in {str(count) for count in range(1, 10)}:
            error = "Choose between 1 and 9 adult passengers."
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
            flight_offers, flight_error = get_live_flight_offers(
                origin, destination, departure_date, int(adults)
            )
            results = {
                "origin": LOCATIONS[origin],
                "destination": LOCATIONS[destination],
                "distance_km": round(distance_km, 1),
                "flight_offers": flight_offers,
                "flight_error": flight_error,
                "flight_checked_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M UTC"
                ),
                "departure_date": departure_date,
                "adults": int(adults),
                "drive_minutes": round(drive_minutes),
                "source": source,
                "alternatives": alternatives,
                "options": options,
                "cheapest": cheapest["name"],
                "fastest": fastest["name"],
            }
            guest_id = None
            if not user:
                guest_id = session.get("guest_id")
                if not guest_id:
                    guest_id = secrets.token_urlsafe(32)
                    session["guest_id"] = guest_id
            created_at = datetime.now().isoformat(timespec="seconds")
            db = get_db()
            db.execute(
                "INSERT INTO searches "
                "(origin, destination, distance_km, created_at, user_id, guest_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    LOCATIONS[origin]["label"],
                    LOCATIONS[destination]["label"],
                    round(distance_km, 1),
                    created_at,
                    user["id"] if user else None,
                    guest_id,
                ),
            )
            db.commit()

    history = []
    if user:
        history = get_db().execute(
            "SELECT origin, destination, distance_km, created_at FROM searches "
            "WHERE user_id = ? ORDER BY id DESC",
            (user["id"],),
        ).fetchall()
    else:
        guest_id = session.get("guest_id")
        legacy_history = session.pop("recent_searches", [])
        db = get_db()
        if not guest_id:
            guest_id = secrets.token_urlsafe(32)
            session["guest_id"] = guest_id
        for item in reversed(legacy_history):
            db.execute(
                "INSERT INTO searches "
                "(origin, destination, distance_km, created_at, guest_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    item["origin"],
                    item["destination"],
                    item["distance_km"],
                    item["created_at"],
                    guest_id,
                ),
            )
        if legacy_history:
            db.commit()
        history = db.execute(
            "SELECT origin, destination, distance_km, created_at FROM searches "
            "WHERE guest_id = ? ORDER BY id DESC",
            (guest_id,),
        ).fetchall()

    location_keys = {
        place["label"]: key for key, place in LOCATIONS.items()
    }
    history = [
        {
            **dict(item),
            "origin_key": location_keys.get(item["origin"]),
            "destination_key": location_keys.get(item["destination"]),
        }
        for item in history
    ]

    return render_template(
        "index.html",
        locations=LOCATIONS,
        results=results,
        error=error,
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        adults=adults,
        today=date.today().isoformat(),
        replay_date=(date.today() + timedelta(days=1)).isoformat(),
        history=history
    )

@app.route("/health")
def health():
    return {"status": "ok", "app": "FareWise"}

@app.route("/manifest.webmanifest")
def web_manifest():
    return send_from_directory(
        os.path.join(BASE_DIR, "static"),
        "manifest.webmanifest",
        mimetype="application/manifest+json",
    )

@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(
        os.path.join(BASE_DIR, "static"),
        "service-worker.js",
    )
    response.headers["Service-Worker-Allowed"] = "/"
    return response

@app.route("/app.js")
def app_script():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "app.js")

@app.route("/offline.html")
def offline_page():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "offline.html")

@app.route("/icons/<path:filename>")
def app_icon(filename):
    return send_from_directory(os.path.join(BASE_DIR, "static", "icons"), filename)

init_db()

if __name__ == "__main__":
    app.run(debug=True)
