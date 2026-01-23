# Job Offers Scraper

Scraper ofert pracy z różnych portali (pracuj.pl, justjoin.it, LinkedIn itp.) z możliwością filtrowania i zapisu do bazy danych SQLite. GUI pozwalające na otwieranie wybranych ofert w nowym oknie.

## Funkcjonalności

- Scraping ofert z wielu portali
- Filtrowanie ofert po technologiach (włącznie z wykluczaniem niepożądanych)
- Zapis do bazy danych SQLite
- GUI do konfiguracji parametrów wyszukiwania
- Tryby: daily, weekly, manual
- Automatyczne wykrywanie duplikatów (po linkach)
- Sortowanie od najnowszych
- Ekstrakcja: tytuł, firma, lokalizacja, opis, technologie, wynagrodzenie, wymiar pracy

## Instalacja

### Docker (zalecane)

```bash
docker-compose up
```

Aplikacja uruchomi się w trybie CLI. Aby uruchomić GUI lokalnie, użyj:

```bash
python main.py
```

lub

```bash
python main.py --gui
```

### Lokalnie

```bash
# Zainstaluj zależności
pip install -r requirements.txt

# Uruchom z GUI (domyślnie)
python main.py

# Uruchom w trybie CLI
python main.py --cli
```

## Konfiguracja

Parametry wyszukiwania można skonfigurować przez GUI lub plik `config/config.json`:

```json
{
  "search_keyword": "junior",
  "max_pages": 5,
  "delay": 1.0,
  "excluded_keywords": ["konsultant", "administrator sieci"],
  "schedule": "daily",
  "sources": ["pracuj_pl"]
}
```

## Użycie

1. **GUI Mode**: Uruchom `python main.py` i użyj interfejsu graficznego do konfiguracji i uruchomienia scrapera
2. **CLI Mode**: Uruchom `python main.py --cli` dla automatycznego uruchomienia z domyślną konfiguracją

## Baza danych

Baza danych SQLite jest automatycznie tworzona w `data/job_offers.db`. Zawiera następujące pola:
- url (unikalny)
- title
- company
- location
- description
- technologies
- salary_min, salary_max, salary_period
- work_type (remote/hybrid/on-site)
- contract_type (UoP/B2B/UZ/UoD)
- source
- scraped_at, created_at

## Licencja

MIT