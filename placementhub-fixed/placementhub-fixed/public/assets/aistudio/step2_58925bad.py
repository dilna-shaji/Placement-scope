import csv
import re
import time
from bs4 import BeautifulSoup
import requests

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
}

with open("internship_links.csv", "r", encoding="utf-8") as infile:
  reader = csv.DictReader(infile)
  rows = list(reader)

with open(
    "internships_final.csv", "w", newline="", encoding="utf-8"
) as outfile:
  writer = csv.writer(outfile)
  writer.writerow(["Job Title", "City / Location", "Duration", "Website Link"])

  for row in rows:
    title = row["Job Title"]
    link = row["Website Link"]
    print(f"Checking: {title}")

    try:
      res = requests.get(link, headers=headers, timeout=15)
      soup = BeautifulSoup(res.text, "html.parser")

      # Extract Location / City
      loc_tag = soup.find(class_=re.compile("location", re.I))
      city = loc_tag.get_text(strip=True) if loc_tag else "Not listed"

      # Extract Duration (e.g., "6 months", "3-6 months")
      full_text = soup.get_text(" ", strip=True)
      dur_match = re.search(
          r"(\d+\s*(?:to|-|–)?\s*\d*\s*months?)", full_text, re.I
      )
      duration = dur_match.group(1) if dur_match else "Not specified"

      writer.writerow([title, city, duration, link])
    except Exception as e:
      writer.writerow([title, "Error fetching", "Error fetching", link])

    time.sleep(1)

print("Done! Open internships_final.csv to view your results.")
