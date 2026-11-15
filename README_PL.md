# UPTMON – Monitor dostępności stron internetowych

Lekki i wydajny system do monitorowania dostępności stron internetowych, stworzony w Pythonie z wykorzystaniem FastAPI.

UPTMON umożliwia sprawdzanie dostępności stron, mierzenie czasu odpowiedzi serwerów oraz otrzymywanie powiadomień w przypadku awarii lub przywrócenia działania monitorowanej usługi.

Projekt zawiera responsywny panel internetowy, automatyczny mechanizm sprawdzania stron oraz system powiadomień oparty na webhookach.

## Funkcje

- Monitorowanie dostępności stron internetowych.
- Automatyczne sprawdzanie stron co 60 sekund.
- Pomiar czasu odpowiedzi serwera.
- Responsywny panel zarządzania monitorami.
- Historia sprawdzeń zapisywana w bazie danych.
- Powiadomienia webhook w przypadku awarii i przywrócenia działania strony.
- Asynchroniczne zapytania HTTP z wykorzystaniem HTTPX.

## Wykorzystane technologie

- **Python** – główny język programowania.
- **FastAPI** – framework do budowy aplikacji webowych i API.
- **SQLAlchemy** – ORM do obsługi bazy danych.
- **SQLite** – relacyjna baza danych.
- **APScheduler** – harmonogram zadań wykonywanych w tle.
- **HTTPX** – asynchroniczny klient HTTP.
- **Pydantic** – walidacja danych.
- **Uvicorn** – serwer ASGI.
- **Webhooks** – system powiadomień.

## Struktura projektu

```text
UPTMON/
├── app/
│   ├── checker.py      # Sprawdzanie stron i wysyłanie powiadomień
│   ├── database.py     # Konfiguracja bazy danych i sesji
│   ├── main.py         # Aplikacja FastAPI, API i panel
│   ├── models.py       # Modele bazy danych
│   ├── run.py          # Plik uruchamiający aplikację
│   └── schemas.py      # Schematy walidacji Pydantic
├── .gitignore
└── requirements.txt
```

## Instalacja

### 1. Sklonuj repozytorium

```bash
git clone https://github.com/HassanAlbe/UPTMON.git
cd UPTMON
```

### 2. Utwórz środowisko wirtualne

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

### 3. Zainstaluj zależności

```bash
pip install -r requirements.txt
```

### 4. Uruchom aplikację

```bash
python app/run.py
```

### 5. Otwórz panel

Po uruchomieniu serwera przejdź w przeglądarce pod adres:

http://127.0.0.1:8000

## Jak działa UPTMON?

1. Dodajesz adres strony internetowej, którą chcesz monitorować.
2. System automatycznie sprawdza jej dostępność co 60 sekund.
3. Aplikacja mierzy czas odpowiedzi i analizuje status HTTP.
4. Wyniki sprawdzeń są zapisywane w bazie SQLite.
5. W przypadku awarii lub przywrócenia działania strony wysyłane jest powiadomienie webhook.
6. Wszystkie monitory i ich historię możesz przeglądać w panelu internetowym.

## Powiadomienia

UPTMON obsługuje powiadomienia oparte na webhookach.

System może wysyłać informacje o:

- Niedostępności monitorowanej strony.
- Ponownym uruchomieniu strony po awarii.

Przykładową integracją jest Discord.

## Baza danych

Do przechowywania danych wykorzystywane są SQLite oraz SQLAlchemy.

Baza zawiera informacje o:

- Monitorowanych stronach internetowych.
- Aktualnym statusie dostępności.
- Czasach odpowiedzi.
- Historii przeprowadzonych sprawdzeń.

## Licencja

Informacje o licencji zostaną dodane w przyszłości.

---

Projekt stworzony w Pythonie z wykorzystaniem FastAPI.
