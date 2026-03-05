# YMCA Connect (Python)

This project helps with class booking workflows for:
- `Location`: Seton, Calgary
- `Class`: Zumba
- `Time`: Thursday, 6:00 PM to 7:00 PM
- `Default person`: Shilpi Jain (editable)

## Where API helps
- Pull live class schedules instead of manually checking site pages.
- Filter directly for Calgary/Seton + Friday evening window.
- Book in one click for the selected person.
- Reuse same flow for multiple people by changing the participant name.

## Run locally
```powershell
cd "C:\Users\jshil\Downloads\kubernetes\ymca connect"
python -m pip install -r requirements.txt
python app.py
```

Open: `http://127.0.0.1:5050`

## Real YMCA API setup
1. Copy `.env.example` to `.env`.
2. Set:
   - `YMCA_API_BASE_URL`
   - `YMCA_API_TOKEN`
3. Restart app.

If API env vars are missing, the app runs in mock mode with demo classes.

## Notes
- The real endpoint paths (`/classes`, `/bookings`) may differ by provider.
- Update request payloads in `app.py` once you have YMCA API docs.

## Real portal automation test (UI)
Use this when a class spot is currently open and you want to test end-to-end automation.

1. Install dependencies and browser:
```powershell
cd "C:\Users\jshil\Downloads\kubernetes\ymca connect"
python -m pip install -r requirements.txt
python -m playwright install chromium
```

2. Copy `.env.example` to `.env` and set:
- `YMCA_USERNAME`
- `YMCA_PASSWORD`
- `YMCA_DRY_RUN=1` (safe test mode)

3. Run:
```powershell
python book_once.py
```

The script opens the site, searches for your target class, and stops before final confirmation in dry-run mode.
