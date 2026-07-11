import feedparser, requests, json, os, re, html

STATE_DIR = "state"
DEFAULT_COLOR = 0x4A90D9
PREVIEW_COUNT = 5

def clean_html(raw):
    text = re.sub(r"<br\s*/?>", "\n", raw)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()[:600]

def load_last_seen(name):
    path = f"{STATE_DIR}/{name}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f).get("last_id")
    return None

def save_last_seen(name, entry_id):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(f"{STATE_DIR}/{name}.json", "w") as f:
        json.dump({"last_id": entry_id}, f)

def get_category(entry):
    tags = entry.get("tags", [])
    return tags[0]["term"] if tags else "Informational"

def post_to_discord(entry, source):
    category = get_category(entry)
    color = source["category_colors"].get(category, DEFAULT_COLOR)
    embed = {
        "title": entry.title,
        "url": entry.link,
        "description": clean_html(entry.get("summary", "")),
        "color": color,
        "thumbnail": {"url": source["avatar_url"]},
        "footer": {"text": f"{source['display_name']} – {category}"},
        "timestamp": entry.get("published", ""),
    }
    payload = {
        "username": source["display_name"],
        "avatar_url": source["avatar_url"],
        "embeds": [embed],
    }
    resp = requests.post(os.environ[source["webhook_env"]], json=payload)
    resp.raise_for_status()

def process_source(source):
    webhook_url = os.environ.get(source["webhook_env"])
    if not webhook_url:
        print(f"Skipping {source['name']}: no webhook URL set")
        return

    feed = feedparser.parse(source["feed_url"])
    if not feed.entries:
        print(f"{source['name']}: feed unreachable or empty")
        return

    last_seen = load_last_seen(source["name"])

    if last_seen is None:
        if len(feed.entries) > PREVIEW_COUNT:
            seed_entry = feed.entries[PREVIEW_COUNT]
            last_seen = seed_entry.get("id", seed_entry.link)

    new_entries = []
    for entry in feed.entries:
        entry_id = entry.get("id", entry.link)
        if entry_id == last_seen:
            break
        if get_category(entry) == "Normal":
            continue
        new_entries.append(entry)

    for entry in reversed(new_entries):
        post_to_discord(entry, source)

    newest = feed.entries[0]
    save_last_seen(source["name"], newest.get("id", newest.link))

def main():
    with open("config.json") as f:
        sources = json.load(f)
    for source in sources:
        process_source(source)

if __name__ == "__main__":
    main()