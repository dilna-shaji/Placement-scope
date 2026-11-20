import csv
import time
from bs4 import BeautifulSoup
import requests

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
}

base_url = "https://" + "internshala.com"

with open("internshala_jobs.csv", "w", newline="", encoding="utf-8") as f:
  writer = csv.writer(f)
  writer.writerow(["Role", "Company", "Location", "Duration", "Stipend", "Link"])
  total_saved = 0

  for page in range(1, 4):
    url = base_url + "/internships" + "/page-" + str(page) + "/"
    print("Fetching:", url)

    res = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    cards = soup.find_all("div", class_="individual_internship")

    for card in cards:
      title_tag = card.find("a", class_="job-title-href")
      company_tag = card.find("p", class_="company-name")
      loc_tag = card.find("div", id="location_names")
      stipend_tag = card.find("span", class_="stipend")

      details = card.find_all("div", class_="item_body")
      duration = "N/A"
      for d in details:
        text = d.get_text(strip=True)
        if "Month" in text or "Week" in text:
          duration = text
          break

      if title_tag:
        role = title_tag.get_text(strip=True)
        link = base_url + title_tag.get("href", "")
        company = company_tag.get_text(strip=True) if company_tag else "N/A"
        location = loc_tag.get_text(strip=True) if loc_tag else "N/A"
        stipend = stipend_tag.get_text(strip=True) if stipend_tag else "N/A"

        writer.writerow([role, company, location, duration, stipend, link])
        total_saved += 1

    time.sleep(2)

print(f"Done! Saved {total_saved} internships to internshala_jobs.csv")
