from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json, logging, time
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logging.basicConfig(level=logging.INFO)

def append_page_param(self, url, page_num):
    parsed = urlparse(url)
    # Get existing fragment query string (after #search&)
    if '#' in url and 'search&' in url:
        fragment = parsed.fragment
        qs_string = fragment.split('search&')[-1]
        query = parse_qs(qs_string)
        query['pageNo'] = [str(page_num)]
        new_query = urlencode(query, doseq=True)
        new_fragment = f"search&{new_query}"
        parsed = parsed._replace(fragment=new_fragment)
        return urlunparse(parsed)
    else:
        # fallback: just append pageNo as query param
        return f"{url}&pageNo={page_num}"

class HotcoursesScraper:
    def __init__(self, headless=True):
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--user-agent=Mozilla/5.0")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.programs = []

    def run(self, base_url, max_pages=2):
        for page in range(1, max_pages + 1):
            url = self.append_page_param(base_url, page)
            logging.info(f"Scraping: {url}")
            self.driver.get(url)

            try:
                WebDriverWait(self.driver, 12).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "searchResults__cardWrapper"))
                )
                time.sleep(2)

                # Save screenshot before parsing
                self.driver.save_screenshot(f"screenshot_page_{page}.png")
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                self.parse_page(soup)
            except Exception as e:
                logging.warning(f"Failed to scrape page {page}: {e}")
                self.driver.save_screenshot(f"error_page_{page}.png")
                continue

    def extract(self, soup):
        cards = soup.select(".searchResults__cardWrapper")
        for card in cards:
            try:
                title = card.select_one(".course-title a")
                university = card.select_one(".institution-title")
                location = card.select_one(".location")
                fees = card.find(text="Fees") or card.find(text="Tuition fees")
                duration = card.find(text="Duration")
                
                self.programs.append({
                    "title": title.text.strip() if title else "N/A",
                    "url": title["href"] if title and title.get("href") else "N/A",
                    "university": university.text.strip() if university else "N/A",
                    "location": location.text.strip() if location else "N/A",
                    "tuition": fees.parent.text.strip() if fees else "N/A",
                    "duration": duration.parent.text.strip() if duration else "N/A"
                })
            except Exception as e:
                logging.warning(f"Error parsing a card: {e}")

    def save(self):
        file_name = f"hotcourses_programs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(self.programs, f, indent=2, ensure_ascii=False)
        logging.info(f"✅ Saved {len(self.programs)} programs to {file_name}")

    def close(self):
        self.driver.quit()


# === Run Example ===
if __name__ == "__main__":
    scraper = HotcoursesScraper(headless=True)
    base_url = "https://www.hotcoursesabroad.com/study/training-degrees/international/postgraduate/computer-and-mathematical-science-courses/slevel/3/cgory/e-2/sin/ct/programs.html#search&catCode=E-2&countryId=211&parentQualId=3&nationCode=59&nationCntryCode=59&studyAbroad=Y&studyOnline=N&studyCross=N&studyDomestic=N&studyPartTime=N&startOnlineCampusLater=N&manStdyAbrdFlg=Y&parentCatEngName=Computer%20and%20Mathematical%20Science&fastlane=N"
    scraper.run(base_url, max_pages=2)
    scraper.save()
    scraper.close()
