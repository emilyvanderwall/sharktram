# Shark Valley Tram Tour Watcher

Watches the 2:00 PM tram tour on 11/7/26 and pings a Discord channel via
webhook the moment tickets become available.

## Repo layout

Create a new GitHub repo with this structure:

```
your-repo/
├── tram_tour_watcher.py
├── requirements.txt
├── .gitignore
└── .github/
    └── workflows/
        └── check-availability.yml
```

Note: `check-availability.yml` in this folder needs to go inside a
`.github/workflows/` directory in your repo — GitHub only picks up workflows
from that exact path.

## Setup (GitHub Actions — recommended, runs for free, no machine to keep on)

1. Create a new repo on GitHub (can be private) and push these files, with
   `check-availability.yml` moved to `.github/workflows/check-availability.yml`.
2. In the repo, go to **Settings → Secrets and variables → Actions → New
   repository secret**.
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: your webhook URL (the one you already generated in Discord)
3. Go to the **Actions** tab and enable workflows if prompted. The workflow
   runs automatically every ~15 minutes. You can also trigger it manually from
   Actions → "Check Tram Tour Availability" → **Run workflow**.
4. Watch your Discord channel. When the 11/7/26 2:00 PM tour opens up, you'll
   get a message with a link straight to the booking page.

Your webhook URL never appears in any file in the repo — it only lives in the
GitHub secret, so it's safe even in a public repo.

## Setup (run it yourself locally instead)

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/your-webhook-here"
python3 tram_tour_watcher.py          # loops forever, checks every 5 min
# or:
python3 tram_tour_watcher.py --once   # single check, good for your own cron job
```

## Watching a different date/time

Open the event's page on the
[event calendar](https://www.sharkvalleytramtours.com/event-calendar/), copy
its URL, and either edit the `EVENT_URL` default in `tram_tour_watcher.py`, or
set it via an `EVENT_URL` env var / repo secret the same way as the webhook.

## How it detects availability

Each tour's page always contains one of two phrases:

- Sold out: "Advanced reservations for this tour are either sold out or no
  longer available."
- Open: "Currently, there are N Tickets available for purchase."

The script checks for these directly in the page's HTML — no browser
automation needed.
