import os
import requests
import re
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

app = FastAPI()

# Load environment variables
load_dotenv()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
OPENAI_KEY = os.getenv("OPENAI_KEY")
client = OpenAI(api_key=OPENAI_KEY)

# Define input model
class PodcastInput(BaseModel):
    chosen_categories: list[str] = ["General", "Sports"]
    chosen_keywords: list[str] = ["Tesla", "Knicks"]
    chosen_general_sources: list[str] = ["Breitbart", "Fox News", "CNN", "Associated Press"]
    chosen_political_sources: list[str] = ["Breitbart", "Fox News", "CNN", "Associated Press"]
    chosen_length: int = 5
    chosen_timeframe: int = 2
    chosen_speed: str = "Normal"
    chosen_voice: int = "male1"

# Source mappings and configurations
categories = {
    "General": [],
    "Politics": [],
    "Business": ["financial-post", "business-insider", "fortune", "bloomberg", "the-wall-street-journal"],
    "Technology": ["techcrunch", "wired", "the-verge", "engadget", "ars-technica"],
    "Science": ["national-geographic", "new-scientist", "next-big-future"],
    "Health": ["medical-news-today"],
    "Entertainment": ["buzzfeed", "mtv-news", "entertainment-weekly", "ign", "polygon"],
    "Sports": ["espn", "fox-sports", "the-sport-bible", "bleacher-report", "talksport"],
}

source_display_names = {
    "breitbart-news": "Breitbart News",
    "the-amercian-conservative": "The American Conservative",
    "fox-news": "Fox News",
    "the-jerusalem-post": "The Jerusalem Post",
    "the-hill": "The Hill",
    "associated-press": "Associated Press",
    "usa-today": "USA Today",
    "cbs-news": "CBS News",
    "nbc-news": "NBC News",
    "abc-news": "ABC News",
    "cnn": "CNN",
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

source_map_input = {
    "Breitbart": "breitbart-news",
    "American Conservative": "the-amercian-conservative",
    "Fox News": "fox-news",
    "The Jerusalem Post": "the-jerusalem-post",
    "The Hill": "the-hill",
    "Associated Press": "associated-press",
    "USA Today": "usa-today",
    "CBS": "cbs-news",
    "NBC": "nbc-news",
    "ABC": "abc-news",
    "CNN": "cnn",
    "MSNBC": "msnbc",
}

voice_map = {"male1": "ballad", "male2": "echo", "female1": "fable", "female2": "shimmer"}
speed_map = {"Slow": 0.75, "Normal": 1.0, "Fast": 1.25, "Very Fast": 1.5}
wpm_map = {"Slow": 134, "Normal": 178, "Fast": 223, "Very Fast": 267}

def fetch_articles(chosen_sources, chosen_keywords, start_date, end_date):
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
    response = requests.get("https://newsapi.org/v2/everything", params=params, timeout=30)
    return response.json()

def normalize_title(t: str):
    return " ".join((t or "").lower().split())

def fuzzy_dedup(articles, threshold=0.9):
    kept = []
    for art in articles:
        t = normalize_title(art["title"])
        if any(SequenceMatcher(None, t, normalize_title(k["title"])).ratio() >= threshold for k in kept):
            continue
        kept.append(art)
    return kept

def clean_field(s: str) -> str:
    if s is None:
        return ""
    s = s.replace('\r', ' ').replace('\n', '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def to_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return datetime.min

@app.post("/generate_podcast")
async def generate_podcast(podcast_input: PodcastInput):
    # Process inputs
    chosen_categories = podcast_input.chosen_categories
    chosen_keywords = podcast_input.chosen_keywords
    chosen_general_sources = podcast_input.chosen_general_sources
    chosen_political_sources = podcast_input.chosen_political_sources
    chosen_length = podcast_input.chosen_length
    chosen_timeframe = podcast_input.chosen_timeframe
    chosen_speed = podcast_input.chosen_speed
    chosen_voice = podcast_input.chosen_voice

    # Set up categories
    categories["General"] = [
        source_map_input.get(src, src.lower().replace(' ', '-')) for src in chosen_general_sources
    ]
    categories["Politics"] = [
        source_map_input.get(src, src.lower().replace(' ', '-')) for src in chosen_political_sources
    ]

    # Calculate word count bounds
    chosen_total_words = chosen_length * wpm_map[chosen_speed]
    low_bound_words = int(chosen_total_words * 0.99)
    high_bound_words = int(chosen_total_words * 1.01)

    # Set up timeframe
    today = datetime.now(timezone.utc)
    start_dt = today - timedelta(days=chosen_timeframe)
    start_date = start_dt.strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')

    # Get chosen sources
    chosen_sources = []
    for category in chosen_categories:
        chosen_sources.extend(categories[category])
    chosen_sources = list(dict.fromkeys(chosen_sources))
    display_sources = [source_display_names.get(src_id, src_id) for src_id in chosen_sources]

    # Map sources to categories
    source_to_category = {}
    for category, sources in categories.items():
        for s in sources:
            source_to_category[s] = category

    # Fetch and process articles
    raw_payload = fetch_articles(chosen_sources, chosen_keywords, start_date, end_date)
    raw_articles = raw_payload.get("articles", [])

    reformatted = []
    for a in raw_articles:
        src = a.get("source", {})
        src_name = src.get("name")
        src_id = src.get("id")
        primary_category = source_to_category.get(src_id, source_to_category.get(src_name, "Unknown"))
        published_raw = a.get("publishedAt") or ""
        published_date = published_raw.split("T")[0] if "T" in published_raw else published_raw

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

    # Deduplicate articles
    seen = set()
    exact_dedup = [art for art in reformatted if not (normalize_title(art["title"]) in seen or seen.add(normalize_title(art["title"]))) ]
    final_articles = fuzzy_dedup(exact_dedup, threshold=0.9)

    # Group and sort articles
    keyword_patterns = {kw: re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE) for kw in chosen_keywords}
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

    for kwdict in grouped.values():
        for arts in kwdict.values():
            arts.sort(key=lambda a: to_date(a.get("publishedAt", "")), reverse=False)

    keyword_position = {kw: i for i, kw in enumerate(chosen_keywords)}
    def keyword_order_key(kw):
        if kw == "__UNMATCHED__":
            return (1_000_000, kw)
        if kw == "__NO_KEYWORDS__":
            return (1_000_001, kw)
        return (0, keyword_position.get(kw, 9_999_999))

    ordered_grouped = {}
    for cat in chosen_categories:
        if cat in grouped:
            kwdict = grouped[cat]
            ordered_grouped[cat] = {kw: kwdict[kw] for kw in sorted(kwdict.keys(), key=keyword_order_key)}

    # Create output JSON
    output = {
        "settings/input": {
            "categories": chosen_categories,
            "keywords": chosen_keywords,
            "sources": display_sources,
            "start_date": start_date,
            "end_date": end_date,
            "timeframe_days": chosen_timeframe,
            "podcast_length_min": chosen_length,
            "speech_speed": chosen_speed,
            "voice": voice_map[chosen_voice],
            "results_reported": len(final_articles),
            "generated_at": today.isoformat()
        },
        "articles/output": ordered_grouped,
        "group article counts": {
            cat: {kw: len(arts) for kw, arts in kwdict.items()}
            for cat, kwdict in ordered_grouped.items()
        }
    }

    # Save JSON output
    output_path = Path("podsmith_output.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Generate podcast script
    system_prompt = f"""
    You are an award-winning podcast writer. Using only the structured JSON news data (with each top-level key representing a category and its articles in chronological order), produce one seamless, conversational podcast script in natural paragraphs. Follow these rules absolutely:
    You must write **between {low_bound_words} and {high_bound_words} words** (95%–105% of {chosen_total_words}).  
    1. Draft your script normally.  
    2. If the count is outside the bounds, automatically trim or expand to hit the target, then output the final script.
    • Use all fields from the JSON (titles, summaries, sources, publication dates, etc.) without inventing any new events or quotes. Reasonable, widely known context or inferences are allowed.  
    • Do not use headings, lists, bullet points, links, or any markdown.  
    • Create one flowing segment per category, in the JSON’s given order. Within each, cover its articles in the order they appear.  
    • Open with a concise, attention-grabbing hook that previews the episode’s top stories and time frame.  
    • Employ smooth, conversational transitions between segments (e.g., “Now, let’s turn to our next story…”).  
    • End with a brief sign-off and a teaser for tomorrow’s episode.  
    • Write entirely in natural, spoken-style paragraphs—ready for recording.
    Output only the raw script text.
    """

    user_prompt = json.dumps(output, indent=2)
    response = client.responses.create(
        model="gpt-4o-mini",
        instructions=system_prompt,
        input=user_prompt
    )
    script = response.output_text

    # Save script
    script_path = Path("podcast_script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    # Generate summary
    summary_response = client.responses.create(
        model="gpt-4o-mini",
        instructions="Summarize the input in a few sentences very clearly.",
        input=script
    )
    summary = summary_response.output_text
    summary_path = Path("podcast_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)

    # Generate title
    title_response = client.responses.create(
        model="gpt-4o-mini",
        instructions="Create a concise, compelling podcast episode title (max 30 characters) based on the following script. No quotation marks; return only the title.",
        input=script
    )
    episode_title = title_response.output_text.strip()
    title_path = Path("podcast_title.txt")
    with open(title_path, "w", encoding="utf-8") as f:
        f.write(episode_title)

    # Generate audio
    audio_path = Path("podcast_audio.mp3")
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice=voice_map[chosen_voice],
        input=script,
        instructions="Read the script of a podcast.",
        speed=speed_map[chosen_speed]
    ) as audio_response:
        audio_response.stream_to_file(audio_path)

    return {
        "script": script,
        "summary": summary,
        "title": episode_title,
        "audio_path": str(audio_path),
        "json_output": output
    }

@app.get("/download/{file_type}")
async def download_file(file_type: str):
    file_map = {
        "script": "podcast_script.txt",
        "summary": "podcast_summary.txt",
        "title": "podcast_title.txt",
        "audio": "podcast_audio.mp3",
        "json": "podsmith_output.json"
    }
    file_path = file_map.get(file_type)
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)