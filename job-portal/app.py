from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
import io
from pathlib import Path
from typing import Any

from flask import Flask, render_template, request
from docx import Document
from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "jobs.json"
DEFAULT_PROFILE = (
    "splunk, observability, site reliability, sre, monitoring, pmo, program management, "
    "business analysis, systems analyst, servicenow, cybersecurity, incident response, "
    "pagerduty, python, terraform, aws, azure, itsi, siem, dashboards, root cause analysis"
)
DEFAULT_NAME = "Shilpi Jain"
DEFAULT_CONTACT = "Calgary, AB, Canada | +1 403 629 7327 | j.shilpi1@gmail.com"
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
        profile_text = source.get("profile", DEFAULT_PROFILE).strip()
        search_text = source.get("q", "").strip()
        days = int(source.get("days", "5"))
        country = source.get("country", "all")
        mode = source.get("mode", "all")
        category = source.get("category", "all")
        sort = source.get("sort", "best_fit")
        upload_note = ""
        tailored: dict[str, str] | None = None

        if request.method == "POST" and source.get("use_resume_profile") == "1":
            resume_file = request.files.get("resume_file")
            if resume_file and resume_file.filename:
                resume_text = extract_resume_text(resume_file.filename, resume_file.read())
                if resume_text:
                    profile_text = build_profile_from_resume_text(resume_text)
                    upload_note = f"Profile generated from {resume_file.filename}."
                else:
                    upload_note = "Could not read resume file. Using current profile keywords."

        if request.method == "POST" and action == "tailor_job":
            selected_job = get_job_by_id(jobs, source.get("job_id", ""))
            if selected_job:
                tailored = build_tailored_package(selected_job, profile_text)

        ranked_jobs = filter_and_rank_jobs(
            jobs=jobs,
            profile_text=profile_text,
            search_text=search_text,
            days=days,
            country=country,
            mode=mode,
            category=category,
            sort=sort,
        )

        return render_template(
            "index.html",
            jobs=ranked_jobs,
            filters={
                "profile": profile_text,
                "q": search_text,
                "days": days,
                "country": country,
                "mode": mode,
                "category": category,
                "sort": sort,
            },
            stats=build_stats(ranked_jobs),
            today=date.today(),
            upload_note=upload_note,
            tailored=tailored,
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


def filter_and_rank_jobs(
    *,
    jobs: list[Job],
    profile_text: str,
    search_text: str,
    days: int,
    country: str,
    mode: str,
    category: str,
    sort: str,
) -> list[dict[str, Any]]:
    today = date.today()
    profile_terms = normalize_terms(profile_text)
    search_terms = normalize_terms(search_text)
    max_age = max(days, 1)
    results: list[dict[str, Any]] = []

    for job in jobs:
        age_days = (today - job.posted_date).days
        if age_days < 0 or age_days > max_age:
            continue
        if country != "all" and job.country.lower() != country.lower():
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

        fit_score, matched_terms = score_job(job, profile_terms)
        freshness_score = max(0, 30 - age_days)
        final_score = min(100, fit_score + min(20, freshness_score // 2))

        results.append(
            {
                "job": job,
                "age_days": age_days,
                "fit_score": fit_score,
                "final_score": final_score,
                "matched_terms": matched_terms[:8],
            }
        )

    if sort == "newest":
        results.sort(key=lambda item: (item["age_days"], -item["fit_score"]))
    else:
        results.sort(key=lambda item: (-item["final_score"], item["age_days"], item["job"].company))
    return results


def score_job(job: Job, profile_terms: list[str]) -> tuple[int, list[str]]:
    title_text = job.title.lower()
    body_text = " ".join([job.summary, " ".join(job.tags), job.category]).lower()
    score = 0
    matched_terms: list[str] = []

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


def build_profile_from_resume_text(text: str) -> str:
    lowered = text.lower()
    matches = [phrase for phrase in KNOWN_PROFILE_PHRASES if phrase in lowered]
    if not matches:
        return DEFAULT_PROFILE
    return ", ".join(matches)


def build_stats(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"count": 0, "top_score": 0}
    return {
        "count": len(results),
        "top_score": results[0]["final_score"],
    }


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
        f"Delivered enterprise initiatives aligned to {job.category} outcomes with measurable process and reporting improvements.",
        f"Applied {', '.join(aligned[:4])} to improve service reliability, data quality, and decision support.",
        "Partnered across IT, security, finance, and business teams to gather requirements and execute production rollouts.",
        "Built and maintained dashboards, metrics, and governance practices that strengthened operational transparency.",
        "Led UAT, change coordination, and stakeholder enablement to ensure adoption and sustained value.",
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

    resume_text = (
        f"{DEFAULT_NAME}\n"
        f"{DEFAULT_CONTACT}\n\n"
        f"Target Role: {job.title} | Company: {job.company}\n\n"
        f"Tailored Professional Summary:\n{resume_summary}\n\n"
        "Tailored Core Skills:\n"
        f"- {', '.join(aligned[:10])}\n\n"
        "Suggested Experience Highlights:\n"
        + "\n".join(f"- {line}" for line in resume_highlights)
    )

    return {
        "job_title": job.title,
        "company": job.company,
        "resume_text": resume_text,
        "cover_letter_text": cover_letter,
    }


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


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
