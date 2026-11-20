"""Configuration for job aggregation pipeline and source connectors."""
import os

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_SEARCH_URL = "https://google.serper.dev/search"

# Default queries for Greenhouse internships in India
DEFAULT_GREENHOUSE_QUERY = 'site:boards.greenhouse.io "intern" "India"'
DEFAULT_INTERNSHALA_BASE = "https://internshala.com"
DEFAULT_LINKEDIN_ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

REQUEST_TIMEOUT = 15  # seconds
RATE_LIMIT_DELAY = 1.0  # seconds between outbound requests
