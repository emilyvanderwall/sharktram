#!/usr/bin/env python3
"""
Shark Valley Tram Tour availability watcher.

Watches a specific tour's event page on sharkvalleytramtours.com and sends a
Discord alert (via webhook) the moment tickets become available.

How it works
------------
Each tour date/time has its own page, e.g.:
    https://www.sharkvalleytramtours.com/event/200pm-tour/2026-11-07_200pm/

That page always contains one of two telltale phrases:
  - Sold out:   "Advanced reservations for this tour are either sold out or no longer available."
  - Available:  "Currently, there are N Tickets available for purchase."

This script polls that page on an interval, and the first time it flips from
sold-out to available, it fires a Discord webhook message. It remembers state
on disk (last_state.json next to this script) so it won't spam you every poll
once it has already alerted for the current "available" streak, and will
alert again if it goes sold-out and then re-opens later.

Setup
-----
This script never hardcodes the webhook URL - it always reads it from the
DISCORD_WEBHOOK_URL environment variable, so it's safe to commit to a public
GitHub repo. See README.md for both local and GitHub Actions setup.

1. pip install -r requirements.txt
2. Create a Discord webhook: in Discord, go to the channel you want alerts in
   -> Edit Channel -> Integrations -> Webhooks -> New Webhook -> Copy URL.
3. Export it locally for a test run:
       export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
       python3 tram_tour_watcher.py --once
4. For unattended use, either leave it running (loops on CHECK_INTERVAL_SECONDS)
   or - recommended - use the included GitHub Actions workflow, which runs it
   on a schedule for free without you needing to keep a machine on. See
   README.md.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Configuration - set these as environment variables (see README.md)
# ---------------------------------------------------------------------------

# The specific tour date/time page to watch. This is the 11/7/26 2:00 PM tour.
# To watch a different date/time, swap in that event's URL from
# https://www.sharkvalleytramtours.com/event-calendar/ (click the tour you
# want; the URL in your browser's address bar is what goes here).
EVENT_URL = os.environ.get(
    "EVENT_URL",
    "https://www.sharkvalleytramtours.com/event/200pm-tour/2026-11-07_200pm/",
)

# Your Discord webhook URL. Get one from Discord: Channel Settings ->
# Integrations -> Webhooks -> New Webhook -> Copy Webhook URL.
# Set via environment variable / GitHub Actions secret - never hardcode it here.
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# How often to check, in seconds. Be a reasonable neighbor to their server;
# every 5-10 minutes is plenty for a ticket watch.
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", 5 * 60))

# Where to persist "did we already alert for this open streak" state, so
# restarting the script doesn't re-send an alert you've already seen.
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_state.json")

# ---------------------------------------------------------------------------

SOLD_OUT_PHRASE = "sold out or no longer available"
AVAILABLE_PATTERN = re.compile(
    r"Currently,\s*there are\s*(\d+)\s*Tickets? available for purchase", re.IGNORECASE
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_status": None, "alerted_for_current_streak": False}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def check_availability() -> tuple[str, int | None]:
    """Fetch the event page and classify it.

    Returns (status, ticket_count) where status is one of:
      "available", "sold_out", "unknown"
    """
    resp = requests.get(EVENT_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    text = resp.text

    match = AVAILABLE_PATTERN.search(text)
    if match:
        return "available", int(match.group(1))

    if SOLD_OUT_PHRASE in text.lower():
        return "sold_out", None

    return "unknown", None


def send_discord_alert(ticket_count: int) -> None:
    if not DISCORD_WEBHOOK_URL:
        log("No Discord webhook URL configured (DISCORD_WEBHOOK_URL) - skipping alert, but tickets are available!")
        return

    content = (
        f"🚨 **Tram tour tickets available!** 🚨\n"
        f"{ticket_count} ticket(s) open for the tour at:\n"
        f"{EVENT_URL}\n"
        f"Go grab it before it's gone!"
    )
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=15)
        if r.status_code >= 300:
            log(f"Discord webhook returned {r.status_code}: {r.text}")
        else:
            log("Discord alert sent.")
    except requests.RequestException as e:
        log(f"Failed to send Discord alert: {e}")


def send_discord_note(message: str) -> None:
    """Send a low-priority note to Discord (used for error notifications)."""
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=15)
    except requests.RequestException:
        pass


def run_once(state: dict) -> dict:
    try:
        status, count = check_availability()
    except requests.RequestException as e:
        log(f"Error fetching page: {e}")
        return state

    if status == "available":
        log(f"Status: AVAILABLE ({count} tickets)")
        if not state.get("alerted_for_current_streak"):
            send_discord_alert(count)
            state["alerted_for_current_streak"] = True
    elif status == "sold_out":
        log("Status: sold out")
        state["alerted_for_current_streak"] = False
    else:
        log("Status: unknown (page structure may have changed - check EVENT_URL manually)")

    state["last_status"] = status
    return state


def main() -> None:
    log(f"Watching: {EVENT_URL}")
    log(f"Checking every {CHECK_INTERVAL_SECONDS} seconds. Press Ctrl+C to stop.")
    state = load_state()

    # Support a single-shot mode for cron/Task Scheduler: pass --once
    if "--once" in sys.argv:
        state = run_once(state)
        save_state(state)
        return

    while True:
        state = run_once(state)
        save_state(state)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------------
# Running this unattended
# ---------------------------------------------------------------------------
# Option A - leave it running:
#   python3 tram_tour_watcher.py
#   (runs forever, checking on CHECK_INTERVAL_SECONDS; ctrl-C to stop)
#
# Option B - cron (macOS/Linux), check every 5 minutes:
#   */5 * * * * /usr/bin/python3 /full/path/to/tram_tour_watcher.py --once >> /full/path/to/tram_watcher.log 2>&1
#
# Option C - Windows Task Scheduler:
#   Create a task that runs every 5 minutes with:
#     Program: python
#     Arguments: "C:\full\path\to\tram_tour_watcher.py" --once
# ---------------------------------------------------------------------------
