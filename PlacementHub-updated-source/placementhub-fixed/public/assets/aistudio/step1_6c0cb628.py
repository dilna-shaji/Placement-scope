import csv
import json
import requests

url = "https://" + "google." + "serper.dev" + "/search"

payload = json.dumps({
    "q": "greenhouse intern jobs India",
    "gl": "in",
    "num": 30,
})
headers = {
    "X-API-KEY": "ce2ec8eb979bc19ac560e117996d2327e55aaee8",
    "Content-Type": "application/json",
}

res = requests.post(url, headers=headers, data=payload, timeout=30)
print("STATUS CODE:", res.status_code)

if res.status_code == 200:
  results = res.json()
  with open("internship_links.csv", "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["Job Title", "Website Link"])
    count = 0
    for item in results.get("organic", []):
      link = item.get("link", "")
      if "greenhouse" in link:
        writer.writerow([item.get("title"), link])
        count += 1
  print(f"Success! Saved {count} Greenhouse links to internship_links.csv")
else:
  print("Error:", res.text)

