from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()


DEFAULT_PREFS = {
    "participant_name": "Shilpi Jain",
    "location": "Seton, Calgary",
    "class_name": "Zumba",
    "day_of_week": "Thursday",
    "start_time": "18:00",
    "end_time": "19:00",
}


@dataclass
class YMCAClass:
    class_id: str
    name: str
    location: str
    day_of_week: str
    start_time: str
    end_time: str
    instructor: str
    spots_left: int


class YmcaApiClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def search_classes(self, prefs: dict[str, str]) -> list[YMCAClass]:
        # Endpoint shape may vary by provider; update path/params to match YMCA API docs.
        params = {
            "location": prefs["location"],
            "class_name": prefs["class_name"],
            "day": prefs["day_of_week"],
            "start_time": prefs["start_time"],
            "end_time": prefs["end_time"],
        }
        response = requests.get(
            f"{self.base_url}/classes",
            params=params,
            headers=self._headers(),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("classes", payload if isinstance(payload, list) else [])

        classes: list[YMCAClass] = []
        for item in items:
            classes.append(
                YMCAClass(
                    class_id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    location=str(item.get("location", "")),
                    day_of_week=str(item.get("day_of_week", "")),
                    start_time=str(item.get("start_time", "")),
                    end_time=str(item.get("end_time", "")),
                    instructor=str(item.get("instructor", "TBD")),
                    spots_left=int(item.get("spots_left", 0)),
                )
            )
        return classes

    def book_class(self, class_id: str, participant_name: str) -> dict[str, Any]:
        payload = {
            "class_id": class_id,
            "participant_name": participant_name,
        }
        response = requests.post(
            f"{self.base_url}/bookings",
            json=payload,
            headers=self._headers(),
            timeout=20,
        )
        response.raise_for_status()
        return response.json() if response.content else {"status": "booked"}


class MockYmcaClient:
    def search_classes(self, prefs: dict[str, str]) -> list[YMCAClass]:
        catalog = [
            YMCAClass(
                class_id="270336",
                name="Zumba (6:00pm w/Claudia)",
                location="Seton, Calgary",
                day_of_week="Thursday",
                start_time="18:00",
                end_time="19:00",
                instructor="Claudia",
                spots_left=8,
            ),
            YMCAClass(
                class_id="seton-zumba-fri-1815",
                name="Zumba",
                location="Seton, Calgary",
                day_of_week="Friday",
                start_time="18:15",
                end_time="19:00",
                instructor="M. Singh",
                spots_left=3,
            ),
        ]
        return [
            c
            for c in catalog
            if prefs["class_name"].lower() in c.name.lower()
            and prefs["day_of_week"].lower() == c.day_of_week.lower()
            and prefs["location"].lower() in c.location.lower()
            and c.start_time >= prefs["start_time"]
            and c.end_time <= prefs["end_time"]
        ]

    def book_class(self, class_id: str, participant_name: str) -> dict[str, Any]:
        return {
            "status": "booked",
            "booking_id": f"demo-{class_id}",
            "class_id": class_id,
            "participant_name": participant_name,
            "booked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "source": "mock",
        }


def build_client() -> YmcaApiClient | MockYmcaClient:
    base_url = os.getenv("YMCA_API_BASE_URL", "").strip()
    token = os.getenv("YMCA_API_TOKEN", "").strip()
    if base_url and token:
        return YmcaApiClient(base_url=base_url, token=token)
    return MockYmcaClient()


app = Flask(__name__)
client = build_client()
BOOKING_STATUS_FILE = Path(__file__).resolve().parent / "last_booking_status.json"


def merged_prefs(form: dict[str, str]) -> dict[str, str]:
    out = DEFAULT_PREFS.copy()
    for key in out:
        val = form.get(key, "").strip()
        if val:
            out[key] = val
    return out


def normalize_weekday(raw: str) -> str:
    val = (raw or "").strip().lower()
    mapping = {
        "monday": "MON",
        "mon": "MON",
        "tuesday": "TUE",
        "tue": "TUE",
        "wednesday": "WED",
        "wed": "WED",
        "thursday": "THU",
        "thu": "THU",
        "friday": "FRI",
        "fri": "FRI",
        "saturday": "SAT",
        "sat": "SAT",
        "sunday": "SUN",
        "sun": "SUN",
    }
    return mapping.get(val, "FRI")


def build_schedule_defaults(form: dict[str, str] | None = None) -> dict[str, str]:
    source = form or {}
    return {
        "task_name": source.get("task_name", "YMCA_Book_Zumba"),
        "day": source.get("schedule_day", "FRI"),
        "time": source.get("schedule_time", "10:25"),
    }


def create_windows_task(*, task_name: str, day: str, time_24h: str) -> None:
    task = (task_name or "").strip() or "YMCA_Book_Zumba"
    day_token = normalize_weekday(day)
    time_token = (time_24h or "").strip()
    if len(time_token) != 5 or time_token[2] != ":":
        raise ValueError("Time must be HH:MM format, e.g., 10:25 or 11:00.")

    project_dir = Path(__file__).resolve().parent
    script_path = project_dir / "book_once.py"
    python_path = Path(sys.executable).resolve()
    tr = f'"{python_path}" "{script_path}"'

    cmd = [
        "schtasks",
        "/Create",
        "/TN",
        task,
        "/TR",
        tr,
        "/SC",
        "WEEKLY",
        "/D",
        day_token,
        "/ST",
        time_token,
        "/F",
    ]
    subprocess.run(cmd, check=True, cwd=str(project_dir), capture_output=True, text=True)


def load_last_booking_status() -> dict[str, str]:
    if not BOOKING_STATUS_FILE.exists():
        return {}
    try:
        payload = json.loads(BOOKING_STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        "status": str(payload.get("status", "")),
        "message": str(payload.get("message", "")),
        "step": str(payload.get("step", "")),
        "timestamp_utc": str(payload.get("timestamp_utc", "")),
    }


@app.get("/health")
def health() -> Any:
    return jsonify({"ok": True, "mode": "api" if isinstance(client, YmcaApiClient) else "mock"})


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    prefs = merged_prefs(request.form if request.method == "POST" else request.args)
    schedule = build_schedule_defaults(request.form if request.method == "POST" else None)
    classes: list[YMCAClass] = []
    note = ""
    error = ""
    last_booking_status = load_last_booking_status()

    if request.method == "POST" and request.form.get("action") == "search":
        try:
            classes = client.search_classes(prefs)
            if not classes:
                note = "No exact class found. Try widening time or location."
        except Exception as exc:  # noqa: BLE001
            error = f"Search failed: {exc}"

    if request.method == "POST" and request.form.get("action") == "book":
        class_id = request.form.get("class_id", "").strip()
        if not class_id:
            error = "Select a class first."
        else:
            try:
                result = client.book_class(class_id=class_id, participant_name=prefs["participant_name"])
                note = f"Booked successfully. Booking ref: {result.get('booking_id', 'N/A')}"
                classes = client.search_classes(prefs)
            except Exception as exc:  # noqa: BLE001
                error = f"Booking failed: {exc}"

    if request.method == "POST" and request.form.get("action") == "schedule":
        schedule = build_schedule_defaults(request.form)
        try:
            create_windows_task(
                task_name=schedule["task_name"],
                day=schedule["day"],
                time_24h=schedule["time"],
            )
            note = (
                f"Scheduled task created: {schedule['task_name']} "
                f"({normalize_weekday(schedule['day'])} at {schedule['time']} MT)."
            )
        except Exception as exc:  # noqa: BLE001
            error = f"Schedule failed: {exc}"

    return render_template(
        "index.html",
        prefs=prefs,
        classes=classes,
        note=note,
        error=error,
        schedule=schedule,
        last_booking_status=last_booking_status,
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    app.run(host="127.0.0.1", port=port, debug=True)
