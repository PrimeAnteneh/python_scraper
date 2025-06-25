from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import logging
import time
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)

class ApplyBoardScraper:
    def __init__(self, headless=True):
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.results = []

    def run_scraper(self, search_url):
        logging.info(f"🔍 Scraping: {search_url}")
        self.driver.get(search_url)

        try:
            # Save screenshot early
            self.driver.save_screenshot("applyboard_loaded.png")

            WebDriverWait(self.driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='search-result-card']"))
            )
            time.sleep(2)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            self.parse_results(soup)

        except Exception as e:
            logging.warning(f"⚠️ Page failed to load: {e}")
            try:
                self.driver.save_screenshot("applyboard_error.png")
                logging.info("📸 Saved applyboard_error.png")
            except Exception as se:
                logging.warning(f"Could not save screenshot: {se}")

    def parse_results(self, soup):
        cards = soup.select("[data-testid='search-result-card']")
        for card in cards:
            try:
                title = card.select_one("[data-testid='program-title']")
                school = card.select_one("[data-testid='institution-name']")
                location = card.select_one("[data-testid='program-location']")
                link = card.select_one("a")["href"] if card.select_one("a") else None

                self.results.append({
                    "title": title.text.strip() if title else "N/A",
                    "school": school.text.strip() if school else "N/A",
                    "location": location.text.strip() if location else "N/A",
                    "url": f"https://www.applyboard.com{link}" if link else "N/A"
                })
            except Exception as e:
                logging.warning(f"⚠️ Could not parse one card: {e}")

    def save_to_file(self):
        filename = f"applyboard_programs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        logging.info(f"✅ Saved {len(self.results)} programs to {filename}")

    def close(self):
        self.driver.quit()


# Usage
if __name__ == "__main__":
    scraper = ApplyBoardScraper(headless=True)
    search_url = "https://www.applyboard.com/search?filter[locations]=us&filter[q]=Computer%20Science"
    scraper.run_scraper(search_url)
    scraper.save_to_file()
    scraper.close()
