# FareWise — Fare and Route Comparator

A beginner-friendly Flask prototype for comparing estimated transport fares and journey times across selected Nigerian city landmarks.

## Features
- Responsive layout for desktop and mobile browsers
- Starting point and destination selection
- Road distance and driving-duration lookup through OSRM when available
- Estimated bus/shared-minibus, shared-taxi, and private-taxi fares
- Illustrative air-fare and journey-time estimates using straight-line distance
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

## Deploy on Vercel
- The Git repository root contains a Vercel entrypoint (`app.py`) and `requirements.txt` that load the Flask app from `farewise_project/`. Leave Vercel's **Root Directory** set to the repository root.
- Vercel serves the stylesheet from `public/static/style.css`; the original `farewise_project/static/style.css` remains in place for local Flask development.
- No separate start command is needed.
- Commit and push these deployment files to the Git branch connected to Vercel, then redeploy. Vercel cannot deploy uncommitted files from your computer.
- Vercel's function filesystem is not persistent. This app uses `/tmp/farewise.db` there so it can start, but recent-search history may disappear between function instances or deployments. Use a hosted database for persistent history.
- To override the database location, set `FAREWISE_DATABASE_PATH` to a writable path.

## Install FareWise on a phone
- Deploy the app over HTTPS, then open its URL on your phone.
- On Android, tap **Install app** if offered, or choose **Install app** / **Add to Home screen** from the browser menu.
- On iPhone, open the URL in Safari, tap **Share**, then choose **Add to Home Screen**.
- If installation is unavailable, confirm `/manifest.webmanifest`, `/service-worker.js`, `/static/icons/icon-192.png`, and `/static/icons/icon-512.png` all load without a 404 on the deployed site.
- FareWise is an installable web app, not a Play Store or Apple App Store package. Its page shell and stylesheet can load offline after a successful online visit; fare searches still need the server.

## Important limitations
- Location list includes a representative city in all 36 states and the FCT, plus additional approximate demo landmarks in selected cities. These are not live GPS pickup points.
- Fare amounts are illustrative estimates generated from a simple rate formula. They are NOT current quotes from transport companies.
- Air estimates are especially approximate: they use landmark-to-landmark straight-line distance and do not verify airports, available routes, airline schedules, seats, or ticket prices.
- OSRM may be unavailable, slow, or rate-limited. The app falls back to a rough distance estimate.
- OSRM road routing does not tell the app actual bus routes, public transport schedules, traffic in real time, or operator fares.
- The built-in Flask server is for local development only. Do not deploy it publicly with debug mode enabled.
- For production, replace demo fare rates with verified operator/user-reported data, add proper API usage controls, authentication/admin moderation as needed, tests, privacy notices, and a production WSGI server.

## Project files
- `app.py`: Flask routes, route lookup, fare estimates and SQLite history
- `templates/index.html`: page structure
- `static/style.css`: responsive styling
- `requirements.txt`: Python dependencies
