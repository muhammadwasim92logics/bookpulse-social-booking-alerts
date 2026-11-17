# BookPulse

### Social booking, appointment management, and Slack notifications

BookPulse is a Django web application prototype for collecting appointment
requests from social media visitors. It includes a public booking page, an
authenticated staff dashboard, email verification, Slack notifications, and
UTM-based link attribution.

> **Project status: prototype.** The booking workflow and dashboard are
> implemented, but social-platform OAuth and live analytics are not. Review
> [Current scope and limitations](#current-scope-and-limitations) before using
> this project with real visitors or deploying it.

**Suggested GitHub repository name:** `bookpulse-social-booking-alerts`

## What it does

- Displays a responsive consultation and appointment-request page.
- Checks available appointment slots and prevents a slot from being accepted
  when it is already booked.
- Creates a booking and emails the visitor a short-lived verification code.
- Confirms the booking after the visitor submits the code, then attempts to
  send a Slack notification.
- Provides a staff dashboard for viewing bookings, changing their status,
  rescheduling, exporting booking data to CSV, and reviewing notification
  status.
- Captures UTM parameters and tracks clicks on links created in the dashboard.
- Includes a calendar view and an `.ics` calendar download for bookings.
- Includes sample social account, video, and metric records for local UI
  previews. These records are synthetic, not live platform data.

## How the booking flow works

1. A visitor opens `/` or `/book/` and chooses an available date and time.
2. The app saves the request with an email-verification-pending status.
3. The app sends a verification code using the configured email backend. With
   the included local configuration, the email is written to the runserver
   console instead of being sent.
4. The visitor submits the code. A successful verification confirms the
   booking and triggers a Slack notification if Slack is enabled and
   configured.
5. Staff can review and manage bookings from the dashboard.

Slack delivery is best-effort: a Slack failure does not undo a saved booking.
The notification service records delivery status for staff review.

## Technology

- Python 3.10+
- Django 4.2
- Django REST Framework
- SQLite for local development
- `requests` for Slack webhook calls
- HTML templates, CSS, and JavaScript

## Get started on Windows

Run these commands in PowerShell from the project directory. The environment
is created inside this project so it is not confused with another activated
virtual environment.

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell says script execution is disabled, use the Python executable
directly instead of activating the environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Continue the normal setup after creating `.env`:

```powershell
python -c "import sys; print(sys.executable)"
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_data
python manage.py runserver
```

The printed Python path should end with this project's
`.venv\Scripts\python.exe`. The `seed_data` step is optional; it adds synthetic
records for trying the dashboard. It does **not** create an administrator.
Create your own administrator with `createsuperuser`.

Open:

- Public booking page: `http://127.0.0.1:8000/`
- Staff dashboard: `http://127.0.0.1:8000/dashboard/`
- Django admin: `http://127.0.0.1:8000/admin/`

### macOS and Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_data
python manage.py runserver
```

## Configuration

The app loads `.env` from the project root. Start with `.env.example`; edit
your local `.env`, not the example file.

| Variable | Purpose | Local setup |
| --- | --- | --- |
| `DEBUG` | Enables Django development behavior | `True` locally; set to `False` in production |
| `SECRET_KEY` | Django signing key | Use a unique random value; never publish it |
| `ALLOWED_HOSTS` | Hosts Django accepts | Use local hosts for development and your real domain in production |
| `SLACK_ENABLED` | Enables Slack notifications | `False` until you intentionally configure a webhook |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL | Keep private; leave blank locally |
| `SLACK_NOTIFICATION_TIMEOUT` | HTTP timeout in seconds | Defaults to `15` |
| `SLACK_CHANNEL` | Channel label used in notifications | Defaults to `new-bookings` |
| `EMAIL_BACKEND` | Django email delivery backend | Console backend prints email contents in the development terminal |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` | SMTP server settings | Only needed when configuring SMTP |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP login | Store credentials only in your untracked `.env` or a secrets manager |
| `DEFAULT_FROM_EMAIL` | Sender shown on outgoing email | Use an address you control when configuring email |

Social OAuth variables are intentionally not listed: OAuth flows and live
platform connections have not been implemented.

## Useful commands

```powershell
python manage.py check
python manage.py test
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_data
python manage.py collectstatic
```

`seed_data` creates example links, example social metrics, availability rules,
and two synthetic bookings. Its displayed metrics are fabricated preview data;
do not use them as business or platform performance figures.

## Main routes

| Route | Purpose |
| --- | --- |
| `/` and `/book/` | Public booking page |
| `/api/availability/?date=YYYY-MM-DD` | Returns slots for a requested date |
| `/api/bookings/` | Creates a booking request |
| `/api/bookings/verify/` | Verifies the visitor's email code |
| `/api/bookings/resend-code/` | Requests another verification code |
| `/api/bookings/<reference>/calendar.ics` | Downloads the appointment calendar event |
| `/dashboard/login/` | Staff sign-in |
| `/dashboard/` | Staff overview |
| `/dashboard/bookings/` | Booking search and management |
| `/dashboard/calendar/` | Appointment calendar |
| `/dashboard/tracked-links/` | UTM tracked-link management |
| `/dashboard/analytics/` | Social metrics preview |
| `/admin/` | Django's built-in administration |

## Project layout

```text
config/                 Django settings and URL routing
apps/bookings/          Booking, availability, and appointment services
apps/notifications/     Email and Slack notification services
apps/analytics/         Attribution, tracked links, and social metric models
apps/dashboard/         Staff dashboard views and routes
templates/              Public pages and dashboard templates
static/                 Project CSS and JavaScript
requirements.txt        Python dependencies
.env.example            Safe local-configuration template
```

## Current scope and limitations

This repository is a working prototype, not a finished production service.

- YouTube, Instagram, and TikTok OAuth are not implemented.
- The social dashboard uses database records; the “sync” action does not fetch
  metrics from the platforms. Seeded metrics are illustrative only.
- Local development uses SQLite. Production database and deployment settings
  have not been configured.
- The included email backend writes messages to the console. Real email
  delivery requires an SMTP provider and private credentials.
- Availability and booking behavior need operational review before accepting
  real appointments.
- Review authentication, access control, rate limiting, privacy/consent,
  backups, logging, and deployment security before handling real personal
  information.

Do not treat the dashboard's sample figures as real analytics, and do not
deploy with `DEBUG=True` or the example secret key.

## Protecting private information before publishing

The repository is **not currently initialized as a Git repository**, and no
GitHub upload is performed by these instructions. Before making a repository
public:

1. **Check client permission.** This project currently contains
   Renowned Homes-specific branding, business copy, and contact details in
   settings, templates, and notification code. Confirm you have permission to
   publish them. If not, replace or remove them throughout the project before
   publishing; changing only this README is not enough.
2. Never commit `.env`, `db.sqlite3`, `.venv/`, `staticfiles/`, uploaded media,
   exported CSVs, logs, credentials, webhook URLs, OAuth secrets, or customer
   records. The `.gitignore` is configured to exclude common local files, but
   still review every file you stage.
3. Do not commit logos, photos, fonts, or other assets unless you own them or
   have a license that permits redistribution.
4. Review the complete staged diff before pushing. If a secret was ever
   committed, removing the file is not enough: revoke or rotate the credential
   and remove it from Git history.

After creating a Git repository locally, verify that private local files are
ignored:

```powershell
git check-ignore -v .env db.sqlite3 .venv staticfiles
git status --short
```

For a public project, use the suggested repository slug
`bookpulse-social-booking-alerts`. GitHub profile:
[@muhammadwasim92logics](https://github.com/muhammadwasim92logics).

## Contributing

1. Create and activate a virtual environment.
2. Install dependencies and configure a local `.env`.
3. Run migrations and tests before opening a pull request.
4. Use synthetic data only in tests and examples; do not add real customer
   information or credentials.

## License

No license is currently included. Add a license only after confirming that
you have the rights to publish the application code, branding, and included
assets. Without a license, normal copyright restrictions apply.
