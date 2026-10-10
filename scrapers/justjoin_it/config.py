# API configuration
# Listing and details go through the justjoin.it reverse proxy (api.justjoin.it
# rejects direct requests with 503). Verified 2026-10.
API_BASE_URL = "https://justjoin.it/api/candidate-api/offers"
OFFER_BASE_URL = "https://justjoin.it/job-offer"

# Default API parameters
DEFAULT_PARAMS = {
    'cityRadiusKm': 30,  # not really important
    'currency': 'pln',
    'from': 0,
    'itemsCount': 100,
    'orderBy': 'Descending',
    'sortBy': 'Newest',
}
