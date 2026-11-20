"""Connectors for external job discovery and detail extraction.

Integrates:
- Google Serper API search for Greenhouse boards (get_links.py & step1.py)
- Greenhouse public posting detail extraction (step2.py)
- Internshala public internship scraper (intershala.py)
- LinkedIn public jobs guest API (scrape_linkedin.py)
"""
import json
import logging
import re
import time
from typing import List, Dict, Any, Optional
from urllib.parse import urlsplit
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:  # keep the app importable; the connectors report a clear message when they are used
    BeautifulSoup = None

from .config import (
    SERPER_API_KEY,
    SERPER_SEARCH_URL,
    DEFAULT_HEADERS,
    REQUEST_TIMEOUT,
    RATE_LIMIT_DELAY,
)

logger = logging.getLogger(__name__)

GREENHOUSE_HOSTS = frozenset({"boards.greenhouse.io", "job-boards.greenhouse.io"})


def _is_allowed_greenhouse_url(url: str) -> bool:
    try:
        parsed = urlsplit(str(url).strip())
        return (
            parsed.scheme.lower() == "https"
            and parsed.hostname is not None
            and parsed.hostname.lower() in GREENHOUSE_HOSTS
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


def _soup(html: str):
    if BeautifulSoup is None:
        raise RuntimeError("beautifulsoup4 is not installed (run: pip install -r backend/requirements.txt)")
    return BeautifulSoup(html, "html.parser")


class SerperGreenhouseConnector:
    """Discovers Greenhouse job listings via Serper Google Search API and extracts job details."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or SERPER_API_KEY

    def search_links(self, query: str = 'site:boards.greenhouse.io "intern" "India"', count: int = 15) -> List[Dict[str, str]]:
        if not self.api_key:
            logger.info("SERPER_API_KEY is not configured; Serper discovery is unavailable.")
            return []

        payload = json.dumps({"q": query, "gl": "in", "num": count})
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            res = requests.post(SERPER_SEARCH_URL, headers=headers, data=payload, timeout=REQUEST_TIMEOUT)
            if res.status_code == 200:
                results = res.json()
                links = []
                for item in results.get("organic", []):
                    link = item.get("link", "")
                    if _is_allowed_greenhouse_url(link):
                        links.append({
                            "title": item.get("title", ""),
                            "link": link,
                            "snippet": item.get("snippet", ""),
                        })
                return links
            else:
                logger.warning(f"Serper API returned {res.status_code}: {res.text}")
                return []
        except Exception as e:
            logger.error(f"Error querying Serper API: {e}")
            return []

    def extract_details(self, title: str, url: str) -> Dict[str, Any]:
        """Fetches public Greenhouse posting and extracts structured fields (step2.py)."""
        if not _is_allowed_greenhouse_url(url):
            raise ValueError("Greenhouse detail URL must use an allowed HTTPS host.")

        location = "India"
        duration = "3-6 months"
        company = "Greenhouse Employer"
        description = ""

        # Extract company name from URL subdomain or path if boards.greenhouse.io/<company>/jobs/...
        m = re.search(r"boards\.greenhouse\.io/([^/]+)", url)
        if m:
            raw_co = m.group(1).replace("-", " ").title()
            company = raw_co

        try:
            res = requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=False)
            if res.status_code == 200:
                soup = _soup(res.text)
                # Location extraction
                loc_tag = soup.find(class_=re.compile("location", re.I))
                if loc_tag:
                    location = loc_tag.get_text(strip=True)

                # Company name from heading or meta
                heading = soup.find("span", class_="company-name") or soup.find(class_=re.compile("app-title", re.I))
                if heading and heading.get_text(strip=True):
                    company = heading.get_text(strip=True)

                # Description
                content = soup.find(id="content") or soup.find("div", class_=re.compile("job-description", re.I))
                if content:
                    description = content.get_text(" ", strip=True)[:1500]

                # Duration search
                full_text = soup.get_text(" ", strip=True)
                dur_match = re.search(r"(\d+\s*(?:to|-|–)?\s*\d*\s*months?)", full_text, re.I)
                if dur_match:
                    duration = dur_match.group(1)
        except Exception as e:
            logger.debug(f"Detail fetch failed for {url}: {e}")

        return {
            "title": title or "Internship Opportunity",
            "company": company,
            "location": location,
            "duration": duration,
            "stipend": "As per company policy",
            "source_url": url,
            "source": "Greenhouse",
            "job_type": "Internship",
            "work_mode": "Hybrid" if "hybrid" in description.lower() else "Remote" if "remote" in description.lower() else "On-site",
            "description": description or f"Opportunity listed on {company} career portal.",
            "from_verified_ats": True,
        }


class InternshalaConnector:
    """Collects publicly visible internship information from Internshala (intershala.py)."""

    def fetch_listings(self, max_pages: int = 2) -> List[Dict[str, Any]]:
        base_url = "https://internshala.com"
        results = []

        for page in range(1, max_pages + 1):
            url = f"{base_url}/internships/page-{page}/"
            try:
                res = requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
                if res.status_code != 200:
                    break

                soup = _soup(res.text)
                cards = soup.find_all("div", class_=re.compile("individual_internship"))
                for card in cards:
                    title_tag = card.find("a", class_=re.compile("job-title"))
                    company_tag = card.find("p", class_=re.compile("company-name")) or card.find("div", class_=re.compile("company"))
                    loc_tag = card.find("div", id=re.compile("location")) or card.find("span", class_=re.compile("location"))
                    stipend_tag = card.find("span", class_=re.compile("stipend"))

                    if title_tag:
                        role = title_tag.get_text(strip=True)
                        href = title_tag.get("href", "")
                        link = href if href.startswith("http") else (base_url + href)
                        co = company_tag.get_text(strip=True) if company_tag else "Internshala Partner"
                        loc = loc_tag.get_text(strip=True) if loc_tag else "India"
                        stipend = stipend_tag.get_text(strip=True) if stipend_tag else "Unpaid / Not specified"

                        results.append({
                            "title": role,
                            "company": co,
                            "location": loc,
                            "duration": "3-6 Months",
                            "stipend": stipend,
                            "source_url": link,
                            "source": "Internshala",
                            "job_type": "Internship",
                            "work_mode": "Remote" if "work from home" in loc.lower() or "remote" in loc.lower() else "On-site",
                            "description": f"Internship for {role} at {co}. Location: {loc}. Stipend: {stipend}.",
                        })

                time.sleep(RATE_LIMIT_DELAY)
            except Exception as e:
                logger.warning(f"Internshala fetch exception: {e}")
                break

        return results


class LinkedInGuestConnector:
    """Collects public jobs from LinkedIn's guest jobs endpoint (scrape_linkedin.py)."""

    def fetch_listings(self, count: int = 15) -> List[Dict[str, Any]]:
        url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=intern&location=India&start=0"
        results = []

        try:
            res = requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
            if res.status_code == 200:
                soup = _soup(res.text)
                jobs = soup.find_all("li")
                for job in jobs[:count]:
                    title_tag = job.find("h3", class_=re.compile("title"))
                    company_tag = job.find("h4", class_=re.compile("subtitle"))
                    loc_tag = job.find("span", class_=re.compile("location"))
                    link_tag = job.find("a", class_=re.compile("link"))

                    if title_tag and link_tag:
                        role = title_tag.get_text(strip=True)
                        co = company_tag.get_text(strip=True) if company_tag else "LinkedIn Recruiter"
                        loc = loc_tag.get_text(strip=True) if loc_tag else "India"
                        raw_link = link_tag.get("href", "")
                        link = raw_link.split("?")[0] if raw_link else "https://www.linkedin.com/jobs"

                        results.append({
                            "title": role,
                            "company": co,
                            "location": loc,
                            "duration": "6 Months",
                            "stipend": "Competitive",
                            "source_url": link,
                            "source": "LinkedIn",
                            "job_type": "Internship",
                            "work_mode": "Hybrid" if "hybrid" in loc.lower() else "On-site",
                            "description": f"Public job opening for {role} at {co} ({loc}) published on LinkedIn.",
                        })
            else:
                logger.info(f"LinkedIn public API returned status {res.status_code} (rate-limiting safe skip).")
        except Exception as e:
            logger.warning(f"LinkedIn guest fetch exception: {e}")

        return results
