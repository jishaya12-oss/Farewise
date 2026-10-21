# FareWise — Fare and Route Comparator

A beginner-friendly Flask prototype for comparing estimated transport fares and journey times across selected Nigerian city landmarks.

## Features
- Responsive layout for desktop and mobile browsers
- Starting point and destination selection
- Road distance and driving-duration lookup through OSRM when available
- Estimated bus/shared-minibus, shared-taxi, and private-taxi fares
- Cheapest and fastest labels
- SQLite recent-search history
- OpenStreetMap directions link

## Requirements
- Python 3.10 or newer
- Internet connection for installation and optional OSRM route lookup

## Run on Linux
```bash
cd farewise_project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser.

If your terminal says `python3` is missing, install Python 3 using your Linux distribution's package manager.

## Important limitations
- Location list includes a representative city in all 36 states and the FCT, plus additional approximate demo landmarks in selected cities. These are not live GPS pickup points.
- Fare amounts are illustrative estimates generated from a simple rate formula. They are NOT current quotes from transport companies.
- OSRM may be unavailable, slow, or rate-limited. The app falls back to a rough distance estimate.
- OSRM road routing does not tell the app actual bus routes, public transport schedules, traffic in real time, or operator fares.
- The built-in Flask server is for local development only. Do not deploy it publicly with debug mode enabled.
- For production, replace demo fare rates with verified operator/user-reported data, add proper API usage controls, authentication/admin moderation as needed, tests, privacy notices, and a production WSGI server.

## Project files
- `app.py`: Flask routes, route lookup, fare estimates and SQLite history
- `templates/index.html`: page structure
- `static/style.css`: responsive styling
- `requirements.txt`: Python dependencies
