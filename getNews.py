import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
OPENAI_KEY = os.getenv("OPENAI_KEY")

# Mapping categories to source names
categories = {
    "General":       ["fox-news", "national-review", "reuters", "the-washington-post", "cnn"],
    "Politics":      ["fox-news", "breitbart-news", "the-hill", "politico", "cnn"],
    "Business":      ["financial-post", "business-insider", "fortune", "bloomberg", "the-wall-street-journal"],
    "Technology":    ["techcrunch", "wired", "the-verge", "engadget", "ars-technica"],
    "Science":       ["national-geographic", "new-scientist", "next-big-future"],
    "Health":        ["medical-news-today"],
    "Entertainment": ["buzzfeed", "mtv-news", "entertainment-weekly", "ign", "polygon"],
    "Sports":        ["espn", "fox-sports", "the-sport-bible", "bleacher-report", "talksport"],
}

chosen_categories = ["Technology", "Sports"]
chosen_keywords = ["Tesla", "Knicks"]
start_date = "2025-07-16"
end_date = "2025-07-18"


chosen_sources = []
for category in chosen_categories:
    for cat in categories[category]:
        chosen_sources.append(cat)

# Print selections
print("Sources:", chosen_sources)
print("Keywords:", chosen_keywords)
print("Start Date:", start_date)
print("End Date:", end_date)

# NewsAPI
query_sources = ",".join(chosen_sources)
query_keywords = " OR ".join(chosen_keywords)
headers = {"X-Api-Key": NEWSAPI_KEY}
response = requests.get(
    "https://newsapi.org/v2/everything",
    headers = headers,
    params = {
        "apiKey": NEWSAPI_KEY,
        "sources": query_sources,
        "q": query_keywords,
        "from": start_date,
        "to": end_date,
        "pageSize": 50,
        "language": "en",
    }
)
data = response.json()
print ("Total Results:", data["totalResults"])

filtered_data = []
for article in data.get("articles", []):
    filtered_data.append({
        "source": article["source"]["name"],
        "title": article["title"],
        "description": article["description"],
        "url": article["url"],
        "publishedAt": article["publishedAt"].split("T")[0]
    })

print(json.dumps(filtered_data, indent = 2))