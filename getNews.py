import os
import requests
import re
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from openai import OpenAI

load_dotenv()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
client = OpenAI(
    api_key = os.getenv("OPENAI_KEY")
)
speech_file_path = Path(__file__).parent / "speech.mp3"

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

# Map NewsAPI source IDs to real names
source_display_names = {
    "breitbart-news": "Breitbart News",
    "fox-news": "Fox News",
    "usa-today": "USA Today",
    "cnn": "CNN",
    "associated-press": "Associated Press",
    "the-hill": "The Hill",
    "msnbc": "MSNBC",
    "financial-post": "Financial Post",
    "business-insider": "Business Insider",
    "fortune": "Fortune",
    "bloomberg": "Bloomberg",
    "the-wall-street-journal": "The Wall Street Journal",
    "techcrunch": "TechCrunch",
    "wired": "Wired",
    "the-verge": "The Verge",
    "engadget": "Engadget",
    "ars-technica": "Ars Technica",
    "national-geographic": "National Geographic",
    "new-scientist": "New Scientist",
    "next-big-future": "Next Big Future",
    "medical-news-today": "Medical News Today",
    "buzzfeed": "BuzzFeed",
    "mtv-news": "MTV News",
    "entertainment-weekly": "Entertainment Weekly",
    "ign": "IGN",
    "polygon": "Polygon",
    "espn": "ESPN",
    "fox-sports": "Fox Sports",
    "the-sport-bible": "SportBible",
    "bleacher-report": "Bleacher Report",
    "talksport": "talkSPORT",
}

# Choose options
chosen_categories = ["Technology", "Sports"]
chosen_keywords = ["Tesla", "Apple", "Knicks"]
chosen_politics = "Center"
chosen_time = 5
chosen_tone = "None"
chosen_time_interval = "14 days"
interval_map = {
    "2 days": 2,
    "3 days": 3,
    "7 days": 7,
    "14 days": 14,
}
chosen_total_words = chosen_time * 178
low_bound_words = int(chosen_total_words * 0.99)
high_bound_words = int(chosen_total_words * 1.01)
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

display_sources = [
    source_display_names.get(src_id, src_id) for src_id in chosen_sources
]

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
        "image": a.get("urlToImage"),
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

# Output
output = {
    "settings/input": {
        "categories": chosen_categories,
        "keywords": chosen_keywords,
        "politics": chosen_politics,
        "sources": display_sources,
        "start_date": start_date,
        "end_date": end_date,
        "requested_interval_days": chosen_time_interval,
        "total_results_reported": total_reported,
        "filtered_results_reported": len(final_articles),
        "generated_at_utc": today.isoformat()
    }
}

def clean_field(s: str) -> str:
    if s is None:
        return ""
    s = s.replace('\r', ' ')
    s = s.replace('\n', '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# Clean text before grouping
for art in final_articles:
    for field in ("title", "description", "content"):
        art[field] = clean_field(art.get(field, ""))

# Group articles
keyword_patterns = {
    kw: re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
    for kw in chosen_keywords
}

grouped = defaultdict(lambda: defaultdict(list))

for art in final_articles:
    cat = art.get("primary_category", "Unknown")
    title_lc = (art.get("title") or "").lower()
    matched_any = False
    for kw, pat in keyword_patterns.items():
        if pat.search(title_lc):
            grouped[cat][kw].append(art)
            matched_any = True
    if not chosen_keywords:
        grouped[cat]["__NO_KEYWORDS__"].append(art)
    elif not matched_any:
        grouped[cat]["__UNMATCHED__"].append(art)

def to_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return datetime.min

# Sort each group by date
for kwdict in grouped.values():
    for arts in kwdict.values():
        arts.sort(key=lambda a: to_date(a.get("publishedAt", "")), reverse = False)

keyword_position = {kw: i for i, kw in enumerate(chosen_keywords)}
def keyword_order_key(kw):
    if kw == "__UNMATCHED__":
        return (1_000_000, kw)
    if kw == "__NO_KEYWORDS__":
        return (1_000_001, kw)
    return (0, keyword_position.get(kw, 9_999_999))

# Preserve chosen category order
ordered_grouped = {}
for cat in chosen_categories:
    if cat in grouped:
        kwdict = grouped[cat]
        ordered_grouped[cat] = {
            kw: kwdict[kw] for kw in sorted(kwdict.keys(), key = keyword_order_key)
        }

output["articles/output"] = ordered_grouped
output["group article counts"] = {
    cat: {kw: len(arts) for kw, arts in kwdict.items()}
    for cat, kwdict in ordered_grouped.items()
}

with open("podsmith_output.json", "w", encoding = "utf-8") as f:
    json.dump(output, f, indent = 2, ensure_ascii = False)

system_prompt = f"""
You are an award‑winning podcast writer. Using only the structured JSON news data (with each top‑level key representing a category and its articles in chronological order), produce one seamless, conversational podcast script in natural paragraphs. Follow these rules absolutely:
You must write **between {low_bound_words} and {high_bound_words} words** (95%–105% of {chosen_total_words}).  
1. Draft your script normally.  
2. If the count is outside the bounds, automatically trim or expand to hit the target, then output the final script and updated count.
• Use all fields from the JSON (titles, summaries, sources, publication dates, etc.) without inventing any new events or quotes. Reasonable, widely known context or inferences are allowed.  
• Do not use headings, lists, bullet points, links, or any markdown.  
• Create one flowing segment per category, in the JSON’s given order. Within each, cover its articles in the order they appear.  
• Open with a concise, attention‑grabbing hook that previews the episode’s top stories and time frame.  
• Employ smooth, conversational transitions between segments (e.g., “Now, let’s turn to our next story…”).  
• End with a brief sign‑off and a teaser for tomorrow’s episode.  
• Write entirely in natural, spoken‑style paragraphs—ready for recording.

Output only the raw script text.
"""

user_prompt = json.dumps(output, indent = 2)

# 4. Save to a .txt file
full_prompt = system_prompt + "\n\n" + user_prompt
with open("podcast_prompt.txt", "w", encoding = "utf-8") as f:
    f.write(full_prompt)
with open("podcast_prompt.txt", "r", encoding = "utf-8") as f:
    full_prompt = f.read()

# 3. Call the API
response = client.responses.create(
    model = "gpt-4o-mini",
    instructions = system_prompt,
    input = user_prompt
)

script = response.output_text
# 4. Extract and save the script
with open("podcast_script.txt", "w", encoding = "utf-8") as f:
    f.write(response.output_text)

print("Wrote generated podcast script to podcast_script.txt")

with open("podcast_script.txt", "r", encoding="utf-8") as f:
    text = f.read()

with client.audio.speech.with_streaming_response.create(
    model = "gpt-4o-mini-tts",
    voice = "coral",
    input = script,
    instructions = "Read the script of a podcast.",
) as response:
    response.stream_to_file(speech_file_path)

print("Saved podcast_audio.mp3")