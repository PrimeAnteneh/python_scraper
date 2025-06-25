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
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

    def extract_program_info(self, card_text, link_href):
        """Extract program information from card text using patterns"""
        # Split text into lines
        lines = [line.strip() for line in card_text.split('\n') if line.strip()]
        
        program_info = {
            "title": "N/A",
            "school": "N/A",
            "location": "N/A",
            "tuition": "N/A",
            "url": f"https://www.applyboard.com{link_href}"
        }
        
        # Extract school - usually contains University/College and appears early
        for line in lines[:5]:  # Check first 5 lines
            if any(inst in line for inst in ["University", "College", "Institute", "School"]):
                # Make sure it's not a program name
                if not any(degree in line for degree in ["Bachelor of", "Master of", "Associate of"]):
                    # Clean up the school name
                    school = line.replace("(Opens in new tab)", "").strip()
                    if school:
                        program_info["school"] = school
                        break
        
        # Extract program title
        for line in lines:
            if any(line.startswith(degree) for degree in ["Bachelor of", "Master of", "Associate of", "Certificate", "Diploma"]):
                title = line.replace("(Opens in new tab)", "").strip()
                if title:
                    program_info["title"] = title
                    break
        
        # Extract location - look for patterns after "Location" or "Campus city"
        location_found = False
        for i, line in enumerate(lines):
            if line in ["Location", "Campus city"] and i + 1 < len(lines):
                location = lines[i + 1]
                # Check if next line might be state/country
                if i + 2 < len(lines) and ("USA" in lines[i + 2] or any(state in lines[i + 2] for state in ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA"])):
                    location = f"{location}, {lines[i + 2]}"
                program_info["location"] = location
                location_found = True
                break
        
        # If no location found with labels, look for patterns
        if not location_found:
            for line in lines:
                # Look for city, state pattern
                if re.search(r'[A-Za-z\s]+,\s*(USA|[A-Z]{2})', line):
                    program_info["location"] = line
                    break
        
        # Extract tuition
        for i, line in enumerate(lines):
            if line == "Tuition (1st year)" and i + 1 < len(lines):
                if "$" in lines[i + 1]:
                    program_info["tuition"] = lines[i + 1]
                    break
            elif "$" in line and "USD" in line and not any(skip in line.lower() for skip in ["application", "deposit"]):
                program_info["tuition"] = line
                break
        
        return program_info

    def run_scraper(self, search_url):
        logging.info(f"🔍 Scraping: {search_url}")
        self.driver.get(search_url)

        try:
            # Wait for initial page load
            time.sleep(5)
            
            # Wait for content
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/programs/']"))
            )
            
            # Additional wait for dynamic content
            time.sleep(3)
            
            # Scroll to load more content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            
            # Get page source
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Save page source for debugging
            with open("applyboard_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            logging.info("📄 Saved page source")
            
            # Find all program links
            program_links = soup.find_all('a', href=lambda x: x and '/programs/' in x)
            logging.info(f"Found {len(program_links)} program links")
            
            # Process each link
            for link_num, link in enumerate(program_links):
                try:
                    href = link.get('href', '')
                    
                    # Skip if not a valid program link
                    if not href or '/programs/' not in href:
                        continue
                    
                    # Get the card container by going up the DOM tree
                    card = link
                    card_text = ""
                    
                    # Try different levels to find the complete card
                    for level in range(15):
                        parent = card.find_parent()
                        if parent:
                            parent_text = parent.get_text(separator='\n', strip=True)
                            
                            # Check if this parent contains the full card info
                            if all(keyword in parent_text for keyword in ['Tuition', 'Location']):
                                card_text = parent_text
                                logging.debug(f"Found complete card at level {level}")
                                break
                            # Keep the largest text found so far
                            elif len(parent_text) > len(card_text):
                                card_text = parent_text
                            
                            card = parent
                    
                    # If we have card text, extract info
                    if card_text:
                        program_info = self.extract_program_info(card_text, href)
                        
                        # Only add if we have meaningful data
                        if program_info["title"] != "N/A" or program_info["school"] != "N/A":
                            self.results.append(program_info)
                            logging.info(f"✓ Program {link_num + 1}: {program_info['title'][:50]}... at {program_info['school'][:30]}...")
                    
                except Exception as e:
                    logging.warning(f"Error processing link {link_num + 1}: {e}")
                    continue
            
            # Save debug info for first 3 cards
            self.save_debug_cards(soup)
            
        except Exception as e:
            logging.error(f"❌ Error during scraping: {e}")
            self.driver.save_screenshot("applyboard_error.png")

    def save_debug_cards(self, soup):
        """Save detailed info about first 3 cards for debugging"""
        try:
            debug_data = []
            links = soup.find_all('a', href=lambda x: x and '/programs/' in x)[:3]
            
            for i, link in enumerate(links):
                # Get card by going up
                card = link
                for _ in range(10):
                    parent = card.find_parent()
                    if parent and 'Tuition' in parent.get_text():
                        card = parent
                        break
                    elif parent:
                        card = parent
                
                # Extract all text
                card_text = card.get_text(separator='\n', strip=True)
                lines = [line for line in card_text.split('\n') if line.strip()]
                
                debug_entry = {
                    "card_number": i + 1,
                    "link": link.get('href', ''),
                    "text_lines": lines[:30],  # First 30 lines
                    "extracted_info": self.extract_program_info(card_text, link.get('href', ''))
                }
                debug_data.append(debug_entry)
            
            with open("debug_cards.json", "w", encoding="utf-8") as f:
                json.dump(debug_data, f, indent=2, ensure_ascii=False)
            logging.info("📝 Saved debug info to debug_cards.json")
            
        except Exception as e:
            logging.warning(f"Could not save debug info: {e}")

    def save_to_file(self):
        # Remove duplicates
        seen_urls = set()
        unique_results = []
        for result in self.results:
            if result["url"] not in seen_urls:
                seen_urls.add(result["url"])
                unique_results.append(result)
        
        self.results = unique_results
        
        filename = f"applyboard_programs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        logging.info(f"✅ Saved {len(self.results)} unique programs to {filename}")
        
        # Show summary
        if self.results:
            logging.info("\n📋 Summary of extracted data:")
            
            # Count how many have each field
            fields_count = {
                "schools": sum(1 for r in self.results if r["school"] != "N/A"),
                "locations": sum(1 for r in self.results if r["location"] != "N/A"),
                "tuitions": sum(1 for r in self.results if r["tuition"] != "N/A")
            }
            
            logging.info(f"  - Programs with school names: {fields_count['schools']}/{len(self.results)}")
            logging.info(f"  - Programs with locations: {fields_count['locations']}/{len(self.results)}")
            logging.info(f"  - Programs with tuition info: {fields_count['tuitions']}/{len(self.results)}")
            
            logging.info("\n📋 Sample results:")
            for i, result in enumerate(self.results[:5]):
                logging.info(f"\n{i+1}. {result['title']}")
                logging.info(f"   School: {result['school']}")
                logging.info(f"   Location: {result['location']}")
                logging.info(f"   Tuition: {result['tuition']}")
                logging.info(f"   URL: {result['url'][:60]}...")
        else:
            logging.warning("⚠️ No programs were extracted!")

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
