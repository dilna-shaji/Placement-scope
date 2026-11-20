import csv
import json
import requests

url = "https://serper.dev"

payload = json.dumps({
    "q": 'site:boards.greenhouse.io "intern" "India"',
    "gl": "in",
    "num": 20,
})
headers = {
    "X-API-KEY": "ce2ec8eb979bc19ac560e117996d2327e55aaee8",
    "Content-Type": "application/json",
}

res = requests.post(url, headers=headers, data=payload, timeout=15)
print("STATUS CODE:", res.status_code)

if res.status_code == 200:
  results = res.json()
  with open("internship_links.csv", "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["Job Title", "Website Link"])
    for item in results.get("organic", []):
      writer.writerow([item.get("title"), item.get("link")])
  print("Success! Saved links to internship_links.csv")
else:
  print("Error:", res.text)
