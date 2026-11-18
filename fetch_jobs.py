"""OK300 vacancy collector: public RSS feeds, no authentication or scraping bypass.

Keeps the previous dataset if all sources fail or return no matching jobs.
"""
import datetime as dt
import email.utils
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent
OUTPUT = ROOT / 'vacancies.json'
QUERIES = [
    'коммерческий директор', 'операционный директор', 'директор по развитию',
    'директор по продажам', 'директор по клиентскому сервису',
    'руководитель клиентского опыта', 'директор по партнерствам',
]
MIN_SALARY = 250_000
UA = 'OK300/1.1 (personal job search; contact: ok300@bk.ru)'


def clean(text):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', ' ', text or '')).strip()


def salary_from_text(text):
    """Conservative extraction: require an explicit RUB amount >= threshold."""
    s = clean(text).replace('\xa0', ' ')
    # 'от 300 000 ₽', '300 000 руб', '300 тыс. рублей'
    pattern = r'(\d{2,3}(?:[\s\u202f]\d{3})?|\d{2,3})\s*(тыс\.?|тысяч)?\s*(₽|руб(?:лей|ля|\.)?|RUB)'
    values = []
    for m in re.finditer(pattern, s, re.I):
        value = int(re.sub(r'\D', '', m.group(1)))
        if m.group(2):
            value *= 1000
        if 100_000 <= value <= 10_000_000:
            values.append(value)
    return min(values) if values else None


def get_feed(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/rss+xml, application/xml, text/xml'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return ET.fromstring(response.read(3_000_000))


def parse_feed(root, source):
    for item in root.findall('.//item'):
        title = clean(item.findtext('title', ''))
        link = (item.findtext('link', '') or '').strip()
        desc = clean(item.findtext('description', ''))
        pub = item.findtext('pubDate', '') or ''
        if not title or not link.startswith('https://'):
            continue
        combined = title + ' ' + desc
        pay = salary_from_text(combined)
        if pay is None or pay < MIN_SALARY:
            continue
        # Do not mislabel an unknown format as remote.
        if not re.search(r'удал[её]нн|remote|работа из дома|дистанционн', combined, re.I):
            continue
        if re.search(r'без оклада|только процент|холодные звонки|удержание клиентов', combined, re.I):
            continue
        try:
            published = email.utils.parsedate_to_datetime(pub).astimezone(dt.timezone.utc).isoformat()
        except (ValueError, TypeError, IndexError):
            published = ''
        identifier = re.sub(r'[^a-zA-Z0-9_-]', '', link.rsplit('/', 1)[-1].split('?', 1)[0]) or str(abs(hash(link)))
        yield {
            'id': source + '-' + identifier, 'title': title,
            'company': '', 'pay': pay, 'salary_from': pay, 'salary_to': None,
            'work': 'remote', 'location': 'Россия', 'url': link,
            'published': published, 'source': source,
            'notes': 'Формат и зарплата извлечены из RSS; проверьте условия на сайте работодателя.',
        }


def main():
    previous = []
    if OUTPUT.exists():
        try:
            previous = json.loads(OUTPUT.read_text(encoding='utf-8')).get('jobs', [])
        except (ValueError, OSError):
            pass
    jobs = {j['url']: j for j in previous if isinstance(j, dict) and j.get('url')}
    success = 0
    errors = 0
    for query in QUERIES:
        params = urllib.parse.urlencode({'text': query, 'area': 113})
        url = 'https://hh.ru/search/vacancy/rss?' + params
        try:
            root = get_feed(url)
            success += 1
            count = 0
            for job in parse_feed(root, 'hh.ru'):
                jobs[job['url']] = job
                count += 1
            print(f'RSS {query}: {count} matching vacancies')
        except (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError) as exc:
            errors += 1
            print(f'RSS unavailable for {query}: {type(exc).__name__}: {exc}')
        time.sleep(0.5)
    print(f'Feeds: {success} successful, {errors} failed; total saved {len(jobs)}')
    if success == 0:
        print('WARNING: all feeds failed; existing vacancies.json preserved.')
        raise SystemExit(1)
    if not jobs:
        print('No matching vacancies yet; existing data preserved.')
        return
    result = {
        'updated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'jobs': sorted(jobs.values(), key=lambda j: j.get('published', ''), reverse=True)[:500],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Saved {len(result["jobs"])} vacancies')


if __name__ == '__main__':
    main()
