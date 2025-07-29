import requests

BASE_URL = "http://podsmith-api.us-east-2.elasticbeanstalk.com"

# 1) Quick health‑check
r = requests.get(f"{BASE_URL}/")
print("GET / →", r.status_code, r.text)

# 2) Generate a podcast
payload = {
    "chosen_categories": ["General","Sports"],
    "chosen_keywords": ["Tesla","Knicks"],
    "chosen_general_sources": ["Breitbart","Fox News","CNN","Associated Press"],
    "chosen_political_sources": ["Breitbart","Fox News","CNN","Associated Press"],
    "chosen_length": 5,
    "chosen_timeframe": 2,
    "chosen_speed": "Normal",
    "chosen_voice": "male1"
}

resp = requests.post(
    f"{BASE_URL}/generate_podcast",
    json=payload,
    timeout=60
)

# Print status and raw body
print("POST /generate_podcast →", resp.status_code)
print("Response headers:", resp.headers)
print("Response body:", resp.text)

# Try to parse JSON if possible
try:
    data = resp.json()
    print("Parsed JSON:", data)
except ValueError:
    print("No JSON could be decoded from the response.")
