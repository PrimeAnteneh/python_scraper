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
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Additional options to avoid detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Execute script to remove webdriver property
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.results = []

    def wait_for_content_load(self):
        """Wait for the skeleton loaders to disappear and actual content to appear"""
        try:
            # Wait for skeleton loaders to disappear
            WebDriverWait(self.driver, 10).until_not(
                EC.presence_of_element_located((By.CLASS_NAME, "skeleton"))
            )
        except:
            pass  # Continue if no skeleton elements found
        
        # Additional wait for dynamic content
        time.sleep(3)

    def run_scraper(self, search_url):
        logging.info(f"🔍 Scraping: {search_url}")
        self.driver.get(search_url)

        try:
            # Initial wait for page load
            time.sleep(5)
            
            # Wait for content to load
            self.wait_for_content_load()
            
            # Save initial screenshot
            self.driver.save_screenshot("applyboard_initial.png")
            
            # Try multiple selectors for program cards
            card_selectors = [
                "[data-testid='search-result-card']",
                ".search-result-card",
                "div[class*='program-card']",
                "div[class*='search-result']",
                "a[href*='/programs/']",
                "div[class*='MuiCard']",
                "div[class*='card'][class*='program']"
            ]
            
            cards_found = False
            for selector in card_selectors:
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    logging.info(f"✅ Found elements with selector: {selector}")
                    cards_found = True
                    break
                except:
                    continue
            
            if not cards_found:
                # If no cards found with CSS selectors, try XPath
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'MuiGrid-item')]//a[contains(@href, '/programs/')]"))
                    )
                    logging.info("✅ Found elements with XPath selector")
                    cards_found = True
                except:
                    pass
            
            # Scroll to load more content if needed
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            
            # Save screenshot after waiting
            self.driver.save_screenshot("applyboard_after_wait.png")
            
            # Save page source for debugging
            with open("applyboard_source.html", "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            logging.info("📄 Saved page source to applyboard_source.html")
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            self.parse_results(soup)

        except Exception as e:
            logging.error(f"❌ Error during scraping: {e}")
            self.driver.save_screenshot("applyboard_error.png")
            logging.info("📸 Saved applyboard_error.png")

    def parse_results(self, soup):
        # Try multiple parsing strategies
        logging.info("🔎 Attempting to parse results...")
        
        # Strategy 1: Look for links containing /programs/
        program_links = soup.find_all('a', href=lambda x: x and '/programs/' in x)
        if program_links:
            logging.info(f"Found {len(program_links)} program links")
            for link in program_links:
                try:
                    # Get the parent container that likely has all the info
                    card = link.find_parent('div', recursive=True)
                    if card:
                        # Extract text content from the card
                        texts = [text.strip() for text in card.find_all(text=True) if text.strip()]
                        
                        # Try to identify program info from the texts
                        program_info = {
                            "title": "N/A",
                            "school": "N/A",
                            "location": "N/A",
                            "tuition": "N/A",
                            "url": f"https://www.applyboard.com{link['href']}"
                        }
                        
                        # Look for patterns in the text
                        for i, text in enumerate(texts):
                            # Program titles often contain "Bachelor", "Master", etc.
                            if any(degree in text for degree in ["Bachelor", "Master", "Associate", "Diploma", "Certificate"]):
                                program_info["title"] = text
                            # Universities often contain "University", "College", "Institute"
                            elif any(inst in text for inst in ["University", "College", "Institute", "School"]):
                                program_info["school"] = text
                            # Location patterns
                            elif ", USA" in text or "USA" in text:
                                program_info["location"] = text
                            # Tuition patterns
                            elif "$" in text and "USD" in text:
                                program_info["tuition"] = text
                        
                        if program_info["title"] != "N/A":  # Only add if we found a title
                            self.results.append(program_info)
                            
                except Exception as e:
                    logging.warning(f"Error parsing link: {e}")
        
        # Strategy 2: Look for any div/article elements that might be cards
        if not self.results:
            potential_cards = soup.find_all(['div', 'article'], class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['card', 'result', 'program', 'item']))
            logging.info(f"Found {len(potential_cards)} potential card elements")
            
            for card in potential_cards[:20]:  # Limit to first 20 to avoid duplicates
                try:
                    texts = [text.strip() for text in card.find_all(text=True) if text.strip()]
                    if len(texts) >= 3:  # A valid card should have multiple text elements
                        # Look for a link
                        link = card.find('a', href=True)
                        
                        program_info = {
                            "title": texts[0] if texts else "N/A",
                            "school": texts[1] if len(texts) > 1 else "N/A",
                            "location": texts[2] if len(texts) > 2 else "N/A",
                            "tuition": "N/A",
                            "url": f"https://www.applyboard.com{link['href']}" if link else "N/A"
                        }
                        
                        # Refine by looking for specific patterns
                        for text in texts:
                            if "$" in text and "USD" in text:
                                program_info["tuition"] = text
                            elif ", USA" in text:
                                program_info["location"] = text
                        
                        if link and "/programs/" in str(link.get('href', '')):
                            self.results.append(program_info)
                            
                except Exception as e:
                    continue
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_results = []
        for result in self.results:
            if result["url"] not in seen_urls and result["url"] != "N/A":
                seen_urls.add(result["url"])
                unique_results.append(result)
        
        self.results = unique_results
        logging.info(f"📊 Parsed {len(self.results)} unique programs")

    def save_to_file(self):
        filename = f"applyboard_programs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        logging.info(f"✅ Saved {len(self.results)} programs to {filename}")
        
        # Also save a summary
        if self.results:
            logging.info("\n📋 Sample results:")
            for i, result in enumerate(self.results[:3]):
                logging.info(f"\n{i+1}. {result['title']}")
                logging.info(f"   School: {result['school']}")
                logging.info(f"   Location: {result['location']}")
                logging.info(f"   Tuition: {result['tuition']}")

    def close(self):
        self.driver.quit()


# Usage
if __name__ == "__main__":
    scraper = ApplyBoardScraper(headless=True)
    search_url = "https://www.applyboard.com/search?filter[locations]=us&filter[q]=Computer%20Science"
    
    try:
        scraper.run_scraper(search_url)
        scraper.save_to_file()
    finally:
        scraper.close()
