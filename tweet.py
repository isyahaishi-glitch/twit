import asyncio
from playwright.async_api import async_playwright
import json
from dotenv import load_dotenv
import os
from flask import Flask, jsonify
from flask_cors import CORS
import threading
from URL import USERNAMES

app = Flask(__name__)
CORS(app)
load_dotenv()

auth_token1 = os.getenv("auth_token")
ct01 = os.getenv("ct0")

COOKIES = [
    {"name": "auth_token", "value": auth_token1, "domain": ".x.com", "path": "/"},
    {"name": "ct0",        "value": ct01,        "domain": ".x.com", "path": "/"},
]

results = []


async def scrape():
    global results
    temp = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_cookies(COOKIES)

        async def scrape_one(username):
            page = await context.new_page()
            try:
                await page.goto(
                    f"https://x.com/{username}",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                await page.wait_for_selector("article", timeout=15000)
                await asyncio.sleep(2)

                tweets = await page.query_selector_all("article")
                for tweet in tweets[:2]:  # up to 2 tweets per account
                    text = await tweet.inner_text()
                    imgs = await tweet.query_selector_all("img")
                    images = []
                    for img in imgs:
                        src = await img.get_attribute("src")
                        if src and "pbs.twimg.com/media" in src:
                            images.append(src)
                    temp.append({
                        "source": username,
                        "text": text,
                        "created_at": "",
                        "image_url": images[0] if images else None,
                    })
            except Exception as e:
                print(f"Error scraping {username}: {e}")
            finally:
                await page.close()

        # Scrape 5 accounts at a time
        chunk_size = 5
        for i in range(0, len(USERNAMES), chunk_size):
            chunk = USERNAMES[i : i + chunk_size]
            await asyncio.gather(*[scrape_one(u) for u in chunk])
            await asyncio.sleep(3)  # pause between chunks

        await browser.close()

    results = temp
    print(json.dumps(results, indent=2))


async def scrape_loop(interval: int = 300):  # runs every 5 minutes
    while True:
        print("Starting scrape...")
        await scrape()
        print(f"Done. Waiting {interval}s...")
        await asyncio.sleep(interval)


def run_scraper():
    asyncio.run(scrape_loop())


@app.route("/tweets")
def route_tweets():
    return jsonify(results)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    thread = threading.Thread(target=run_scraper, daemon=True)
    thread.start()
    app.run(debug=False, host="0.0.0.0", port=port)
