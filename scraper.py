import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import os
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Tuple

URL = "https://support.optisigns.com/api/v2/help_center/en-us/articles.json"
STATE_FILE = "data/articles_state.json"
ARTICLES_PER_PAGE = 30
DEFAULT_MAX_PAGES = 2


def ensure_data_dir():
    """Ensure data directory exists."""
    os.makedirs("data", exist_ok=True)
    os.makedirs("articles", exist_ok=True)


def load_state() -> Dict:
    """Load the previous state of articles."""
    ensure_data_dir()
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"articles": {}, "last_run": None}


def save_state(state: Dict):
    """Save the current state of articles."""
    ensure_data_dir()
    state["last_run"] = datetime.now().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def calculate_content_hash(article: Dict) -> str:
    """Calculate hash of article content for change detection."""
    content_for_hash = (
        f"{article['title']}{article['body']}{article.get('updated_at', '')}"
    )
    return hashlib.md5(content_for_hash.encode("utf-8")).hexdigest()


def fetch_all_articles(max_pages: int = 10) -> List[Dict]:
    """Fetch articles with pagination until we get all recent updates."""
    all_articles = []
    page = 1
    per_page = ARTICLES_PER_PAGE

    while page <= max_pages:
        print(f"Fetching page {page}...")
        response = requests.get(
            URL,
            params={
                "per_page": per_page,
                "page": page,
                "sort_by": "updated_at",
                "sort_order": "desc",
            },
        )

        if response.status_code != 200:
            print(f"Error fetching page {page}: {response.status_code}")
            break

        data = response.json()
        articles = data.get("articles", [])

        if not articles:  # No more articles
            break

        all_articles.extend(articles)

        # If we got fewer articles than requested, we've reached the end
        if len(articles) < per_page:
            break

        page += 1

    print(f"Fetched {len(all_articles)} total articles from {page-1} pages")
    return all_articles


def detect_article_changes(
    articles: List[Dict], previous_state: Dict
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Detect new, updated, and unchanged articles.
    Returns: (new_articles, updated_articles, skipped_articles)
    """
    previous_articles = previous_state.get("articles", {})

    new_articles = []
    updated_articles = []
    skipped_articles = []

    for article in articles:
        article_id = str(article["id"])
        current_hash = calculate_content_hash(article)

        if article_id not in previous_articles:
            # New article
            new_articles.append(article)
        elif previous_articles[article_id]["hash"] != current_hash:
            # Updated article
            updated_articles.append(article)
        else:
            # Unchanged article
            skipped_articles.append(article)

    return new_articles, updated_articles, skipped_articles


def to_markdown(article: Dict) -> Tuple[str, str]:
    """Convert article to markdown format."""
    title = article["title"]
    html = article["body"]
    slug = str(article["id"])

    soup = BeautifulSoup(html, "html.parser")

    # Remove unwanted elements
    for element in soup.find_all(["nav", "footer"]):
        element.decompose()

    for element in soup.find_all(
        class_=["nav", "navigation", "ad", "ads", "advertisement"]
    ):
        element.decompose()

    for element in soup.find_all(
        id=["nav", "navigation", "ad", "ads", "advertisement"]
    ):
        element.decompose()

    cleaned_html = str(soup)
    markdown = md(cleaned_html)

    return slug, f"# {title}\n\n{markdown}"


def save_articles_delta(new_articles: List[Dict], updated_articles: List[Dict]) -> Dict:
    """
    Save only new and updated articles to files.
    Returns dictionary with file paths for upload.
    """
    ensure_data_dir()

    files_to_upload = {"new": [], "updated": []}

    # Process new articles
    for article in new_articles:
        slug, content = to_markdown(article)
        filepath = f"articles/{slug}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        files_to_upload["new"].append(filepath)

    # Process updated articles
    for article in updated_articles:
        slug, content = to_markdown(article)
        filepath = f"articles/{slug}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        files_to_upload["updated"].append(filepath)

    return files_to_upload


def update_state_with_articles(state: Dict, all_articles: List[Dict]) -> Dict:
    """Update state with current article information."""
    for article in all_articles:
        article_id = str(article["id"])
        state["articles"][article_id] = {
            "hash": calculate_content_hash(article),
            "updated_at": article.get("updated_at"),
            "title": article["title"],
        }
    return state


def fetch_articles_with_delta() -> Tuple[Dict, Dict]:
    """
    Main function to fetch articles and detect changes.
    Returns: (files_to_upload, counts)
    """
    # Load previous state
    previous_state = load_state()

    # Fetch all recent articles
    all_articles = fetch_all_articles(max_pages=DEFAULT_MAX_PAGES)

    # Detect changes
    new_articles, updated_articles, skipped_articles = detect_article_changes(
        all_articles, previous_state
    )

    # Save only changed articles to files
    files_to_upload = save_articles_delta(new_articles, updated_articles)

    # Update and save state
    updated_state = update_state_with_articles(previous_state, all_articles)
    save_state(updated_state)

    # Prepare counts for logging at upload stage
    counts = {
        "total_fetched": len(all_articles),
        "new": len(new_articles),
        "updated": len(updated_articles),
        "skipped": len(skipped_articles),
    }

    return files_to_upload, counts
