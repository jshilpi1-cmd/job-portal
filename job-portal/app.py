from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import io
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, Response, render_template, request
from docx import Document
from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "jobs.json"
SYNC_STATE_FILE = BASE_DIR / "data" / "sync_state.json"
ENBRIDGE_CAREERS_URL = "https://careers.enbridge.com/careers"
ENBRIDGE_WORKDAY_API = "https://enbridge.wd3.myworkdayjobs.com/wday/cxs/enbridge/enbridge_careers/jobs"
ENBRIDGE_WORKDAY_BASE = "https://enbridge.wd3.myworkdayjobs.com/enbridge_careers"
ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
REMOTEOK_API = "https://remoteok.com/api"
SYNC_TARGET_HOUR_MT = 11
DEFAULT_PROFILE = (
    "splunk, observability, site reliability, sre, monitoring, pmo, program management, "
    "business analysis, systems analyst, servicenow, cybersecurity, incident response, "
    "pagerduty, python, terraform, aws, azure, itsi, siem, dashboards, root cause analysis"
)
DEFAULT_NAME = "Shilpi Jain"
DEFAULT_CONTACT = "Calgary, AB, Canada | +1 403 629 7327 | j.shilpi1@gmail.com"
COMPANY_ALIASES = {
    "atb financial": "atb",
    "atb": "atb",
    "suncor energy": "suncor",
    "suncor": "suncor",
    "enbridge inc": "enbridge",
    "enbridge": "enbridge",
    "deloitte canada": "deloitte",
    "deloitte": "deloitte",
    "infosys limited": "infosys",
    "infosys": "infosys",
    "accenture ltd": "accenture",
    "accenture": "accenture",
}
DESIRED_ROLE_KEYWORDS = {
    "AI Engineer": "ai engineer, llm, model deployment, prompt engineering, python, mlops, vector database, rag, evaluation metrics",
    "SRE": "site reliability, sre, production monitoring, incident response, reliability engineering, observability",
    "Observability Engineer": "observability, telemetry, monitoring, alerting, splunk, dashboards, tracing",
    "Senior Analyst": "senior analyst, business analysis, stakeholder management, governance, reporting",
    "Application Analyst": "application analyst, application support, systems analysis, incident management, process improvement",
    "Business Analyst": "business analysis, requirements, process mapping, uat, stakeholder communication",
    "PMO Analyst": "pmo, governance, portfolio reporting, project controls, roadmap, planning",
    "Cybersecurity Analyst": "cybersecurity, siem, iam, risk, controls, security operations",
}
KNOWN_PROFILE_PHRASES = [
    "splunk",
    "observability",
    "site reliability",
    "sre",
    "monitoring",
    "pmo",
    "program management",
    "project delivery",
    "business analysis",
    "business analyst",
    "systems analyst",
    "application support",
    "servicenow",
    "cybersecurity",
    "incident response",
    "pagerduty",
    "python",
    "terraform",
    "aws",
    "azure",
    "itsi",
    "siem",
    "dashboards",
    "root cause analysis",
    "data quality",
    "cmdb",
    "governance",
    "uat",
    "sql",
]
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "your",
    "into",
    "across",
    "across",
    "within",
    "including",
    "using",
    "used",
    "where",
    "while",
    "over",
    "into",
    "role",
    "roles",
    "team",
    "teams",
    "senior",
    "engineer",
    "analyst",
    "project",
    "program",
    "experience",
    "years",
    "year",
    "work",
    "worked",
    "support",
    "delivery",
}
EXPERIENCE_LIBRARY = [
    {
        "title": "Senior Analyst - PMO & PMIS Administration",
        "company": "City of Calgary, Calgary, AB",
        "dates": "Feb 2025 - Dec 2025",
        "bullets": [
            "Administered Microsoft Project Online (PMIS) with custom fields, workflows, templates, and governance controls to standardize project delivery data across teams.",
            "Led requirements gathering, UAT coordination, and production rollout for PMIS enhancements that improved usability, reporting quality, and stakeholder confidence.",
            "Created Power BI dashboards for intake status, delivery progress, and portfolio performance, improving executive visibility and decision support.",
            "Partnered with PMO and Finance to align project metrics with forecast and financial reporting needs, improving consistency between operational and budget data.",
            "Designed and implemented archival/retention standards to protect historical reporting integrity and improve platform performance.",
            "Trained project managers and business users on data standards, governance expectations, and reporting best practices.",
        ],
    },
    {
        "title": "Automation and Monitoring Engineer",
        "company": "Vancity Savings Credit Union, Vancouver, BC",
        "dates": "Sep 2023 - Mar 2024",
        "bullets": [
            "Deployed Splunk ITSI to improve service health visibility and anomaly detection across critical digital banking platforms.",
            "Built advanced SPL queries and standardized data models supporting high-priority initiatives such as Online Account Opening and Visa information services.",
            "Implemented identity governance controls and role mapping to improve access management and auditability within secured environments.",
            "Integrated Saviynt and Google Cloud telemetry into Splunk to strengthen centralized monitoring and investigation workflows.",
            "Optimized alert thresholds and PagerDuty routing to reduce noise and improve response quality for incidents.",
            "Supported cross-team delivery using Azure DevOps, coordinating timeline, scope, and stakeholder expectations.",
        ],
    },
    {
        "title": "Senior Enterprise Support Analyst",
        "company": "Shaw Communications, Calgary, AB",
        "dates": "Jul 2013 - Jul 2023",
        "bullets": [
            "Designed and operated enterprise monitoring solutions that reduced MTTR by 30% and improved proactive incident detection across operations and security teams.",
            "Planned and executed Splunk upgrades across 2,000+ hosts with zero downtime and controlled rollout practices.",
            "Standardized CMDB services and data relationships by aligning monitoring records with ServiceNow structures to improve impact analysis and automation.",
            "Engineered data ingestion and parsing pipelines using schema mapping and normalization practices for better data quality and reporting reliability.",
            "Developed predictive models for license consumption and onboarding strategy to improve capacity planning and cost control.",
            "Provided L3 escalation and root cause analysis, translating incident patterns into long-term reliability and process improvements.",
            "Delivered training and governance guidance to 100+ stakeholders on monitoring usage, data quality expectations, and operational best practices.",
        ],
    },
    {
        "title": "Assistant Manager (IT)",
        "company": "Andhra Bank, India",
        "dates": "Oct 2004 - Jan 2011",
        "bullets": [
            "Prepared business requirements and coordinated stakeholder approvals for system changes across banking platforms.",
            "Managed infrastructure integration, environment configuration, and disaster recovery activities in a compliance-sensitive domain.",
            "Supported AML-related monitoring and control processes, including exception review and operational risk follow-up.",
            "Led status and planning sessions with business and IT teams to ensure delivery transparency and issue resolution.",
        ],
    },
]


def resolve_sync_timezone() -> tuple[timezone | ZoneInfo, str]:
    # Prefer named Mountain Time zones with DST support.
    for key in ("America/Edmonton", "America/Denver", "Canada/Mountain", "MST7MDT"):
        try:
            return ZoneInfo(key), key
        except ZoneInfoNotFoundError:
            continue
    # Fallback for environments without tzdata.
    return timezone(timedelta(hours=-7), name="MT"), "MT (fixed UTC-07:00)"


SYNC_TIMEZONE, SYNC_TIMEZONE_NAME = resolve_sync_timezone()


@dataclass
class Job:
    id: str
    title: str
    company: str
    country: str
    location: str
    work_mode: str
    category: str
    posted_date: date
    source: str
    url: str
    summary: str
    tags: list[str]


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/", methods=["GET", "POST"])
    def index() -> str:
        jobs = load_jobs()
        source = request.form if request.method == "POST" else request.args
        action = source.get("action", "apply_filters")
        profile_text = source.get("profile", "").strip()
        skills_text = source.get("skills", "").strip()
        desired_role = source.get("desired_role", "Any")
        resume_titles_text = source.get("resume_titles", "").strip()
        search_text = source.get("q", "").strip()
        days = int(source.get("days", "5"))
        country = source.get("country", "all")
        company = source.get("company", "all")
        mode = source.get("mode", "all")
        category = source.get("category", "all")
        sort = source.get("sort", "best_fit")
        upload_note = ""
        tailored: dict[str, str] | None = None
        auto_sync_canada_if_due()
        jobs = load_jobs()

        if request.method == "POST" and source.get("use_resume_profile") == "1":
            resume_file = request.files.get("resume_file")
            if resume_file and resume_file.filename:
                resume_text = extract_resume_text(resume_file.filename, resume_file.read())
                if resume_text:
                    extracted_skills = extract_skills_from_resume_text(resume_text, jobs)
                    if extracted_skills:
                        skills_text = ", ".join(extracted_skills[:20])
                    profile_text = build_profile_from_resume_text(resume_text, jobs)
                    extracted_titles = extract_titles_from_resume_text(resume_text)
                    if extracted_titles:
                        resume_titles_text = ", ".join(extracted_titles[:10])
                    upload_note = f"Profile generated from {resume_file.filename}."
                else:
                    upload_note = "Could not read resume file. Using current profile keywords."

        effective_profile = build_effective_profile(profile_text, skills_text, desired_role)
        if not effective_profile:
            effective_profile = DEFAULT_PROFILE

        if request.method == "POST" and action == "tailor_job":
            selected_job = get_job_by_id(jobs, source.get("job_id", ""))
            if selected_job:
                tailored = build_tailored_package(selected_job, effective_profile)

        ranked_jobs = filter_and_rank_jobs(
            jobs=jobs,
            profile_text=effective_profile,
            search_text=search_text,
            days=days,
            country=country,
            company=company,
            mode=mode,
            category=category,
            sort=sort,
            resume_titles=normalize_terms(resume_titles_text),
        )
        company_options = build_company_options(jobs, country)

        return render_template(
            "index.html",
            jobs=ranked_jobs,
            company_options=company_options,
            filters={
                "profile": effective_profile,
                "skills": skills_text,
                "desired_role": desired_role,
                "resume_titles": resume_titles_text,
                "q": search_text,
                "days": days,
                "country": country,
                "company": company,
                "mode": mode,
                "category": category,
                "sort": sort,
            },
            stats=build_stats(ranked_jobs),
            today=date.today(),
            upload_note=upload_note,
            tailored=tailored,
        )

    @app.route("/download-cover-letter", methods=["POST"])
    def download_cover_letter() -> Response:
        text = request.form.get("cover_letter_text", "").strip()
        company = request.form.get("company", "company").strip() or "company"
        role = request.form.get("job_title", "role").strip() or "role"
        safe_company = slug(company)
        safe_role = slug(role)
        filename = f"cover_letter_{safe_company}_{safe_role}.txt"
        return Response(
            text + "\n",
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.route("/download-application-package", methods=["POST"])
    def download_application_package() -> Response:
        company = request.form.get("company", "company").strip() or "company"
        role = request.form.get("job_title", "role").strip() or "role"
        resume_text = request.form.get("resume_text", "").strip()
        cover_letter_text = request.form.get("cover_letter_text", "").strip()
        safe_company = slug(company)
        safe_role = slug(role)

        buf = io.BytesIO()
        import zipfile

        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"resume_{safe_company}_{safe_role}.txt", resume_text + "\n")
            zf.writestr(f"cover_letter_{safe_company}_{safe_role}.txt", cover_letter_text + "\n")
            zf.writestr(
                "README.txt",
                (
                    f"Tailored package for {role} at {company}\n"
                    "Files:\n"
                    "- resume_*.txt\n"
                    "- cover_letter_*.txt\n"
                ),
            )
        buf.seek(0)

        zip_name = f"application_package_{safe_company}_{safe_role}.zip"
        return Response(
            buf.getvalue(),
            mimetype="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
        )

    return app


def load_jobs() -> list[Job]:
    raw_jobs = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    jobs: list[Job] = []
    for item in raw_jobs:
        jobs.append(
            Job(
                id=item["id"],
                title=item["title"],
                company=item["company"],
                country=item["country"],
                location=item["location"],
                work_mode=item["work_mode"],
                category=item["category"],
                posted_date=datetime.strptime(item["posted_date"], "%Y-%m-%d").date(),
                source=item["source"],
                url=item["url"],
                summary=item["summary"],
                tags=item["tags"],
            )
        )
    return jobs


def save_jobs(jobs: list[Job]) -> None:
    payload = [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "country": j.country,
            "location": j.location,
            "work_mode": j.work_mode,
            "category": j.category,
            "posted_date": j.posted_date.isoformat(),
            "source": j.source,
            "url": j.url,
            "summary": j.summary,
            "tags": j.tags,
        }
        for j in jobs
    ]
    DATA_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def sync_enbridge_jobs() -> int:
    parsed = fetch_enbridge_jobs_live()
    if not parsed:
        return 0

    jobs = load_jobs()
    jobs = [j for j in jobs if not j.id.startswith("enbridge-live-")]

    for item in parsed:
        jobs.append(
            Job(
                id=item["id"],
                title=item["title"],
                company="Enbridge",
                country=item.get("country", "Canada"),
                location=item["location"],
                work_mode=item.get("work_mode", "Hybrid: Remote and Office"),
                category=item["category"],
                posted_date=item["posted_date"],
                source="Enbridge Careers (Live Sync)",
                url=item["url"],
                summary=item["summary"],
                tags=item["tags"],
            )
        )
    save_jobs(jobs)
    return len(parsed)


def auto_sync_canada_if_due() -> None:
    state = load_sync_state()
    now_mt = datetime.now(SYNC_TIMEZONE)
    today_key = now_mt.date().isoformat()

    # Run only after 11:00 AM MT.
    if now_mt.hour < SYNC_TARGET_HOUR_MT:
        return

    # Run only once per day.
    if state.get("last_canada_sync_date") == today_key:
        return

    # Record attempt before network calls to prevent repeated attempts during failures.
    state["last_canada_sync_date"] = today_key
    state["last_canada_sync_attempt_ts"] = int(time.time())
    save_sync_state(state)

    try:
        counts = sync_canada_companies()
        state["last_canada_sync_success_ts"] = int(time.time())
        state["last_canada_sync_counts"] = counts
        save_sync_state(state)
    except Exception:
        # Keep portal responsive even when external sync fails.
        return


def sync_canada_companies() -> dict[str, int]:
    jobs = load_jobs()
    jobs = [
        j
        for j in jobs
        if not (
            j.id.startswith("enbridge-live-")
            or j.id.startswith("arbeitnow-")
            or j.id.startswith("remoteok-")
        )
    ]

    counts: dict[str, int] = {
        "enbridge": 0,
        "arbeitnow": 0,
        "remoteok": 0,
        "atb": 0,
        "deloitte": 0,
        "infosys": 0,
        "accenture": 0,
        "suncor": 0,
    }

    enbridge_items = fetch_enbridge_jobs_live()
    for item in enbridge_items:
        jobs.append(
            Job(
                id=item["id"],
                title=item["title"],
                company="Enbridge",
                country=item.get("country", "Canada"),
                location=item["location"],
                work_mode=item.get("work_mode", "Hybrid: Remote and Office"),
                category=item["category"],
                posted_date=item["posted_date"],
                source="Enbridge Careers (Live Sync)",
                url=item["url"],
                summary=item["summary"],
                tags=item["tags"],
            )
        )
    counts["enbridge"] = len(enbridge_items)

    arbeitnow_items = fetch_arbeitnow_jobs_live(max_pages=6, page_size=100)
    for item in arbeitnow_items:
        jobs.append(
            Job(
                id=item["id"],
                title=item["title"],
                company=item["company"],
                country=item["country"],
                location=item["location"],
                work_mode=item["work_mode"],
                category=item["category"],
                posted_date=item["posted_date"],
                source="Arbeitnow API (Live Sync)",
                url=item["url"],
                summary=item["summary"],
                tags=item["tags"],
            )
        )
    counts["arbeitnow"] = len(arbeitnow_items)

    remoteok_items = fetch_remoteok_jobs_live(limit=300)
    for item in remoteok_items:
        jobs.append(
            Job(
                id=item["id"],
                title=item["title"],
                company=item["company"],
                country=item["country"],
                location=item["location"],
                work_mode=item["work_mode"],
                category=item["category"],
                posted_date=item["posted_date"],
                source="RemoteOK API (Live Sync)",
                url=item["url"],
                summary=item["summary"],
                tags=item["tags"],
            )
        )
    counts["remoteok"] = len(remoteok_items)

    save_jobs(jobs)
    return {
        "enbridge": counts["enbridge"],
        "arbeitnow": counts["arbeitnow"],
        "remoteok": counts["remoteok"],
        "atb": counts["atb"],
        "deloitte": counts["deloitte"],
        "infosys": counts["infosys"],
        "accenture": counts["accenture"],
        "suncor": counts["suncor"],
    }


def load_sync_state() -> dict[str, Any]:
    if not SYNC_STATE_FILE.exists():
        return {}
    try:
        return json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_sync_state(state: dict[str, Any]) -> None:
    SYNC_STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_enbridge_jobs_from_html(html: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    # Parse visible job cards from Enbridge careers search results.
    # Each card shows title + "Posted X Days Ago" + requisition number.
    title_iter = list(
        re.finditer(r"<a[^>]*>(?P<title>[^<]{6,160})</a>", html, re.I)
    )
    seen = set()
    today = date.today()

    for m in title_iter:
        title = " ".join(m.group("title").split())
        if len(title) < 5 or "Find Jobs" in title or "Read More" in title:
            continue
        window = html[m.end() : m.end() + 1200]
        days_match = re.search(r"Posted\\s+(\\d+)\\s+Days\\s+Ago", window, re.I)
        req_match = re.search(r"\\b(\\d{4,6})\\b", window)
        if not days_match or not req_match:
            continue
        req = req_match.group(1)
        if req in seen:
            continue
        seen.add(req)
        days_ago = int(days_match.group(1))
        posted = today.fromordinal(today.toordinal() - days_ago)
        clean_title = html_unescape(title)
        category = infer_category_from_title(clean_title)
        tags = infer_tags_from_title(clean_title)
        url = f"{ENBRIDGE_CAREERS_URL}?domain=enbridge.com&pid={req}"
        items.append(
            {
                "id": f"enbridge-live-{req}",
                "title": clean_title,
                "location": "Calgary, AB, CAN",
                "posted_date": posted,
                "category": category,
                "summary": f"Enbridge live posting synced from careers site. Requisition ID: {req}.",
                "tags": tags,
                "url": url,
            }
        )

    return items


def fetch_enbridge_jobs_live(limit: int = 20, max_pages: int = 5) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for page in range(max_pages):
        offset = page * limit
        body = json.dumps({"limit": limit, "offset": offset, "searchText": ""}).encode("utf-8")
        req = urllib.request.Request(
            ENBRIDGE_WORKDAY_API,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        except Exception:
            break
        postings = payload.get("jobPostings", [])
        if not postings:
            break
        payloads.extend(postings)
        if len(postings) < limit:
            break

    out: list[dict[str, Any]] = []
    seen = set()
    for job in payloads:
        req_id = ""
        bullets = job.get("bulletFields") or []
        if bullets:
            req_id = str(bullets[0]).strip()
        if not req_id:
            req_id = slug(job.get("title", ""))[:10]
        if req_id in seen:
            continue
        seen.add(req_id)

        posted = posted_on_to_date(job.get("postedOn", ""))
        title = job.get("title", "").strip()
        location_text = (job.get("locationsText") or "").strip()
        remote_type = (job.get("remoteType") or "").strip()
        external_path = (job.get("externalPath") or "").strip()
        url = ENBRIDGE_WORKDAY_BASE + external_path if external_path.startswith("/") else ENBRIDGE_CAREERS_URL

        external_upper = external_path.upper()
        if "-CAN" in external_upper or "CANADA" in external_upper:
            country = "Canada"
        elif " USA" in location_text or "-USA" in external_upper:
            country = "USA"
        else:
            country = "Canada"
        category = infer_category_from_title(title)
        tags = infer_tags_from_title(title)

        if remote_type:
            work_mode = remote_type
        else:
            work_mode = "Onsite / Location-based"

        out.append(
            {
                "id": f"enbridge-live-{req_id}",
                "title": title,
                "location": location_text or "Location not listed",
                "posted_date": posted,
                "category": category,
                "summary": f"Live Enbridge posting synced from Workday API. Requisition ID: {req_id}.",
                "tags": tags,
                "url": url,
                "country": country,
                "work_mode": work_mode,
            }
        )
    return out


def fetch_arbeitnow_jobs_live(max_pages: int = 6, page_size: int = 100) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen = set()

    for page in range(1, max_pages + 1):
        url = f"{ARBEITNOW_API}?page={page}&limit={page_size}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        except Exception:
            break

        jobs = payload.get("data", []) if isinstance(payload, dict) else []
        if not jobs:
            break

        for job in jobs:
            job_id = str(job.get("slug") or job.get("id") or "").strip()
            title = str(job.get("title") or "").strip()
            company = str(job.get("company_name") or "").strip() or "Unknown Company"
            location = str(job.get("location") or "").strip() or "Location not listed"
            url = str(job.get("url") or "").strip()
            description_html = str(job.get("description") or "")
            description = html_to_text(description_html)
            remote_flag = bool(job.get("remote"))
            posted = epoch_to_date(job.get("created_at"))

            if not job_id or not title or not url:
                continue
            if job_id in seen:
                continue
            seen.add(job_id)

            country = infer_country(location=location, remote_hint=remote_flag)
            if not is_relevant_for_user_scope(location=location, country=country, remote_hint=remote_flag):
                continue

            work_mode = infer_work_mode(location=location, remote_hint=remote_flag)
            category = infer_category_from_text(f"{title} {description}")
            tags = infer_tags_from_text(f"{title} {description}")
            summary = summarize_text(description, fallback=f"Live posting from Arbeitnow for {title}.")

            out.append(
                {
                    "id": f"arbeitnow-{slug(job_id)}",
                    "title": title,
                    "company": company,
                    "country": country,
                    "location": location,
                    "work_mode": work_mode,
                    "category": category,
                    "posted_date": posted,
                    "url": url,
                    "summary": summary,
                    "tags": tags,
                }
            )
    return out


def fetch_remoteok_jobs_live(limit: int = 300) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen = set()
    try:
        req = urllib.request.Request(REMOTEOK_API, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except Exception:
        return out

    if not isinstance(payload, list):
        return out

    for item in payload:
        if not isinstance(item, dict):
            continue
        raw_id = str(item.get("id") or "").strip()
        title = str(item.get("position") or "").strip()
        company = str(item.get("company") or "").strip() or "Unknown Company"
        url = str(item.get("url") or item.get("apply_url") or "").strip()
        if not raw_id or not title or not url:
            continue
        if raw_id in seen:
            continue
        seen.add(raw_id)

        location = str(item.get("location") or "").strip() or "Remote"
        date_text = str(item.get("date") or "").strip()
        posted = iso_date_to_date(date_text)
        body = html_to_text(str(item.get("description") or ""))
        text = f"{title} {body} {' '.join(item.get('tags') or [])}".strip()

        country = infer_country(location=location, remote_hint=True)
        if not is_relevant_for_user_scope(location=location, country=country, remote_hint=True):
            continue

        work_mode = infer_work_mode(location=location, remote_hint=True)
        category = infer_category_from_text(text)
        tags = infer_tags_from_text(text)
        summary = summarize_text(body, fallback=f"Live remote posting from RemoteOK for {title}.")
        out.append(
            {
                "id": f"remoteok-{slug(raw_id)}",
                "title": title,
                "company": company,
                "country": country,
                "location": location,
                "work_mode": work_mode,
                "category": category,
                "posted_date": posted,
                "url": url,
                "summary": summary,
                "tags": tags,
            }
        )
        if len(out) >= limit:
            break
    return out


def infer_category_from_text(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("ai engineer", "machine learning", "llm", "mlops", "data scientist")):
        return "AI / ML"
    if any(k in t for k in ("site reliability", "sre", "devops", "platform engineer")):
        return "SRE"
    if any(k in t for k in ("observability", "monitoring", "splunk", "telemetry")):
        return "Observability"
    if "servicenow" in t:
        return "ServiceNow"
    if any(k in t for k in ("cybersecurity", "iam", "siem", "security")):
        return "Cybersecurity"
    if any(k in t for k in ("business analyst", "pmo", "program manager", "governance")):
        return "PMO / Business Analysis"
    if any(k in t for k in ("systems analyst", "application analyst", "application support")):
        return "Systems Analyst"
    return "Information Technology"


def infer_tags_from_text(text: str) -> list[str]:
    lowered = text.lower()
    tags = [phrase for phrase in KNOWN_PROFILE_PHRASES if phrase in lowered]
    if "remote" in lowered:
        tags.append("remote")
    if "hybrid" in lowered:
        tags.append("hybrid")
    if "calgary" in lowered:
        tags.append("calgary")
    if "canada" in lowered:
        tags.append("canada")
    if "usa" in lowered or "united states" in lowered:
        tags.append("usa")
    unique: list[str] = []
    for tag in tags:
        if tag not in unique:
            unique.append(tag)
    return unique[:16] if unique else ["information technology"]


def infer_country(*, location: str, remote_hint: bool) -> str:
    lowered = location.lower()
    if "calgary" in lowered or "canada" in lowered:
        return "Canada"
    if "usa" in lowered or "united states" in lowered or ", us" in lowered:
        return "USA"
    if "north america" in lowered or "canada or us" in lowered or "us/canada" in lowered:
        return "USA/Canada"
    if remote_hint and ("americas" in lowered or "america" in lowered):
        return "USA/Canada"
    return "Global"


def infer_work_mode(*, location: str, remote_hint: bool) -> str:
    lowered = location.lower()
    if "hybrid" in lowered:
        return "Hybrid"
    if remote_hint or "remote" in lowered:
        return "Remote"
    if "onsite" in lowered or "on-site" in lowered or "in person" in lowered:
        return "In person"
    return "Location-based"


def is_relevant_for_user_scope(*, location: str, country: str, remote_hint: bool) -> bool:
    lowered = location.lower()
    if "calgary" in lowered:
        return True
    if country in {"Canada", "USA", "USA/Canada"} and remote_hint:
        return True
    if country in {"Canada", "USA"} and any(k in lowered for k in ("hybrid", "onsite", "on-site", "in person")):
        return True
    return False


def html_to_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = html_unescape(text)
    text = re.sub(r"\\s+", " ", text)
    return text.strip()


def summarize_text(text: str, fallback: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return fallback
    return cleaned[:260].strip() + ("..." if len(cleaned) > 260 else "")


def epoch_to_date(raw: Any) -> date:
    try:
        ts = int(raw)
        return datetime.fromtimestamp(ts, tz=timezone.utc).date()
    except Exception:
        return date.today()


def iso_date_to_date(raw: str) -> date:
    if not raw:
        return date.today()
    candidate = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate).date()
    except Exception:
        return date.today()


def posted_on_to_date(posted_on: str) -> date:
    text = (posted_on or "").strip().lower()
    today = date.today()
    if "today" in text:
        return today
    if "yesterday" in text:
        return today.fromordinal(today.toordinal() - 1)
    m = re.search(r"(\\d+)\\s+day", text)
    if m:
        days = int(m.group(1))
        return today.fromordinal(today.toordinal() - days)
    return today


def html_unescape(text: str) -> str:
    return (
        text.replace("&amp;", "&")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
        .replace("&nbsp;", " ")
    )


def infer_category_from_title(title: str) -> str:
    t = title.lower()
    if "developer" in t or "engineer" in t:
        return "Developer / Engineering"
    if "analyst" in t:
        return "Business / Systems Analysis"
    if "advisor" in t:
        return "Infrastructure / Systems"
    return "Information Technology"


def infer_tags_from_title(title: str) -> list[str]:
    t = title.lower()
    tags = ["enbridge", "information technology", "hybrid", "calgary"]
    if "developer" in t:
        tags += ["developer", "systems"]
    if "analyst" in t:
        tags += ["analyst", "business analysis"]
    if "advisor" in t:
        tags += ["infrastructure", "systems"]
    if "tis" in t:
        tags += ["tis"]
    if "endur" in t:
        tags += ["endur", "etrm"]
    return tags


def filter_and_rank_jobs(
    *,
    jobs: list[Job],
    profile_text: str,
    search_text: str,
    days: int,
    country: str,
    company: str,
    mode: str,
    category: str,
    sort: str,
    resume_titles: list[str] | None = None,
) -> list[dict[str, Any]]:
    today = date.today()
    profile_terms = normalize_terms(profile_text)
    search_terms = normalize_terms(search_text)
    max_age = max(days, 1)
    results: list[dict[str, Any]] = []

    title_terms = resume_titles or []

    for job in jobs:
        age_days = (today - job.posted_date).days
        if age_days < 0 or age_days > max_age:
            continue
        if country != "all" and not country_matches_filter(job.country, country):
            continue
        if company != "all" and canonical_company_name(job.company) != canonical_company_name(company):
            continue
        if mode != "all" and mode.lower() not in job.work_mode.lower():
            continue
        if category != "all" and category.lower() not in job.category.lower():
            continue

        haystack = " ".join(
            [job.title, job.company, job.location, job.work_mode, job.category, job.summary, " ".join(job.tags)]
        ).lower()
        if search_terms and not any(term in haystack for term in search_terms):
            continue

        fit_score, matched_terms = score_job(job, profile_terms, title_terms)
        freshness_score = max(0, 30 - age_days)
        final_score = min(100, fit_score + min(20, freshness_score // 2))

        results.append(
            {
                "job": job,
                "age_days": age_days,
                "fit_score": fit_score,
                "final_score": final_score,
                "fit_label": fit_label(final_score),
                "matched_terms": matched_terms[:8],
            }
        )

    if sort == "newest":
        results.sort(key=lambda item: (item["age_days"], -item["fit_score"]))
    else:
        results.sort(key=lambda item: (-item["final_score"], item["age_days"], item["job"].company))
    return results


def country_matches_filter(job_country: str, filter_country: str) -> bool:
    jc = (job_country or "").strip().lower()
    fc = (filter_country or "").strip().lower()
    if fc == "all":
        return True
    if fc == "canada":
        return "canada" in jc
    if fc == "usa":
        return "usa" in jc or "united states" in jc
    return jc == fc


def score_job(job: Job, profile_terms: list[str], resume_title_terms: list[str] | None = None) -> tuple[int, list[str]]:
    title_text = job.title.lower()
    body_text = " ".join([job.summary, " ".join(job.tags), job.category]).lower()
    score = 0
    matched_terms: list[str] = []
    resume_title_terms = resume_title_terms or []

    for term in profile_terms:
        if term in title_text:
            score += 14
            matched_terms.append(term)
        elif term in body_text:
            score += 8
            matched_terms.append(term)

    # Direct preference weighting toward the user's strongest tracks.
    weighted_phrases = {
        "splunk": 12,
        "observability": 12,
        "site reliability": 12,
        "sre": 10,
        "monitoring": 10,
        "pmo": 9,
        "business analysis": 9,
        "systems analyst": 9,
        "servicenow": 8,
        "cybersecurity": 8,
    }
    combined = f"{job.title} {job.category} {job.summary} {' '.join(job.tags)}".lower()
    for phrase, bonus in weighted_phrases.items():
        if phrase in combined:
            score += bonus
            if phrase not in matched_terms:
                matched_terms.append(phrase)

    for term in resume_title_terms:
        if len(term) < 3:
            continue
        if term in title_text:
            score += 18
            tagged = f"title:{term}"
            if tagged not in matched_terms:
                matched_terms.append(tagged)
        elif term in body_text:
            score += 10
            tagged = f"title:{term}"
            if tagged not in matched_terms:
                matched_terms.append(tagged)

    role_family_bonus = {
        "analyst": 8,
        "engineer": 8,
        "manager": 8,
        "specialist": 6,
        "administrator": 6,
        "consultant": 6,
        "developer": 6,
        "architect": 6,
        "advisor": 6,
    }
    joined_titles = " ".join(resume_title_terms)
    for family, bonus in role_family_bonus.items():
        if family in joined_titles and family in combined:
            score += bonus
            if family not in matched_terms:
                matched_terms.append(family)

    if "calgary" in job.location.lower() and "hybrid" in job.work_mode.lower():
        score += 6
    elif job.country.lower() in {"canada", "usa"} and "remote" in job.work_mode.lower():
        score += 4

    return min(score, 100), matched_terms


def normalize_terms(raw_text: str) -> list[str]:
    if not raw_text:
        return []
    parts = [part.strip().lower() for part in raw_text.replace("\n", ",").split(",")]
    return [part for part in parts if part]


def build_effective_profile(profile_text: str, skills_text: str, desired_role: str) -> str:
    chunks: list[str] = []
    if profile_text:
        chunks.append(profile_text)
    if skills_text:
        chunks.append(skills_text)
    role_keywords = DESIRED_ROLE_KEYWORDS.get(desired_role, "")
    if role_keywords:
        chunks.append(role_keywords)
    merged = ", ".join(chunks)
    terms = normalize_terms(merged)
    deduped: list[str] = []
    seen = set()
    for term in terms:
        if term not in seen:
            deduped.append(term)
            seen.add(term)
    return ", ".join(deduped)


def extract_resume_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt":
        return data.decode("utf-8", errors="ignore")
    if suffix == ".docx":
        try:
            doc = Document(io.BytesIO(data))
            return "\n".join(para.text for para in doc.paragraphs)
        except Exception:
            return ""
    if suffix == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return ""
    return ""


def extract_titles_from_resume_text(text: str) -> list[str]:
    title_tokens = (
        "analyst",
        "engineer",
        "manager",
        "specialist",
        "administrator",
        "consultant",
        "developer",
        "architect",
        "advisor",
        "lead",
        "owner",
        "coordinator",
    )
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    out: list[str] = []
    seen = set()

    for raw in lines:
        line = " ".join(raw.split())
        if len(line) > 100:
            continue
        lowered = line.lower()
        if not any(token in lowered for token in title_tokens):
            continue
        if any(skip in lowered for skip in ("responsibilities", "summary", "education", "certification")):
            continue

        candidate = line
        for sep in ("|", " - ", " — ", " – ", "@"):
            if sep in candidate:
                candidate = candidate.split(sep)[0].strip()
                break
        candidate = re.sub(r"\\([^)]*\\)", "", candidate).strip()
        candidate = re.sub(r"\\s+", " ", candidate)
        if not candidate:
            continue
        if len(candidate) < 3 or len(candidate) > 70:
            continue
        lowered_candidate = candidate.lower()
        if lowered_candidate in seen:
            continue
        seen.add(lowered_candidate)
        out.append(candidate)
        if len(out) >= 12:
            break
    return out


def build_profile_from_resume_text(text: str, jobs: list[Job] | None = None) -> str:
    lowered = text.lower()
    matches = [phrase for phrase in KNOWN_PROFILE_PHRASES if phrase in lowered]
    if not matches:
        source_jobs = jobs if jobs is not None else load_jobs()
        matches = extract_skills_from_resume_text(text, source_jobs)
    if not matches:
        return DEFAULT_PROFILE
    return ", ".join(matches)


def extract_skills_from_resume_text(text: str, jobs: list[Job]) -> list[str]:
    lowered = text.lower()
    candidates = collect_skill_candidates(jobs)
    matched = [c for c in candidates if c in lowered]

    # Add frequent meaningful single-word tokens from resume text.
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-]{2,}", lowered)
    freq: dict[str, int] = {}
    for token in tokens:
        if token in STOPWORDS or token.isdigit():
            continue
        freq[token] = freq.get(token, 0) + 1
    top_tokens = [k for k, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:25]]

    merged = []
    for term in matched + top_tokens:
        if term not in merged:
            merged.append(term)
    return merged


def collect_skill_candidates(jobs: list[Job]) -> list[str]:
    candidates: list[str] = []
    for job in jobs:
        fields = [job.category, job.title, *job.tags]
        for field in fields:
            for part in re.split(r"[,/|]", field.lower()):
                phrase = part.strip()
                if len(phrase) >= 3 and phrase not in STOPWORDS:
                    candidates.append(phrase)
            words = re.findall(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-]{2,}", field.lower())
            for w in words:
                if w not in STOPWORDS:
                    candidates.append(w)
    # Prioritize by uniqueness while preserving order
    unique: list[str] = []
    seen = set()
    for c in candidates:
        if c not in seen:
            unique.append(c)
            seen.add(c)
    return unique


def build_company_options(jobs: list[Job], country: str) -> list[str]:
    if country.lower() == "usa":
        names = sorted({job.company for job in jobs if country_matches_filter(job.country, "usa")})
        return names
    if country.lower() == "canada":
        names = sorted({job.company for job in jobs if country_matches_filter(job.country, "canada")})
        return names
    # Default view: include both Canada and USA employers.
    names = sorted(
        {
            job.company
            for job in jobs
            if country_matches_filter(job.country, "canada") or country_matches_filter(job.country, "usa")
        }
    )
    return names


def canonical_company_name(name: str) -> str:
    key = name.strip().lower()
    return COMPANY_ALIASES.get(key, key)


def build_stats(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"count": 0, "top_score": 0}
    return {
        "count": len(results),
        "top_score": results[0]["final_score"],
    }


def fit_label(score: int) -> str:
    if score >= 80:
        return "Strong Fit"
    if score >= 65:
        return "Good Fit"
    if score >= 50:
        return "Partial Fit"
    return "Low Fit"


def get_job_by_id(jobs: list[Job], job_id: str) -> Job | None:
    for job in jobs:
        if job.id == job_id:
            return job
    return None


def build_tailored_package(job: Job, profile_text: str) -> dict[str, str]:
    profile_terms = normalize_terms(profile_text)
    keywords = prioritize_job_keywords(job)
    aligned = [term for term in keywords if any(term in p for p in profile_terms)] or keywords[:8]

    resume_summary = (
        f"Senior analyst with 18+ years delivering outcomes across {job.category.lower()} environments. "
        f"Targeting {job.title} at {job.company} with strong experience in "
        f"{', '.join(aligned[:5])}, stakeholder communication, and production delivery governance."
    )

    resume_highlights = [
        f"Delivered enterprise initiatives aligned to {job.category} outcomes with measurable process, reliability, and reporting improvements.",
        f"Applied {', '.join(aligned[:4])} to improve service quality, data integrity, and business decision support.",
        "Partnered across IT, security, finance, and business functions to gather requirements and execute production-ready solutions.",
        "Built and maintained governance dashboards and KPI views that improved transparency, accountability, and prioritization.",
        "Led UAT, change coordination, and stakeholder enablement to improve adoption and sustain outcomes over time.",
    ]

    cover_letter = (
        f"Dear Hiring Team,\n\n"
        f"I am applying for the {job.title} role at {job.company}. With 18+ years of experience across "
        f"enterprise IT delivery, governance, and platform operations, I bring strong alignment to your needs in "
        f"{job.category.lower()}.\n\n"
        f"In recent roles, I delivered results in {', '.join(aligned[:6])}, while partnering with cross-functional teams "
        "to improve data quality, reporting visibility, and operational execution. I have consistently translated business "
        "requirements into practical, production-ready solutions and supported adoption through clear stakeholder communication.\n\n"
        f"I am particularly interested in this opportunity because it combines {job.category.lower()} work with the scale and "
        f"impact of {job.company}. I would value the opportunity to contribute and discuss how my background can support your team.\n\n"
        "Sincerely,\n"
        f"{DEFAULT_NAME}\n"
    )

    resume_text = build_full_tailored_resume(
        job=job,
        summary=resume_summary,
        aligned=aligned,
        intro_highlights=resume_highlights,
    )

    return {
        "job_title": job.title,
        "company": job.company,
        "resume_text": resume_text,
        "cover_letter_text": cover_letter,
    }


def build_full_tailored_resume(
    *,
    job: Job,
    summary: str,
    aligned: list[str],
    intro_highlights: list[str],
) -> str:
    competencies = [
        "Program and project governance",
        "Business and systems analysis",
        "Observability and monitoring operations",
        "ServiceNow and CMDB process alignment",
        "Data quality controls and reporting standards",
        "Incident management and root cause analysis",
        "Stakeholder communication and cross-functional delivery",
        "Power BI, SQL, Python, and automation support",
    ]
    skills_line = ", ".join(dict.fromkeys(aligned + competencies))[:800]
    lines: list[str] = []
    lines.append(DEFAULT_NAME)
    lines.append(DEFAULT_CONTACT)
    lines.append("")
    lines.append(f"TARGET ROLE: {job.title} | TARGET COMPANY: {job.company}")
    lines.append("")
    lines.append("PROFESSIONAL SUMMARY")
    lines.append(summary)
    lines.append("")
    lines.append("ROLE ALIGNMENT HIGHLIGHTS")
    lines.extend(f"- {item}" for item in intro_highlights)
    lines.append("")
    lines.append("CORE SKILLS")
    lines.append(f"- {skills_line}")
    lines.append("")
    lines.append("PROFESSIONAL EXPERIENCE")
    for exp in EXPERIENCE_LIBRARY:
        lines.append(f"{exp['title']} | {exp['company']} | {exp['dates']}")
        for bullet in exp["bullets"]:
            lines.append(f"- {bullet}")
        lines.append("")
    lines.append("EDUCATION")
    lines.append("Bachelor of Engineering, Computer Science — College of Engineering, Roorkee, India (2004)")
    lines.append("")
    lines.append("CERTIFICATIONS")
    lines.append(
        "AWS Cloud Practitioner | Microsoft Identity & Access Management Associate | PagerDuty Certified Incident Responder | "
        "Splunk ITSI | Splunk Enterprise Security | IT Project Management Methodology"
    )
    lines.append("")
    lines.append("NOTE")
    lines.append(
        "This tailored draft intentionally includes full career coverage and expanded bullet detail to support a two-page resume format."
    )
    return "\n".join(lines)


def prioritize_job_keywords(job: Job) -> list[str]:
    pool = [
        job.title.lower(),
        job.category.lower(),
        job.summary.lower(),
        *[t.lower() for t in job.tags],
    ]
    joined = " ".join(pool)
    priorities = [
        "splunk",
        "observability",
        "site reliability",
        "sre",
        "monitoring",
        "pmo",
        "program management",
        "business analysis",
        "systems analyst",
        "servicenow",
        "cybersecurity",
        "incident response",
        "data quality",
        "governance",
        "sql",
        "aws",
        "azure",
        "python",
        "terraform",
        "dashboards",
    ]
    found = [k for k in priorities if k in joined]
    if not found:
        found = job.tags[:]
    return found


def slug(raw: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in raw).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned[:48] or "item"


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
