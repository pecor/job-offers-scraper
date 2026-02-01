# Job Offers Scraper

Scraper ofert pracy z różnych portali (pracuj.pl, justjoin.it) z możliwością filtrowania i zapisu do bazy danych PostgreSQL. GUI w Next.js z Material-UI pozwalające na otwieranie wybranych ofert w nowym oknie.

## Architektura

- **Frontend**: Next.js 14 z Material-UI (MUI) i Tailwind CSS
- **Backend**: FastAPI
- **Baza danych**: PostgreSQL
- **Task processing**: FastAPI BackgroundTasks

## Funkcjonalności

- Scraping ofert z wielu portali (pracuj.pl, justjoin.it)
- Filtrowanie ofert po technologiach (włącznie z wykluczaniem niepożądanych)
- Filtrowanie po słowach kluczowych (wymagane i wykluczone)
- Zapis do bazy danych PostgreSQL
- Nowoczesne GUI w Next.js z Material-UI
- Automatyczne wykrywanie duplikatów
- Sortowanie ofert
- Ekstrakcja: tytuł, firma, lokalizacja, opis, technologie, wynagrodzenie, wymiar pracy
- Eksport/import do csv lub json
- Zaznaczenie ofert jako wyświetlone

## Instalacja

### Docker (zalecane)

1. Skopiuj plik `.env.example` do `.env` i uzupełnij dane:

```bash
cp .env.example .env
```

2. Uruchom wszystkie serwisy:

```bash
docker-compose up
```

Aplikacja będzie dostępna pod adresami:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- PostgreSQL: http://localhost:5432

### Konfiguracja scrapera

Parametry wyszukiwania można skonfigurować przez GUI lub plik `config/config.json`:

```json
{
  "search_keyword": "junior",
  "max_pages": 5,
  "delay": 1.0,
  "excluded_keywords": ["konsultant", "administrator sieci"],
  "schedule": "daily",
  "sources": ["pracuj_pl", "justjoin_it"]
}
```

## Użycie

1. **GUI**: Otwórz http://localhost:3000 w przeglądarce
2. Kliknij ikonę ustawień, aby skonfigurować scraper
3. Wybierz źródła, słowo kluczowe i inne parametry
4. Kliknij "Uruchom scraper" aby rozpocząć scraping
5. Użyj filtrów do przeglądania ofert
6. Zaznacz oferty i otwórz je w nowych kartach (jeśli otwiera się tylko jedna karta to trzeba zezwolić na pop-upy)

## Licencja

MIT
