from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

STATUS_FILE = Path(__file__).with_name("last_booking_status.json")


def getenv(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def click_first(page, names: list[str], timeout_ms: int = 4000) -> bool:
    for name in names:
        try:
            locator = page.get_by_role("button", name=name).first
            if locator.is_visible(timeout=timeout_ms):
                locator.click()
                return True
        except Exception:
            continue
    return False


def click_any(page, labels: list[str], timeout_ms: int = 5000) -> bool:
    for label in labels:
        # Try accessible button role first.
        try:
            btn = page.get_by_role("button", name=label).first
            if btn.is_visible(timeout=timeout_ms):
                btn.click()
                return True
        except Exception:
            pass
        # Fallback: any element containing visible text.
        try:
            node = page.locator(f"text={label}").first
            if node.is_visible(timeout=timeout_ms):
                node.click()
                return True
        except Exception:
            pass
    return False


def wait_for_any_text(page, candidates: list[str], timeout_ms: int = 60000) -> str:
    for text in candidates:
        try:
            page.get_by_text(text).first.wait_for(timeout=timeout_ms)
            return text
        except Exception:
            continue
    raise PlaywrightTimeoutError(f"None of expected texts appeared: {candidates}")


def write_status(*, status: str, message: str, step: str, details: dict | None = None) -> None:
    payload = {
        "status": status,
        "message": message,
        "step": step,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "details": details or {},
    }
    STATUS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))

    portal_url = getenv("YMCA_PORTAL_URL", "https://ymcacalgary.my.site.com/#/app/program/list/DIV-007/")
    username = getenv("YMCA_USERNAME")
    password = getenv("YMCA_PASSWORD")
    target_program = getenv("YMCA_TARGET_PROGRAM", "Zumba")
    target_class_id = getenv("YMCA_TARGET_CLASS_ID", "270336")
    target_day = getenv("YMCA_TARGET_DAY", "Thu")
    target_time = getenv("YMCA_TARGET_TIME", "6:00 PM - 7:00 PM")
    dry_run = getenv("YMCA_DRY_RUN", "1") != "0"
    context_details = {
        "program": target_program,
        "class_id": target_class_id,
        "day": target_day,
        "time": target_time,
        "dry_run": dry_run,
    }
    write_status(status="RUNNING", message="Automation started.", step="startup", details=context_details)

    print("Opening YMCA portal...")
    print(f"Program={target_program}, class_id={target_class_id}, day={target_day}, time={target_time}, dry_run={dry_run}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=150)
            context = browser.new_context()
            page = context.new_page()
            page.goto(portal_url, wait_until="domcontentloaded", timeout=120000)

            # Login if prompted.
            if username and password:
                try:
                    email_input = page.locator("input[type='email'], input[name*='user'], input[name*='email']").first
                    if email_input.is_visible(timeout=5000):
                        email_input.fill(username)
                        pw_input = page.locator("input[type='password']").first
                        pw_input.fill(password)
                        if not click_first(page, ["Log In", "Login", "Sign In", "Next"]):
                            page.keyboard.press("Enter")
                except Exception:
                    pass
            else:
                print("No YMCA_USERNAME/YMCA_PASSWORD in .env. If login page appears, sign in manually in the opened browser.")

            wait_for_any_text(page, ["Drop-in Registration", "Drop-in Results", "Program List"], timeout_ms=180000)
            print("Loaded booking portal.")

            # Search by program.
            search_input = page.locator("input[placeholder*='Search'], input[placeholder*='search']").first
            search_input.click()
            search_input.fill(target_program)
            if not click_first(page, ["Search"]):
                write_status(
                    status="FAILED",
                    message="Search button not found.",
                    step="search",
                    details=context_details,
                )
                print("FAILED: Search button not found.")
                return 2
            print("Search submitted.")

            wait_for_any_text(page, ["Drop-in Results", "Results"], timeout_ms=60000)

            # Open offerings.
            if not click_first(page, ["View Offerings"]):
                write_status(
                    status="FAILED",
                    message="Could not find 'View Offerings' button.",
                    step="open_offerings",
                    details=context_details,
                )
                print("FAILED: Could not find 'View Offerings' button.")
                return 3
            print("Opened offerings.")

        # Try to focus target offering details.
        found_marker = False
        for marker in [target_class_id, target_day, target_time, target_program]:
            try:
                page.get_by_text(marker, exact=False).first.wait_for(timeout=25000)
                found_marker = True
                break
            except Exception:
                continue
            if not found_marker:
                print("Warning: target offering markers were not detected. Please verify page manually.")
            else:
                print("Offering marker detected.")

        # YMCA modal flow: Select person -> Next -> Add to Cart -> Checkout/Confirm.
        # Try to enter registration step if needed.
            _ = click_any(page, ["Book", "Register", "Enroll", "Continue", "Add to Cart"], timeout_ms=4000)
            wait_for_any_text(
                page,
                ["Select a Person to Register", "Registration", "About Program", "Add to Cart"],
                timeout_ms=40000,
            )
            print("Registration flow opened.")

        # Select default person card.
            person_selected = False
            try:
                person_row = page.locator("tr, div").filter(has_text="Shilpi Jain").first
                select_btn = person_row.get_by_role("button", name="Select").first
                if select_btn.is_visible(timeout=3000):
                    select_btn.click()
                    person_selected = True
            except Exception:
                pass
            if not person_selected:
                person_selected = click_any(page, ["Select"], timeout_ms=4000)
            print(f"Person select clicked: {person_selected}")

        # Move from step 1 to step 2.
            next_clicked = click_any(page, ["Next", "Continue"], timeout_ms=6000)
            print(f"Next clicked: {next_clicked}")

        # Add to cart step.
            add_clicked = click_any(page, ["Add to Cart", "Add", "Register"], timeout_ms=10000)
            print(f"Add to Cart clicked: {add_clicked}")

            if dry_run:
                message = "Dry run reached Add to Cart stage; no final submit."
                write_status(status="DRY_RUN", message=message, step="pre_submit", details=context_details)
                print("DRY RUN enabled. Stopping before final confirmation/checkout.")
                print("Set YMCA_DRY_RUN=0 in .env to allow final submit attempts.")
                input("Press Enter to close browser...")
                browser.close()
                return 0

            # Final confirmation click.
            if click_any(page, ["Checkout", "Confirm", "Complete Booking", "Place Order", "Submit"], timeout_ms=12000):
                write_status(
                    status="SUCCESS",
                    message="Final confirmation submitted.",
                    step="submit",
                    details=context_details,
                )
                print("SUCCESS: Final confirmation submitted.")
            else:
                write_status(
                    status="FAILED",
                    message="Final confirmation button not found.",
                    step="submit",
                    details=context_details,
                )
                print("FAILED: Final confirmation button not found automatically. Please confirm manually.")
                input("Press Enter to close browser...")

            browser.close()
            return 0
    except Exception as exc:  # noqa: BLE001
        write_status(
            status="FAILED",
            message=f"Unhandled error: {exc}",
            step="exception",
            details={"traceback": traceback.format_exc(), **context_details},
        )
        print(f"FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
