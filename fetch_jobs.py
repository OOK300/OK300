"""OK300: fetch public HH vacancies, preserving prior data on source failures."""
import datetime
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
OUTPUT = ROOT / "vacancies.json"
QUERIES = [
    "коммерческий директор",
    "операционный директор",
    "директор по развитию",
    "директор по продажам",
    "директор по клиентскому сервису",
    "руководитель клиентского опыта",
    "директор по партнерствам",
]

items = {}
successful_requests = 0
failed_requests = 0
for query in QUERIES:
    params = urllib.parse.urlencode({
        "text": query, "area": 113, "per_page": 100,
        "page": 0, "order_by": "publication_time",
    })
    request = urllib.request.Request(
        "https://api.hh.ru/vacancies?" + params,
        headers={
            "User-Agent": "OK300VacancyTracker/1.0 (personal project)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.load(response)
        successful_requests += 1
    except urllib.error.HTTPError as error:
        failed_requests += 1
        print(f"HH API HTTP {error.code} for '{query}'. Source refused request.")
        continue
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        failed_requests += 1
        print(f"HH API error for '{query}': {error}")
        continue

    for vacancy in data.get("items", []):
        salary = vacancy.get("salary") or {}
        minimum = salary.get("from")
        maximum = salary.get("to")
        amount = minimum or maximum
        if salary.get("currency") != "RUR" or not amount or amount < 250000:
            continue
        schedule = vacancy.get("schedule") or {}
        if schedule.get("id") != "remote":
            continue
        url = vacancy.get("alternate_url")
        if not url:
            continue
        vacancy_id = str(vacancy["id"])
        items[vacancy_id] = {
            "id": vacancy_id,
            "title": vacancy.get("name", ""),
            "company": (vacancy.get("employer") or {}).get("name", ""),
            "pay": amount,
            "salary_from": minimum,
            "salary_to": maximum,
            "work": "remote",
            "location": (vacancy.get("area") or {}).get("name", ""),
            "url": url,
            "published": vacancy.get("published_at", ""),
            "source": "hh.ru",
        }
    time.sleep(0.4)

print(f"Requests: {successful_requests} successful, {failed_requests} failed; {len(items)} matching jobs")
if successful_requests == 0:
    print("WARNING: all HH API requests failed; preserving previous data.")
    if not OUTPUT.exists():
        OUTPUT.write_text(
            json.dumps({"updated_at": None, "jobs": []}, ensure_ascii=False),
            encoding="utf-8",
        )
    raise SystemExit(1)

if not items:
    print("No matching vacancies; preserving previous data.")
    if not OUTPUT.exists():
        OUTPUT.write_text(
            json.dumps({"updated_at": None, "jobs": []}, ensure_ascii=False),
            encoding="utf-8",
        )
    raise SystemExit(0)

output = {
    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "jobs": sorted(items.values(), key=lambda item: item["published"], reverse=True),
}
OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved {len(items)} vacancies")
