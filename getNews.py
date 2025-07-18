import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta

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
chosen_categories = ["General"]
chosen_keywords = []
chosen_politics = "Center"
chosen_time_interval = "14 days"
interval_map = {
    "1 day": 2,
    "3 days": 3,
    "7 days": 7,
    "14 days": 14,
}
time_difference = interval_map.get(chosen_time_interval, 0)
end_dt = datetime.today()
start_dt = end_dt - timedelta(days = time_difference)
start_date = start_dt.strftime('%Y-%m-%d')
end_date = end_dt.strftime('%Y-%m-%d')

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

# NewsAPI pull request
query_sources = ",".join(chosen_sources)
query_keywords = " OR ".join(chosen_keywords)
headers = {"X-Api-Key": NEWSAPI_KEY}
response = requests.get(
    "https://newsapi.org/v2/everything",
    headers=headers,
    params={
        "apiKey": NEWSAPI_KEY,
        "sources": query_sources,
        "q": query_keywords,
        "from": start_date,
        "to": end_date,
        "pageSize": 100,
        "language": "en",
    }
)
data = response.json()

# Reformat data from NewsAPI
filtered_data = []
for article in data.get("articles", []):
    filtered_data.append({
        "source": article["source"]["name"],
        "title": article["title"],
        "description": article["description"],
        "content": article["content"],
        "url": article["url"],
        "publishedAt": article["publishedAt"].split("T")[0]
    })

with open("podsmith_output.txt", "w", encoding = "utf-8") as out:
    print("Categories:", chosen_categories, file = out)
    print("Keywords:", chosen_keywords, file = out)
    print("Politics:", chosen_politics, file = out)
    print("Sources:", chosen_sources, file = out)
    print("Start Date:", start_date, file = out)
    print("End Date:", end_date, file = out)
    print("Total Results:", data.get("totalResults"), file = out)
    print(json.dumps(filtered_data, indent = 2), file = out)