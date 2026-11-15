# UPTMON – Uptime Monitor

A lightweight website uptime monitoring application built with Python and FastAPI.

UPTMON allows you to monitor website availability, track response times, and receive notifications when a monitored service goes offline or becomes available again.

The project includes a responsive web dashboard, automated monitoring, and webhook notifications.

## Features

- Website availability monitoring.
- Automatic checks every 60 seconds.
- Response time measurement.
- Responsive web dashboard.
- Monitoring history stored in a database.
- Webhook notifications when a website goes down or recovers.
- Asynchronous HTTP requests using HTTPX.

## Technologies

- **Python** – Core programming language.
- **FastAPI** – Web framework.
- **SQLAlchemy** – Database ORM.
- **SQLite** – Database.
- **APScheduler** – Background task scheduling.
- **HTTPX** – Asynchronous HTTP client.
- **Pydantic** – Data validation.
- **Uvicorn** – ASGI server.
- **Webhooks** – Notifications.

## Project Structure

```text
UPTMON/
├── app/
│   ├── checker.py      # Website checks and webhook notifications
│   ├── database.py     # Database configuration and sessions
│   ├── main.py         # FastAPI application, API and dashboard
│   ├── models.py       # Database models
│   ├── run.py          # Application entry point
│   └── schemas.py      # Pydantic schemas
├── .gitignore
└── requirements.txt
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/HassanAlbe/UPTMON.git
cd UPTMON
```

### 2. Create a virtual environment

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the application

```bash
python app/run.py
```

### 5. Open the dashboard

Visit the following address in your browser:

http://127.0.0.1:8000

## How It Works

1. Add a website URL to the monitoring system.
2. UPTMON automatically checks the website every 60 seconds.
3. The application measures response time and checks availability.
4. Check results are saved in the SQLite database.
5. Webhook notifications are sent when a website goes offline or comes back online.
6. Monitor your websites through the web dashboard.

## Notifications

UPTMON supports webhook notifications, allowing you to receive alerts when a monitored website changes its availability status.

For example, notifications can be sent to a Discord channel.

## Database

SQLite and SQLAlchemy are used to store:

- Monitored websites.
- Website availability status.
- Response times.
- Monitoring history.

## License

License information will be added later.

---

Built with Python and FastAPI.
