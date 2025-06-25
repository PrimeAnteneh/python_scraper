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

    def analyze_html_structure(self, soup):
        """Analyze and log the HTML structure to understand the layout"""
        logging.info("🔬 Analyzing HTML structure...")
        
        # Find a sample program link
        sample_link = soup.find('a', href=lambda x: x and '/programs/' in x)
        if sample_link:
            # Navigate up to find the card container
            current = sample_link
            for level in range(5):
                parent = current.find_parent()
                if parent:
                    # Log the tag and classes
                    classes = parent.get('class', [])
                    logging.info(f"Level {level}: <{parent.name}> with classes: {classes}")
                    
                    # Get immediate children info
                    children = [child.name for child in parent.children if hasattr(child, 'name')]
                    logging.info(f"  Children tags: {children[:5]}...")  # First 5 children
                    
                    # Get text preview
                    text_preview = parent.get_text(strip=True)[:200]
                    logging.info(f"  Text preview: {text_preview}...")
                    
                    current = parent
            
            # Also log the complete card HTML for manual inspection
            card_parent = sample_link.find_parent('div')
            if card_parent:
                # Go up until we find a reasonably sized container
                while card_parent and len(str(card_parent)) < 500:
                    card_parent = card_parent.find_parent('div')
                
                if card_parent:
                    with open("sample_card.html", "w", encoding="utf-8") as f:
                        f.write(str(card_parent.prettify()))
                    logging.info("📄 Saved sample card HTML to sample_card.html")

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
            
            # Analyze structure first
            self.analyze_html_structure(soup)
            
            # Then parse results
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
                    # Get the parent container - try multiple levels up
                    card = None
                    current = link
                    for _ in range(5):  # Go up to 5 levels
                        parent = current.find_parent(['div', 'article', 'li'])
                        if parent:
                            # Check if this parent contains meaningful content
                            text_content = parent.get_text(strip=True)
                            if len(text_content) > 50:  # Likely a card with content
                                card = parent
                                break
                            current = parent
                    
                    if card:
                        # Extract all text elements
                        all_text = card.get_text(separator='\n', strip=True)
                        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                        
                        # Try to identify program info from the lines
                        program_info = {
                            "title": "N/A",
                            "school": "N/A", 
                            "location": "N/A",
                            "tuition": "N/A",
                            "url": f"https://www.applyboard.com{link['href']}"
                        }
                        
                        # Based on your screenshot, parse the structured data
                        for i, line in enumerate(lines):
                            # Skip common UI elements
                            if line in ['High Job Demand', 'Scholarships Available', 'Location', 'Campus city', 'Tuition (1st year)', 'Application fee']:
                                continue
                                
                            # Program titles often contain degree types
                            if any(degree in line for degree in ["Bachelor", "Master", "Associate", "Diploma", "Certificate", "PhD", "Doctorate"]):
                                if program_info["title"] == "N/A":
                                    program_info["title"] = line
                            # University names
                            elif any(inst in line for inst in ["University", "College", "Institute", "School", "Academy"]) and "Bachelor" not in line and "Master" not in line:
                                if program_info["school"] == "N/A":
                                    program_info["school"] = line
                            # Location - look for state abbreviations or "USA"
                            elif ("USA" in line or ", USA" in line or 
                                  any(state in line for state in ["Washington", "Missouri", "California", "New York", "Texas", "Florida"])):
                                if "$" not in line:  # Make sure it's not tuition
                                    program_info["location"] = line
                            # Tuition
                            elif "$" in line and "USD" in line:
                                program_info["tuition"] = line
                        
                        # Try to get degree type from the link if not found
                        if program_info["title"] == "N/A" and "Year" in all_text:
                            degree_match = None
                            for line in lines:
                                if "Year" in line and any(deg in line for deg in ["Bachelor's", "Master's", "Associate"]):
                                    degree_match = line
                                    break
                            if degree_match:
                                # Look for the next meaningful line after degree type
                                idx = lines.index(degree_match)
                                if idx + 1 < len(lines):
                                    program_info["title"] = lines[idx + 1]
                        
                        # Only add if we have meaningful data
                        if program_info["title"] != "N/A" or program_info["school"] != "N/A":
                            self.results.append(program_info)
                            logging.info(f"✓ Found: {program_info['title']} at {program_info['school']}")
                            
                except Exception as e:
                    logging.warning(f"Error parsing card: {e}")
                    continue
        
        # Strategy 2: Direct extraction based on ApplyBoard's structure
        if not self.results:
            logging.info("Trying alternative parsing strategy...")
            # Look for grid items that contain program info
            grid_items = soup.find_all('div', class_=lambda x: x and 'MuiGrid-item' in str(x))
            
            for item in grid_items:
                try:
                    link = item.find('a', href=lambda x: x and '/programs/' in x)
                    if link:
                        # Extract structured data
                        all_text = item.get_text(separator='\n', strip=True)
                        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                        
                        if len(lines) >= 4:  # Minimum expected content
                            program_info = {
                                "title": "N/A",
                                "school": lines[0] if lines else "N/A",  # Usually first line
                                "location": "N/A",
                                "tuition": "N/A",
                                "url": f"https://www.applyboard.com{link['href']}"
                            }
                            
                            # Parse remaining lines
                            for line in lines[1:]:
                                if any(degree in line for degree in ["Bachelor", "Master", "Associate", "Diploma"]):
                                    program_info["title"] = line
                                elif "$" in line and "USD" in line:
                                    program_info["tuition"] = line
                                elif "USA" in line:
                                    program_info["location"] = line
                            
                            if program_info["title"] != "N/A":
                                self.results.append(program_info)
                
                except Exception as e:
                    continue
        
        # Strategy 3: Parse based on ApplyBoard's actual card structure from screenshots
        if not self.results:
            logging.info("Trying screenshot-based parsing strategy...")
            
            # From the screenshot, we can see the structure has these elements in order:
            # 1. University name (with logo)
            # 2. Degree type (e.g., "4-Year Bachelor's Degree")
            # 3. Program name (e.g., "Bachelor of Science - Computer Science")
            # 4. Various metadata (High Job Demand, Scholarships Available)
            # 5. Location info
            # 6. Tuition info
            
            # Find all links to programs
            all_program_links = soup.find_all('a', href=lambda x: x and '/programs/' in x)
            
            for link in all_program_links:
                try:
                    # Go up to find the card container - usually 3-4 levels up
                    card = link
                    for _ in range(4):
                        parent = card.find_parent('div')
                        if parent:
                            # Check if this looks like a complete card
                            text = parent.get_text(strip=True)
                            if all(keyword in text for keyword in ['Location', 'Tuition']):
                                card = parent
                                break
                            card = parent
                    
                    if card:
                        # Get all text blocks
                        text_blocks = []
                        for elem in card.find_all(['div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                            text = elem.get_text(strip=True)
                            if text and text not in text_blocks:
                                text_blocks.append(text)
                        
                        program_info = {
                            "title": "N/A",
                            "school": "N/A",
                            "location": "N/A", 
                            "tuition": "N/A",
                            "degree_type": "N/A",
                            "url": f"https://www.applyboard.com{link['href']}"
                        }
                        
                        # Parse based on position and content
                        for i, text in enumerate(text_blocks):
                            # University names are usually at the top
                            if i < 3 and any(word in text for word in ["University", "College", "Institute"]):
                                program_info["school"] = text
                            # Degree types
                            elif "Year" in text and any(deg in text for deg in ["Bachelor", "Master", "Associate"]):
                                program_info["degree_type"] = text
                            # Program names with "Bachelor of", "Master of", etc.
                            elif text.startswith(("Bachelor of", "Master of", "Associate of", "Certificate in")):
                                program_info["title"] = text
                            # Location - after "Location" label
                            elif i > 0 and text_blocks[i-1] == "Location" and "USA" in text:
                                program_info["location"] = text
                            # Campus city - might be separate from state
                            elif i > 0 and text_blocks[i-1] == "Campus city":
                                campus = text
                                # Check if next item might be state
                                if i + 1 < len(text_blocks) and "USA" in text_blocks[i + 1]:
                                    program_info["location"] = f"{campus}, {text_blocks[i + 1]}"
                            # Tuition
                            elif "$" in text and "USD" in text and "Tuition" in str(text_blocks[max(0, i-2):i+1]):
                                program_info["tuition"] = text
                        
                        # Add if we have key information
                        if (program_info["title"] != "N/A" or program_info["school"] != "N/A"):
                            self.results.append(program_info)
                            
                except Exception as e:
                    logging.warning(f"Error in strategy 3: {e}")
                    continue
        if not self.results:
            logging.info("Trying alternative parsing strategy...")
            # Look for grid items that contain program info
            grid_items = soup.find_all('div', class_=lambda x: x and 'MuiGrid-item' in str(x))
            
            for item in grid_items:
                try:
                    link = item.find('a', href=lambda x: x and '/programs/' in x)
                    if link:
                        # Extract structured data
                        all_text = item.get_text(separator='\n', strip=True)
                        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                        
                        if len(lines) >= 4:  # Minimum expected content
                            program_info = {
                                "title": "N/A",
                                "school": lines[0] if lines else "N/A",  # Usually first line
                                "location": "N/A",
                                "tuition": "N/A",
                                "url": f"https://www.applyboard.com{link['href']}"
                            }
                            
                            # Parse remaining lines
                            for line in lines[1:]:
                                if any(degree in line for degree in ["Bachelor", "Master", "Associate", "Diploma"]):
                                    program_info["title"] = line
                                elif "$" in line and "USD" in line:
                                    program_info["tuition"] = line
                                elif "USA" in line:
                                    program_info["location"] = line
                            
                            if program_info["title"] != "N/A":
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
        
        # Debug: Print first few results
        if self.results:
            logging.info("Sample parsed data:")
            for i, result in enumerate(self.results[:3]):
                logging.info(f"{i+1}. URL: {result['url'][:50]}...")
                logging.info(f"   Title: {result['title']}")
                logging.info(f"   School: {result['school']}")

    def save_to_file(self):
        filename = f"applyboard_programs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        logging.info(f"✅ Saved {len(self.results)} programs to {filename}")
        
        # Also save a summary
        if self.results:
            logging.info("\n📋 Sample results:")
            for i, result in enumerate(self.results[:5]):  # Show up to 5 samples
                logging.info(f"\n{i+1}. {result.get('title', 'N/A')}")
                logging.info(f"   School: {result.get('school', 'N/A')}")
                logging.info(f"   Location: {result.get('location', 'N/A')}")
                logging.info(f"   Tuition: {result.get('tuition', 'N/A')}")
                if 'degree_type' in result:
                    logging.info(f"   Degree Type: {result.get('degree_type', 'N/A')}")
                logging.info(f"   URL: {result.get('url', 'N/A')[:50]}...")
        else:
            logging.warning("⚠️ No programs were parsed. Check the HTML structure in 'applyboard_source.html' and 'sample_card.html'")

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
