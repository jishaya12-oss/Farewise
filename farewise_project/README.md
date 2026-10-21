# FareWise — Fare and Route Comparator

A beginner-friendly Flask prototype for comparing estimated transport fares and journey times across selected Nigerian city landmarks.

## Features
- Responsive layout for desktop and mobile browsers
- Starting point and destination selection
- Road distance and driving-duration lookup through OSRM when available
- Estimated bus/shared-minibus, shared-taxi, and private-taxi fares (not live operator quotes)
- Live one-way airline offers through Amadeus when production API credentials are configured
- Flight searches by departure date and adult passenger count
- Cheapest and fastest labels
- SQLite recent-search history
- Subscriber registration, login, and account pages
- Admin dashboard for manually managing subscriber access
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
- Subscriber accounts on Vercel require a persistent Supabase PostgreSQL database; configure `DATABASE_URL` as a Vercel environment variable using your Supabase PostgreSQL connection string.
- Set `FAREWISE_SECRET_KEY` in Vercel to a strong random secret (for example, generate one with `openssl rand -hex 32`). Do not commit either secret.
- Live flight fares require Amadeus production API credentials. Add `AMADEUS_CLIENT_ID` and `AMADEUS_CLIENT_SECRET` as Vercel environment variables; never put these secrets in source code or send them in chat. The default API endpoint is `https://api.amadeus.com`. `AMADEUS_API_URL=https://test.api.amadeus.com` is for sandbox testing only and does not provide live prices.
- Create an Amadeus for Developers account and request production access at [developers.amadeus.com](https://developers.amadeus.com/). Until production credentials are configured, FareWise shows a clear message instead of inventing a flight fare.
- Vercel's function filesystem is temporary. Without `DATABASE_URL`, account registration and login return a setup error rather than saving accounts to an unreliable temporary database.
- To override the database location, set `FAREWISE_DATABASE_PATH` to a writable path.

## Subscriber login and administration
- Subscribers can create a free account at `/register`, then sign in at `/login`. Passwords are stored as scrypt hashes.
- The first administrator must first register an account. After the app has created the `farewise_users` table in Supabase, run this in the Supabase SQL Editor, replacing the email:

```sql
UPDATE public.farewise_users
SET role = 'admin'
WHERE email = lower('admin@example.com');
```

- Admins can view subscribers and manually change their access and plan. Free registration is enabled. Paystack checkout is not active and no one is charged; set plan prices and configure/test Paystack before enabling payments.
- Recent searches are tied to the signed-in subscriber so users do not see one another's history.

## Install FareWise on a phone
- Deploy the app over HTTPS, then open its URL on your phone.
- On Android, tap **Install app** if offered, or choose **Install app** / **Add to Home screen** from the browser menu.
- On iPhone, open the URL in Safari, tap **Share**, then choose **Add to Home Screen**.
- If installation is unavailable, confirm `/manifest.webmanifest`, `/service-worker.js`, `/static/icons/icon-192.png`, and `/static/icons/icon-512.png` all load without a 404 on the deployed site.
- FareWise is an installable web app, not a Play Store or Apple App Store package. Its page shell and stylesheet can load offline after a successful online visit; fare searches still need the server.

## Important limitations
- Location list includes a representative city in all 36 states and the FCT, plus additional approximate demo landmarks in selected cities. These are not live GPS pickup points.
- Road fare amounts are illustrative estimates generated from a simple rate formula. They are NOT current quotes from bus, taxi, or transport operators; they must not be presented as current prices.
- Live flight results require production Amadeus credentials, a supported airport pair, and provider availability for the selected date. Results are one-way offers for the requested adult count, can change before purchase, and are not a completed booking.
- The app does not yet have a live bus/operator fare provider. Add a provider integration or maintain verified route fares before claiming road fares are current.
- Subscriber accounts do not yet have email verification, password recovery, or login rate limiting. Add these before treating the service as a production account system.
- OSRM may be unavailable, slow, or rate-limited. The app falls back to a rough distance estimate.
- OSRM road routing does not tell the app actual bus routes, public transport schedules, traffic in real time, or operator fares.
- The built-in Flask server is for local development only. Do not deploy it publicly with debug mode enabled.
- For production, replace demo fare rates with verified operator/user-reported data, add proper API usage controls, authentication/admin moderation as needed, tests, privacy notices, and a production WSGI server.

## Project files
- `app.py`: Flask routes, road-fare estimates, Amadeus flight search and search history
- `templates/index.html`: page structure
- `static/style.css`: responsive styling
- `requirements.txt`: Python dependencies
