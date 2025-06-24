from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import json
import logging
from datetime import datetime
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

logging.basicConfig(level=logging.INFO)

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    return text

class BachelorsPortalSeleniumScraper:
    def __init__(self, headless=True):
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        #self.driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
        self.base_url = "https://www.bachelorsportal.com"
        self.programs_data = []

    def fetch_page(self, url):
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "ProgramCard"))
            )
            logging.info("Program cards loaded successfully.")
            return self.driver.page_source
        except Exception as e:
            logging.warning(f"Timeout or error fetching {url}: {e}")
            return None

    def extract_programs_from_page(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.find_all('div', class_='ProgramCard') or \
                soup.find_all('article', class_='program-card') or \
                soup.find_all('div', {'data-role': 'ProgramCard'})
        
        programs = []
        for card in cards:
            try:
                title = card.find('h3') or card.find('h2')
                university = card.find('a', class_='university') or card.find('span', class_='institution')
                location = card.find('span', class_='location') or card.find('div', class_='location')
                url = card.find('a', href=True)
                duration = card.find('span', class_='duration')
                tuition = card.find('span', class_='tuition')
                deadline = card.find('span', class_='deadline')

                program = {
                    'title': title.text.strip() if title else 'N/A',
                    'university': university.text.strip() if university else 'N/A',
                    'city': location.text.strip() if location else 'N/A',
                    'url': self.base_url + url['href'] if url else '',
                    'duration': duration.text.strip() if duration else 'N/A',
                    'tuition_fee': tuition.text.strip() if tuition else 'N/A',
                    'deadline': deadline.text.strip() if deadline else 'N/A',
                    'scraped_at': datetime.now().isoformat()
                }
                programs.append(program)
            except Exception as e:
                logging.warning(f"Error parsing program: {e}")
        return programs
        
    def run_scraper(self, country, discipline, pages=1):
        all_programs = []
        for page in range(1, pages + 1):
            country_slug = slugify(country)
            discipline_slug = slugify(discipline)
            url = f"{self.base_url}/search/bachelor/{discipline_slug}/{country_slug}/page-{page}"
            logging.info(f"Scraping: {url}")
            html = self.fetch_page(url)
            if not html:
                continue
            page_programs = self.extract_programs_from_page(html)
            if not page_programs:
                logging.info(f"No programs found on page {page}")
                break
            all_programs.extend(page_programs)
            time.sleep(2)
        return all_programs

    def save_data(self, data, filename="bachelors_programs"):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"{filename}_{timestamp}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logging.info(f"Saved {len(data)} programs to {output_file}")

    def close(self):
        self.driver.quit()

# Example usage
if __name__ == "__main__":
    scraper = BachelorsPortalSeleniumScraper(headless=True)
    country = "Germany"
    discipline = "Computer Science"
    programs = scraper.run_scraper(country=country, discipline=discipline, pages=2)
    scraper.save_data(programs)
    scraper.close()
