# Profile Job Portal MVP

Small Flask app for searching jobs that fit a saved profile.

Current MVP features:

- Search against profile keywords such as `splunk`, `observability`, `pmo`, `systems analyst`, `servicenow`
- Filter to jobs posted in the last `5` or `30` days
- Filter by `Canada`, `USA`, `remote`, `hybrid`, `in person`, and job track
- Rank jobs by profile fit instead of only by date
- Seed data from the jobs already curated in this workspace

## Run locally

```powershell
cd C:\Users\jshil\Downloads\kubernetes\job-portal
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Where to tune the matching

- Default profile keywords: [app.py](C:/Users/jshil/Downloads/kubernetes/job-portal/app.py)
- Ranking logic: [app.py](C:/Users/jshil/Downloads/kubernetes/job-portal/app.py)
- Seed jobs: [jobs.json](C:/Users/jshil/Downloads/kubernetes/job-portal/data/jobs.json)

## Practical next step

To turn this into a real portal with live jobs, add one or more source adapters that pull from allowed APIs or imported CSV/XLSX exports, then normalize results into the `jobs.json` shape before scoring.
