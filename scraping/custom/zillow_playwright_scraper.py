"""
PLAYWRIGHT-BASED ZILLOW SCRAPER
================================

This uses Playwright (real Chrome browser) which is much harder for Zillow to detect
compared to curl-cffi. This is the most reliable FREE scraping method.

Cost: $0/month (just your infrastructure)
Success rate: Much higher than curl-cffi
"""

import asyncio
import csv
import json
import os
import time
from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path
import bittensor as bt
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from common.data import DataEntity, DataLabel, DataSource
from common.date_range import DateRange
from scraping.scraper import ScrapeConfig, Scraper, ValidationResult
from scraping.custom.schema import PropertyDataSchema


class ZillowPlaywrightScraper(Scraper):
    """
    ✅ FREE Zillow scraper using Playwright (real browser)
    ✅ Much more reliable than curl-cffi
    ✅ Harder for Zillow to detect
    ✅ Can solve CAPTCHAs if needed
    
    Cost: $0.00 per scrape 💰
    """
    
    def __init__(self, proxy_url: str = None, zipcodes_file: str = None, headless: bool = True):
        """
        Initialize Playwright scraper
        
        Args:
            proxy_url: Optional proxy (format: "http://user:pass@host:port")
            zipcodes_file: Path to zipcodes.csv
            headless: Run browser in headless mode (True = no visible browser)
        """
        self.proxy_url = proxy_url
        self.headless = headless
        
        # Load zipcodes
        if zipcodes_file is None:
            current_dir = Path(__file__).parent
            zipcodes_file = current_dir / "zipcodes.csv"
        
        self.zipcodes = self._load_zipcodes(zipcodes_file)
        bt.logging.info(f"Loaded {len(self.zipcodes)} zipcodes")
        
        # Playwright instances
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        
        # Rate limiting
        self.requests_per_minute = 10
        self.last_request_time = 0
        self.min_request_interval = 60.0 / self.requests_per_minute
        
        # Stats
        self.stats = {
            'requests': 0,
            'properties_scraped': 0,
            'errors': 0,
            'total_cost': 0.0
        }
    
    async def _init_browser(self):
        """Initialize Playwright browser"""
        if self.browser is not None:
            return
        
        bt.logging.info("Starting Playwright browser...")
        self.playwright = await async_playwright().start()
        
        # Browser launch options
        launch_options = {
            'headless': self.headless,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        }
        
        # Add proxy if provided
        if self.proxy_url:
            # Parse proxy URL
            # Format: http://user:pass@host:port
            proxy_parts = self.proxy_url.replace('http://', '').replace('https://', '')
            if '@' in proxy_parts:
                auth, server = proxy_parts.split('@')
                username, password = auth.split(':')
                launch_options['proxy'] = {
                    'server': f'http://{server}',
                    'username': username,
                    'password': password
                }
            else:
                launch_options['proxy'] = {'server': f'http://{proxy_parts}'}
            
            bt.logging.info(f"Using proxy: {proxy_parts.split('@')[-1]}")
        
        self.browser = await self.playwright.chromium.launch(**launch_options)
        
        # Create context with realistic settings
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
        )
        
        # Stealth settings - hide automation
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Chrome runtime
            window.chrome = {
                runtime: {}
            };
            
            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        bt.logging.success("Browser initialized successfully!")
    
    async def _close_browser(self):
        """Close Playwright browser"""
        if self.context:
            await self.context.close()
            self.context = None
        
        if self.browser:
            await self.browser.close()
            self.browser = None
        
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
    
    async def scrape(self, scrape_config: ScrapeConfig) -> List[DataEntity]:
        """
        Main scraping method
        """
        bt.logging.info(f"🎭 Starting Playwright scraping (Cost: $0.00)")
        
        try:
            # Initialize browser
            await self._init_browser()
            
            entities = []
            
            # Get zipcodes to scrape
            zipcodes_to_scrape = []
            if scrape_config.labels:
                zipcodes_to_scrape = [label.value for label in scrape_config.labels]
            else:
                zipcodes_to_scrape = [z['zipcode'] for z in self.zipcodes[:10]]
            
            bt.logging.info(f"Scraping {len(zipcodes_to_scrape)} zipcodes: {zipcodes_to_scrape[:5]}...")
            
            for zipcode in zipcodes_to_scrape:
                try:
                    # Scrape properties for this zipcode
                    properties = await self._scrape_zipcode(zipcode)
                    
                    bt.logging.info(f"Zipcode {zipcode}: Found {len(properties)} properties")
                    
                    # Convert to DataEntity
                    for prop_data in properties:
                        entity = self._create_data_entity(prop_data, zipcode)
                        if entity:
                            entities.append(entity)
                    
                    # Check entity limit
                    if scrape_config.entity_limit and len(entities) >= scrape_config.entity_limit:
                        bt.logging.info(f"Reached entity limit: {scrape_config.entity_limit}")
                        break
                    
                    # Delay between zipcodes
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    bt.logging.error(f"Error scraping zipcode {zipcode}: {e}")
                    self.stats['errors'] += 1
                    continue
            
            bt.logging.success(
                f"🎭 Playwright scraping complete! "
                f"Scraped {len(entities)} properties. Cost: $0.00 💰"
            )
            
            return entities
            
        finally:
            # Always close browser
            await self._close_browser()
    
    async def _scrape_zipcode(self, zipcode: str) -> List[dict]:
        """Scrape sold properties for a zipcode"""
        await self._rate_limit()
        
        page: Page = await self.context.new_page()
        
        try:
            url = f"https://www.zillow.com/homes/recently_sold/{zipcode}_rb/"
            
            bt.logging.debug(f"Navigating to: {url}")
            
            # Navigate to page (don't wait for networkidle - can timeout)
            try:
                response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                self.stats['requests'] += 1
                
                if response and response.status >= 400:
                    bt.logging.warning(f"Got status {response.status} for {zipcode}")
                    return []
            except Exception as e:
                bt.logging.warning(f"Page load warning for {zipcode}: {e}")
                # Continue anyway - page might have partially loaded
            
            # Wait for content to load
            bt.logging.debug("Waiting for page content...")
            await page.wait_for_timeout(5000)  # Give it time to render
            
            # Take screenshot for debugging (save to /tmp/)
            try:
                screenshot_path = f"/tmp/zillow_{zipcode}.png"
                await page.screenshot(path=screenshot_path)
                bt.logging.debug(f"Screenshot saved to {screenshot_path}")
            except:
                pass
            
            # Check for CAPTCHA
            captcha = await page.query_selector('text=Press & Hold')
            if captcha:
                bt.logging.warning(f"CAPTCHA detected for {zipcode}. Please solve manually or use CAPTCHA solving service.")
                if not self.headless:
                    bt.logging.info("Waiting 30 seconds for you to solve CAPTCHA...")
                    await page.wait_for_timeout(30000)
                else:
                    return []
            
            # Extract property data from page
            properties = await self._extract_properties_from_page(page, zipcode)
            
            return properties
            
        except Exception as e:
            bt.logging.error(f"Error navigating to {zipcode}: {e}")
            return []
            
        finally:
            await page.close()
    
    async def _extract_properties_from_page(self, page: Page, zipcode: str) -> List[dict]:
        """Extract property data from the page"""
        properties = []
        
        try:
            # Method 1: Extract from embedded JSON in script tags
            scripts = await page.query_selector_all('script[type="application/json"]')
            
            for script in scripts:
                try:
                    content = await script.inner_text()
                    data = json.loads(content)
                    
                    if isinstance(data, dict):
                        # Look for search results
                        results = (
                            data.get('searchPageState', {})
                            .get('cat1', {})
                            .get('searchResults', {})
                            .get('mapResults', [])
                        )
                        
                        if results:
                            bt.logging.info(f"Found {len(results)} properties in embedded JSON")
                            
                            for prop in results:
                                prop_dict = self._parse_property_data(prop, zipcode)
                                if prop_dict:
                                    properties.append(prop_dict)
                                    self.stats['properties_scraped'] += 1
                            
                            break  # Found data, no need to check more scripts
                
                except (json.JSONDecodeError, KeyError, AttributeError) as e:
                    bt.logging.debug(f"Script parsing error: {e}")
                    continue
            
            # Method 2: If no JSON found, try scraping visible cards (fallback)
            if not properties:
                bt.logging.debug("No JSON data found, trying to scrape visible cards...")
                cards = await page.query_selector_all('article[data-test="property-card"]')
                
                for card in cards[:20]:  # Limit to first 20 visible
                    try:
                        prop_dict = await self._parse_property_card(card, zipcode)
                        if prop_dict:
                            properties.append(prop_dict)
                            self.stats['properties_scraped'] += 1
                    except Exception as e:
                        bt.logging.debug(f"Card parsing error: {e}")
                        continue
        
        except Exception as e:
            bt.logging.error(f"Error extracting properties: {e}")
        
        return properties
    
    async def _parse_property_card(self, card, zipcode: str) -> Optional[dict]:
        """Parse a property card from the page"""
        try:
            # Extract link
            link = await card.query_selector('a[data-test="property-card-link"]')
            if not link:
                return None
            
            href = await link.get_attribute('href')
            if not href:
                return None
            
            # Extract zpid from URL
            zpid = None
            if '_zpid' in href:
                zpid = href.split('/')[-2].replace('_zpid', '')
            
            # Extract address
            address_elem = await card.query_selector('address')
            address = await address_elem.inner_text() if address_elem else None
            
            # Extract price
            price_elem = await card.query_selector('[data-test="property-card-price"]')
            price_text = await price_elem.inner_text() if price_elem else None
            price = None
            if price_text:
                # Remove $, commas, and convert to int
                price = int(price_text.replace('$', '').replace(',', '').split()[0])
            
            if not zpid or not address or not price:
                return None
            
            return {
                'zpid': zpid,
                'address': address,
                'zipcode': zipcode,
                'price': price,
                'url': f"https://www.zillow.com{href}",
                'scraped_at': datetime.now(timezone.utc).isoformat(),
            }
        
        except Exception as e:
            bt.logging.debug(f"Error parsing card: {e}")
            return None
    
    def _parse_property_data(self, prop: dict, zipcode: str) -> Optional[dict]:
        """Parse property data from API response (same as curl-cffi version)"""
        try:
            zpid = str(prop.get('zpid', ''))
            if not zpid:
                return None
            
            address = prop.get('address', '')
            if not address:
                return None
            
            price = prop.get('price')
            if not price:
                hdp_data = prop.get('hdpData', {})
                price = hdp_data.get('homeInfo', {}).get('price')
            
            if not price:
                return None
            
            bedrooms = prop.get('bedrooms') or prop.get('beds')
            bathrooms = prop.get('bathrooms') or prop.get('baths')
            sqft = prop.get('area') or prop.get('livingArea')
            
            return {
                'zpid': zpid,
                'address': address,
                'city': prop.get('addressCity', ''),
                'state': prop.get('addressState', ''),
                'zipcode': zipcode,
                'price': int(price),
                'bedrooms': int(bedrooms) if bedrooms else None,
                'bathrooms': float(bathrooms) if bathrooms else None,
                'sqft': int(sqft) if sqft else None,
                'property_type': prop.get('homeType', 'SINGLE_FAMILY'),
                'latitude': prop.get('latLong', {}).get('latitude'),
                'longitude': prop.get('latLong', {}).get('longitude'),
                'url': f"https://www.zillow.com/homedetails/{zpid}_zpid/",
                'scraped_at': datetime.now(timezone.utc).isoformat(),
            }
        
        except Exception as e:
            bt.logging.debug(f"Error parsing property: {e}")
            return None
    
    def _create_data_entity(self, prop_data: dict, zipcode: str) -> Optional[DataEntity]:
        """Convert property data to DataEntity (same as curl-cffi version)"""
        try:
            schema = PropertyDataSchema()
            
            schema.metadata.miner_hot_key = os.getenv('MINER_HOTKEY', 'unknown')
            schema.ids.zillow.zpid = int(prop_data.get('zpid', 0)) if prop_data.get('zpid') else None
            
            schema.property.location.addresses = prop_data.get('address')
            schema.property.location.city = prop_data.get('city')
            schema.property.location.state = prop_data.get('state')
            schema.property.location.zip_code = zipcode
            schema.property.location.latitude = prop_data.get('latitude')
            schema.property.location.longitude = prop_data.get('longitude')
            
            schema.property.features.bedrooms = prop_data.get('bedrooms')
            schema.property.features.bathrooms = prop_data.get('bathrooms')
            schema.property.characteristics.property_type = prop_data.get('property_type')
            schema.property.size.house_size_sqft = prop_data.get('sqft')
            
            sale_price = prop_data.get('price')
            if sale_price:
                sale_record = {
                    'date': prop_data.get('scraped_at', datetime.now(timezone.utc).isoformat()),
                    'value': float(sale_price),
                    'transaction_type': 'sold',
                    'source': 'playwright_scraper'
                }
                schema.home_sales.sales_history = [sale_record]
            
            schema.market_context.final_sale_price = float(sale_price) if sale_price else None
            schema.market_context.sale_date = prop_data.get('scraped_at')
            
            content = schema.model_dump_json()
            content_bytes = content.encode('utf-8')
            
            entity = DataEntity(
                uri=prop_data.get('url', f"https://zillow.com/{prop_data.get('zpid')}"),
                datetime=datetime.now(timezone.utc),
                source=DataSource.SZILL_VALI,
                label=DataLabel(value=zipcode),
                content=content_bytes,
                content_size_bytes=len(content_bytes),
            )
            
            return entity
        
        except Exception as e:
            bt.logging.error(f"Error creating DataEntity: {e}")
            return None
    
    async def validate(self, entities: List[DataEntity]) -> List[ValidationResult]:
        """Validate scraped entities"""
        results = []
        
        for entity in entities:
            try:
                is_valid = (
                    entity.uri and
                    entity.content and
                    len(entity.content) > 0 and
                    entity.label
                )
                
                results.append(ValidationResult(
                    is_valid=is_valid,
                    content_size_bytes_validated=entity.content_size_bytes,
                    reason="Valid" if is_valid else "Missing required fields"
                ))
            
            except Exception as e:
                results.append(ValidationResult(
                    is_valid=False,
                    content_size_bytes_validated=0,
                    reason=f"Validation error: {e}"
                ))
        
        return results
    
    async def _rate_limit(self):
        """Apply rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _load_zipcodes(self, zipcodes_file: Path) -> List[dict]:
        """Load zipcodes from CSV"""
        zipcodes = []
        
        try:
            with open(zipcodes_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    zipcodes.append({
                        'zipcode': row['RegionName'],
                        'city': row['City'],
                        'state': row['State'],
                        'size_rank': int(row['SizeRank'])
                    })
        except Exception as e:
            bt.logging.error(f"Error loading zipcodes: {e}")
        
        return zipcodes
    
    def get_stats(self) -> dict:
        """Get scraping statistics"""
        return {
            **self.stats,
            'scraper_type': 'Playwright (Real Browser)',
            'cost_savings': 'FREE! Using real browser automation 🎭'
        }


# Factory function
def create_playwright_scraper(proxy_url: str = None, headless: bool = True) -> ZillowPlaywrightScraper:
    """
    Create Playwright scraper instance
    
    Args:
        proxy_url: Optional proxy URL
        headless: Run in headless mode (True = no visible browser)
        
    Returns:
        Configured Playwright scraper
    """
    return ZillowPlaywrightScraper(proxy_url=proxy_url, headless=headless)


# USAGE EXAMPLE
"""
How to use in your miner:

1. Import:
```python
from scraping.custom.zillow_playwright_scraper import create_playwright_scraper
```

2. Create scraper:
```python
# With proxy
scraper = create_playwright_scraper(
    proxy_url="http://user:pass@host:port",
    headless=True  # False to see browser (useful for debugging/CAPTCHAs)
)

# Without proxy (try this first!)
scraper = create_playwright_scraper(headless=True)
```

3. Use it:
```python
entities = await scraper.scrape(scrape_config)
```

ADVANTAGES over curl-cffi:
- ✅ Real browser = harder to detect
- ✅ Can solve CAPTCHAs (set headless=False)
- ✅ Better success rate
- ✅ Still FREE!

DISADVANTAGES:
- ❌ Slower than curl-cffi
- ❌ Uses more memory/CPU
- ❌ Needs browser binaries installed

Cost: $0/month 💰
"""

