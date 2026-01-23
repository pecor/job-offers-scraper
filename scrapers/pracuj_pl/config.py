# URL configuration
BASE_URL = "https://it.pracuj.pl"
SEARCH_URL = "https://it.pracuj.pl/praca/{keyword};kw"

# HTML selectors
SELECTORS = {
    'offer_link': {'data-test': 'link-offer'},
    'company_link': {'data-test': 'link-company-profile'},
    'company_alt': lambda x: x and 'company' in x.lower(),
    'location': [
        {'data-test': lambda x: x and 'location' in x.lower()},
        {'class': lambda x: x and 'location' in x.lower()},
    ],
    'work_place': [
        {'text': lambda x: x and 'miejsce pracy' in x.lower()},
    ],
    'description_sections': [
        'O projekcie',
        'Twój zakres obowiązków',
        'Nasze wymagania',
        'Oferujemy',
    ],
}

# Keywords for extraction
WORK_TYPE_KEYWORDS = {
    'remote': ['praca zdalna', 'zdalnie', 'remote', 'home office', 'praca w pełni zdalna'],
    'hybrid': ['praca hybrydowa', 'hybrydowo', 'hybrid', 'częściowo zdalnie'],
    'on-site': ['praca stacjonarna', 'stacjonarnie', 'on-site', 'biuro', 'w biurze'],
}

CONTRACT_TYPE_KEYWORDS = {
    'UoP': ['umowa o pracę', 'uop'],
    'B2B': ['b2b', 'umowa b2b', 'kontrakt b2b'],
    'UZ': ['umowa zlecenie', 'uz'],
    'UoD': ['umowa o dzieło', 'uod'],
}

# Text to remove from description
DESCRIPTION_REMOVE_PATTERNS = [
    'Przejdź do treści ogłoszenia',
    'Przejdź do panelu aplikowania',
    'Przejdź do panelu bocznego',
    'Przejdź do stopki',
    'Niestety, nie wspieramy Twojej przeglądarki',
    'Niestety nie wspieramy Twojej przeglądarki',
    'co może znacznie wpłynąć na poprawne ładowanie skryptów strony',
    'Oferty pracy',
    'Pобота',
    'Profile pracodawców',
    'Porady i narzędzia',
    'Wybrano język polski',
    'Moje konto',
    'Dla firm',
    'Dodaj ogłoszenie',
    'Nowość',
    'Zapisz',
    'Sprawdź jak dojechać',
    'Asystent Pracuj.pl',
    'Podsumowanie oferty',
    'Wypróbuj nową funkcję',
    'Pokaż podsumowanie',
    'Dodatkowe informacje',
    'Specjalizacje:',
    'Siedziba firmy',
    'Technologie, których używamy',
    'Wymagane',
    'Mile widziane',
]

# Regex patterns to remove metadata from description
DESCRIPTION_REMOVE_REGEX = [
    r'valid for.*?\)',  # "valid for over a month(to 21 Feb)"
    r'ważna jeszcze.*?\)',  # "ważna jeszcze miesiąc(do 19 lut)"
    r'ważna jeszcze ponad.*?\)',  # "ważna jeszcze ponad miesiąc(do 21 lut)"
    r'ważna.*?dni\(',  # "ważna 21 dni(to 11 Feb)"
    r'[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+ \d+[a-z]?[,]? [A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+.*?\([^)]+\)',  # Addresses like "Legnicka 48f, Fabryczna, Wrocław(Lower Silesia)"
    r'contract of employment.*?junior',  # "contract of employment junior specialist (Junior)"
    r'umowa o pracę.*?junior',  # "umowa o pracę, kontrakt B2B junior"
    r'junior specialist.*?\(Junior\)',  # "junior specialist (Junior)"
    r'młodszy specjalista.*?\(Junior\)',  # "młodszy specjalista (Junior)"
    r'Specializations?:.*?(?=\n|$)',  # "Specializations:DevOps"
    r'języki?:.*?(?=\n|$)',  # "języki:angielski"
    r'Запрошуємо працівників з України',  # Ukrainian text
]