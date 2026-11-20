import csv
import time
from bs4 import BeautifulSoup
import requests

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
}

sep = chr(58) + chr(47) + chr(47)
domain = "www." + "linkedin." + "com"
path = (
    "/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=intern&location=India&start="
)

with open("linkedin_jobs.csv", "w", newline="", encoding="utf-8") as f:
  writer = csv.writer(f)
  writer.writerow(["Role", "Company", "Location", "Posted", "Link"])
  total_saved = 0

  for start in (0, 25, 50):
    url = "https" + sep + domain + path + str(start)
    print("Fetching:", url)

    res = requests.get(url, headers=headers, timeout=15)
    print("STATUS:", res.status_code)

    if res.status_code != 200:
      print("Rate limited by LinkedIn—stopping early to stay safe.")
      break

    soup = BeautifulSoup(res.text, "html.parser")
    jobs = soup.find_all("li")

    for job in jobs:
      title_tag = job.find("h3", class_="base-search-card__title")
      company_tag = job.find("h4", class_="base-search-card__subtitle")
      loc_tag = job.find("span", class_="job-search-card__location")
      time_tag = job.find("time")
      link_tag = job.find("a", class_="base-card__full-link")

      if title_tag and link_tag:
        role = title_tag.get_text(strip=True)
        company = company_tag.get_text(strip=True) if company_tag else "N/A"
        location = loc_tag.get_text(strip=True) if loc_tag else "N/A"
        posted = time_tag.get_text(strip=True) if time_tag else "N/A"
        raw_link = link_tag.get("href", "")
        link = raw_link.split("?")[0] if raw_link else "N/A"

        writer.writerow([role, company, location, posted, link])
        total_saved += 1

    time.sleep(3)

print(f"Done! Saved {total_saved} LinkedIn internships to linkedin_jobs.csv")
