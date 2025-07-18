import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
OPENAI_KEY = os.getenv("OPENAI_KEY")

# Mapping source names to real names and links
source_info = {
    "associated-press":     ("Associated Press",       "https://apnews.com/"),
    "politico":             ("Politico",               "https://www.politico.com/"),
    "the-hill":             ("The Hill",               "https://thehill.com/"),
    "cnn":                  ("CNN",                    "https://www.cnn.com/"),
    "fox-news":             ("Fox News",               "https://www.foxnews.com/"),
    "reuters":              ("Reuters",                "https://www.reuters.com/"),
    "yahoo-news":           ("Yahoo News",             "https://news.yahoo.com/"),
    "cnbc":                 ("CNBC",                   "https://www.cnbc.com/"),
    "investopedia":         ("Investopedia",           "https://www.investopedia.com/"),
    "fox-business":         ("Fox Business",           "https://www.foxbusiness.com/"),
    "marketwatch":          ("MarketWatch",            "https://www.marketwatch.com/"),
    "yahoo-finance":        ("Yahoo Finance",          "https://finance.yahoo.com/"),
    "techcrunch":           ("TechCrunch",             "https://techcrunch.com/"),
    "wired":                ("Wired",                  "https://www.wired.com/"),
    "the-verge":            ("The Verge",              "https://www.theverge.com/"),
    "cnet":                 ("CNET",                   "https://www.cnet.com/"),
    "zdnet":                ("ZDNet",                  "https://www.zdnet.com/"),
    "live-science":         ("Live Science",           "https://www.livescience.com/"),
    "the-conversation":     ("The Conversation",       "https://theconversation.com/"),
    "sciencealert":         ("ScienceAlert",           "https://www.sciencealert.com/"),
    "phys-org":             ("Phys.org",               "https://phys.org/"),
    "nasa-newsroom":        ("NASA Newsroom",          "https://www.nasa.gov/newsroom"),
    "healthday":            ("HealthDay",              "https://www.healthday.com/"),
    "medical-news-today":   ("Medical News Today",     "https://www.medicalnewstoday.com/"),
    "npr":                  ("NPR Life & Health",      "https://www.npr.org/sections/health/"),
    "cdc-newsroom":         ("CDC Newsroom",           "https://www.cdc.gov/media/index.html"),
    "variety":              ("Variety",                "https://variety.com/"),
    "people":               ("People",                 "https://people.com/"),
    "entertainment-weekly": ("Entertainment Weekly",   "https://ew.com/"),
    "deadline":             ("Deadline",               "https://deadline.com/"),
    "screen-rant":          ("Screen Rant",            "https://screenrant.com/"),
    "espn":                 ("ESPN",                   "https://www.espn.com/"),
    "ap-sports":            ("AP Sports",              "https://apnews.com/hub/sports"),
    "bbc-sport":            ("BBC Sport",              "https://www.bbc.com/sport"),
    "bleacher-report":      ("Bleacher Report",        "https://bleacherreport.com/"),
    "yahoo-sports":         ("Yahoo Sports",           "https://sports.yahoo.com/"),
    "npr-life-and-health":  ("NPR Life & Health",      "https://www.npr.org/sections/health/"),
    "guardian-lifestyle":   ("The Guardian Lifestyle", "https://www.theguardian.com/lifeandstyle"),
    "refinery29":           ("Refinery29",             "https://www.refinery29.com/"),
    "well-and-good":        ("Well+Good",              "https://www.wellandgood.com/"),
    "eater":                ("Eater",                  "https://www.eater.com/"),
    "serious-eats":         ("Serious Eats",           "https://www.seriouseats.com/"),
    "allrecipes":           ("AllRecipes",             "https://www.allrecipes.com/"),
    "guardian-food":        ("The Guardian Food",      "https://www.theguardian.com/food"),
    "delish":               ("Delish",                 "https://www.delish.com/")
}

# Mapping categories to source names
categories = {
    "Politics":      ["associated-press", "politico", "the-hill", "cnn", "fox-news"],
    "General":       ["reuters", "yahoo-news", "associated-press", "cnn", "fox-news"],
    "Business":      ["cnbc", "reuters", "investopedia", "fox-business", "marketwatch"],
    "Finance":       ["cnbc", "yahoo-finance", "reuters", "investopedia", "morningstar"],
    "Technology":    ["techcrunch", "wired", "the-verge", "cnet", "zdnet"],
    "Science":       ["live-science", "the-conversation", "sciencealert", "phys-org", "nasa-newsroom"],
    "Health":        ["healthday", "medical-news-today", "npr", "cdc-newsroom"],
    "Entertainment": ["variety", "people", "entertainment-weekly", "deadline", "screen-rant"],
    "Sports":        ["espn", "ap-sports", "bbc-sport", "bleacher-report", "yahoo-sports"],
    "Lifestyle":     ["npr-life-and-health", "guardian-lifestyle", "refinery29", "well-and-good"],
    "Food":          ["eater", "serious-eats", "allrecipes", "guardian-food", "delish"]
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