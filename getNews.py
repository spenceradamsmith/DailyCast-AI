import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

load_dotenv()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
OPENAI_KEY = os.getenv("OPENAI_KEY")

# Mapping categories to source names
categories = {
    "General": ["breitbart-news", "fox-news", "usa-today", "cnn", "associated-press"],
    "Politics": ["breitbart-news", "fox-news", "the-hill", "cnn", "msnbc"],
    "Business": ["financial-post", "business-insider", "fortune", "bloomberg", "the-wall-street-journal"],
    "Technology": ["techcrunch", "wired", "the-verge", "engadget", "ars-technica"],
    "Science": ["national-geographic", "new-scientist", "next-big-future"],
    "Health": ["medical-news-today"],
    "Entertainment": ["buzzfeed", "mtv-news", "entertainment-weekly", "ign", "polygon"],
    "Sports": ["espn", "fox-sports", "the-sport-bible", "bleacher-report", "talksport"],
}
removals_by_category = {
    "General": {
        "Left":   {"breitbart-news", "fox-news", "usa-today"},
        "Center-Left": {"breitbart-news", "fox-news", "associated-press"},
        "Center": {"breitbart-news", "associated-press"},
        "Center-Right": {"breitbart-news", "cnn", "associated-press"},
        "Right":  {"usa-today", "cnn", "associated-press"},
    },
    "Politics": {
        "Left":   {"breitbart-news", "fox-news", "the-hill"},
        "Center-Left": {"breitbart-news", "fox-news", "msnbc"},
        "Center": {"breitbart-news", "msnbc"},
        "Center-Right": {"breitbart-news", "cnn", "msnbc"},
        "Right":  {"the-hill", "cnn", "msnbc"},
    }
}

# Choose options
chosen_categories = ["Technology", "Sports"]
chosen_keywords = ["Tesla", "Knicks"]
chosen_politics = "Center"
chosen_time = "5 minutes"
chosen_speed = "Normal"
speed_map = {
    "Slow": 0.75,
    "Normal": 1,
    "Fast": 1.25,
    "Faster": 1.5,
    "Very Fast": 2,
}
chosen_time_interval = "14 days"
interval_map = {
    "1 day": 2,
    "3 days": 3,
    "7 days": 7,
    "14 days": 14,
}
time_difference = interval_map.get(chosen_time_interval, 0)
today = datetime.now(timezone.utc)
start_dt = today - timedelta(days = time_difference)
start_date = start_dt.strftime('%Y-%m-%d')
end_date = today.strftime('%Y-%m-%d')

# Get sources from chosen categories
chosen_sources = []
for category in chosen_categories:
    for cat in categories[category]:
        chosen_sources.append(cat)
chosen_sources = list(dict.fromkeys(chosen_sources))

source_removals = set()
for category in chosen_categories:
    if category in removals_by_category:
        source_removals |= removals_by_category[category][chosen_politics]
chosen_sources = [s for s in chosen_sources if s not in source_removals]

source_to_category = {}
for category, source in categories.items():
    for s in source:
        source_to_category.setdefault(s, category)

# NewsAPI pull request
def fetch_articles():
    query_sources = ",".join(chosen_sources)
    query_keywords = " OR ".join(chosen_keywords)
    params = {
        "apiKey": NEWSAPI_KEY,
        "sources": query_sources,
        "qInTitle": query_keywords,
        "from": start_date,
        "to": end_date,
        "pageSize": 100,
        "sortBy": "popularity",
        "language": "en",
    }
    data = requests.get("https://newsapi.org/v2/everything", params = params, timeout = 30)
    return data.json()

def normalize_title(t: str):
    return " ".join((t or "").lower().split())

def fuzzy_dedup(articles, threshold = 0.9):
    kept = []
    for art in articles:
        t = normalize_title(art["title"])
        if any(SequenceMatcher(None, t, normalize_title(k["title"])).ratio() >= threshold for k in kept):
            continue
        kept.append(art)
    return kept
raw_payload = fetch_articles()
raw_articles = raw_payload.get("articles", [])
total_reported = raw_payload.get("totalResults")

# Reformat data
reformatted = []
for a in raw_articles:
    src = a.get("source", {})
    src_name = src.get("name")
    src_id = src.get("id")
    primary_category = source_to_category.get(src_id, source_to_category.get(src_name, "Unknown"))

    published_raw = a.get("publishedAt") or ""
    if "T" in published_raw:
        published_date = published_raw.split("T")[0]
    else:
        published_date = published_raw

    reformatted.append({
        "source": src_name,
        "primary_category": primary_category,
        "title": a.get("title") or "",
        "description": a.get("description") or "",
        "content": a.get("content") or "",
        "url": a.get("url"),
        "publishedAt": published_date,
    })

# Dedup
seen = set()
exact_dedup = []
for art in reformatted:
    nt = normalize_title(art["title"])
    if nt in seen:
        continue
    seen.add(nt)
    exact_dedup.append(art)

# Fuzzy dedup
final_articles = fuzzy_dedup(exact_dedup, threshold = 0.9)

# Sort by category order then oldest first
category_order = {category: i for i, category in enumerate(chosen_categories)}
def to_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return datetime.max

final_articles.sort(
    key = lambda a: (
        category_order.get(a.get("primary_category"), len(category_order)),
        to_date(a.get("publishedAt", "")).timestamp()
    )
)

# Output
output = {
    "meta": {
        "categories": chosen_categories,
        "keywords": chosen_keywords,
        "politics": chosen_politics,
        "sources": chosen_sources,
        "start_date": start_date,
        "end_date": end_date,
        "requested_interval_days": chosen_time_interval,
        "total_results_reported": total_reported,
        "filtered_results_reported": len(final_articles),
        "generated_at_utc": today.isoformat()
    },
    "articles": final_articles
}

with open("podsmith_output.json", "w", encoding = "utf-8") as f:
    json.dump(output, f, indent = 2)

print(
    f"Wrote podsmith_output.json with {len(final_articles)} articles "
    f"(reported {total_reported}, after exact {len(exact_dedup)})"
)