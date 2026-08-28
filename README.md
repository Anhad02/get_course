# UW Waterloo Course Seat Monitor

Watches a course section on the University of Waterloo
[Schedule of Classes](https://classes.uwaterloo.ca/cgi-bin/cgiwrap/infocour/salook.pl)
and notifies you (SMS, phone call, or email) when a seat opens up.

It checks on an interval (default every 10 minutes), compares **Enrl Cap** vs
**Enrl Tot** for your target section, and sends a notification the moment
`Enrl Tot < Enrl Cap`.

## How it works

- `scraper.py` — fetches the schedule page and parses the section table.
- `notifier.py` — sends the alert via Twilio SMS, Twilio voice call, or email.
- `monitor.py` — the entry point; loads config, loops on an interval, notifies.

The page is queried with four values: `subject`, `cournum` (catalog number),
`level` (`under`/`grad`), and `sess` (term code). A "section" like **81** is
matched against the component number, so `81` matches `LEC 081`, `TST 081`, etc.

## Setup

1. Install Python 3.10+ then set up a virtual environment and dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy the example config and fill it in:

   ```bash
   cp .env.example .env
   ```

   Edit `.env`:

   | Variable | What it is |
   |----------|------------|
   | `SUBJECT` | Subject code, e.g. `CS`, `MATH`, `ECE` |
   | `COURSE_NUMBER` | Catalog number, e.g. `350` |
   | `SECTION` | Section to watch, e.g. `81` |
   | `LEVEL` | `under` (undergrad) or `grad` |
   | `SESSION` | Term code from the schedule site URL, e.g. `1259` |
   | `CHECK_INTERVAL_MINUTES` | How often to check (default `10`) |
   | `NOTIFY_METHOD` | `twilio_sms`, `twilio_call`, or `email` |

### Finding the term (`SESSION`) code

Go to the [Schedule of Classes](https://classes.uwaterloo.ca/), pick your term
and any subject, and look at the `sess=` value in the resulting URL. That
number is your `SESSION`.

## Notification setup

Pick one method and fill in the matching values in `.env`.

### Option A — Text / call (Twilio)

1. Create an account at [twilio.com](https://www.twilio.com/) and get a phone number.
2. From the Twilio console copy your **Account SID** and **Auth Token**.
3. Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_PHONE` (your
   Twilio number), and `TO_PHONE` (your phone, e.g. `+15559876543`).
4. Set `NOTIFY_METHOD=twilio_sms` for a text or `twilio_call` for a phone call
   that reads the alert aloud.

Note: a Twilio trial account can only send to verified numbers and prefixes
messages with a trial notice. That's fine for personal use.

### Option B — Email (free)

Using Gmail:

1. Turn on 2-Step Verification, then create an
   [App Password](https://support.google.com/accounts/answer/185833).
2. Set `SMTP_USER` to your Gmail address, `SMTP_PASSWORD` to the app password,
   and `EMAIL_TO` to where you want the alert.
3. Set `NOTIFY_METHOD=email`.

Tip: most carriers have an email-to-SMS gateway (e.g.
`5551234567@vtext.com`), so emailing that address effectively texts you.

## Running

Test your notification setup first:

```bash
python monitor.py --test-notify
```

Run a single check (prints current seat status, notifies if open):

```bash
python monitor.py --once
```

Run continuously, checking every `CHECK_INTERVAL_MINUTES`:

```bash
python monitor.py
```

While running, it only notifies once per opening: it alerts on the change from
full to open, and re-arms after the section fills again, so you won't get a
message every interval.

## Running it on a schedule

You can either keep `python monitor.py` running (it sleeps between checks), or
use `--once` with a scheduler.

### macOS / Linux cron

Run `crontab -e` and add (adjust the paths):

```cron
*/10 * * * * cd /Users/achadman/Desktop/papa_project/Course-Selection && .venv/bin/python monitor.py --once >> monitor.log 2>&1
```

That runs a check every 10 minutes and appends output to `monitor.log`.

## Notes

- This scrapes a public UW page. Keep the interval reasonable (10 minutes is
  polite) to avoid hammering the server.
- If the section number can't be found, the log lists the sections that do
  exist for that course/term so you can correct your config.
- `.env` is git-ignored so your credentials stay out of version control.
