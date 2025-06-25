from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json
import logging
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO)

class EducationsCategoryScraper:
    def __init__(self, headless=True):
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.programs = []

    def run_scraper(self, base_url, max_pages=2):
        for page in range(1, max_pages + 1):
            url = f"{base_url}?page={page}"
            logging.info(f"Scraping: {url}")
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".card__title-link"))
                )
                time.sleep(2)  # Wait for full JS load
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                self.parse_page(soup)
            except Exception as e:
                logging.warning(f"Failed to scrape page {page}: {e}")
                continue

    def parse_page(self, soup):
        cards = soup.select("div.card__content")
        for card in cards:
            try:
                title_tag = card.select_one("a.card__title-link")
                provider = card.select_one(".card__provider")
                location = card.select_one(".card__location")
                link = title_tag["href"] if title_tag and title_tag.has_attr("href") else None

                self.programs.append({
                    "title": title_tag.text.strip() if title_tag else "N/A",
                    "provider": provider.text.strip() if provider else "N/A",
                    "location": location.text.strip() if location else "N/A",
                    "url": f"https://www.educations.com{link}" if link else "N/A"
                })
            except Exception as e:
                logging.warning(f"Error parsing program card: {e}")

    def save_to_file(self):
        filename = f"educations_bachelors_na_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.programs, f, indent=2, ensure_ascii=False)
        logging.info(f"✅ Saved {len(self.programs)} programs to {filename}")

    def close(self):
        self.driver.quit()


# Usage
if __name__ == "__main__":
    scraper = EducationsCategoryScraper(headless=True)
    url = "https://www.educations.com/bachelors-degree/north-america"
    scraper.run_scraper(url, max_pages=2)
    scraper.save_to_file()
    scraper.close()
