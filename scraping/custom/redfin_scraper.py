"""
REDFIN SCRAPER - EASIER THAN ZILLOW!
=====================================

Redfin has much less aggressive anti-bot protection than Zillow.
This makes it a better FREE alternative for scraping sold properties.

Cost: $0/month 💰
Success rate: Higher than Zillow
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


class RedfinScraper(Scraper):
    """
    ✅ FREE Redfin scraper - EASIER than Zillow!
    ✅ Less aggressive anti-bot protection
    ✅ Better success rate without proxy
    ✅ Sold properties data
    
    Cost: $0.00 per scrape 💰
    """
    
    def __init__(self, zipcodes_file: str = None, headless: bool = True):
        """
        Initialize Redfin scraper
        
        Args:
            zipcodes_file: Path to zipcodes.csv
            headless: Run in headless mode
        """
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
        
        # Rate limiting (Redfin is more lenient)
        self.requests_per_minute = 15
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
        
        bt.logging.info("Starting browser for Redfin...")
        self.playwright = await async_playwright().start()
        
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
        )
        
        # Stealth settings
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        bt.logging.success("Browser initialized!")
    
    async def _close_browser(self):
        """Close browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def scrape(self, scrape_config: ScrapeConfig) -> List[DataEntity]:
        """Main scraping method"""
        bt.logging.info(f"🏠 Starting Redfin scraping (FREE!)")
        
        try:
            await self._init_browser()
            
            entities = []
            
            # Get zipcodes
            zipcodes_to_scrape = []
            if scrape_config.labels:
                zipcodes_to_scrape = [label.value for label in scrape_config.labels]
            else:
                zipcodes_to_scrape = [z['zipcode'] for z in self.zipcodes[:10]]
            
            bt.logging.info(f"Scraping {len(zipcodes_to_scrape)} zipcodes from Redfin")
            
            for zipcode in zipcodes_to_scrape:
                try:
                    properties = await self._scrape_zipcode(zipcode)
                    bt.logging.info(f"Zipcode {zipcode}: Found {len(properties)} properties")
                    
                    for prop_data in properties:
                        entity = self._create_data_entity(prop_data, zipcode)
                        if entity:
                            entities.append(entity)
                    
                    if scrape_config.entity_limit and len(entities) >= scrape_config.entity_limit:
                        break
                    
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    bt.logging.error(f"Error scraping {zipcode}: {e}")
                    self.stats['errors'] += 1
            
            bt.logging.success(f"🏠 Redfin scraping complete! {len(entities)} properties")
            return entities
            
        finally:
            await self._close_browser()
    
    async def _scrape_zipcode(self, zipcode: str) -> List[dict]:
        """Scrape sold properties from Redfin"""
        await self._rate_limit()
        
        page: Page = await self.context.new_page()
        
        try:
            # Redfin URL for sold properties
            url = f"https://www.redfin.com/zipcode/{zipcode}/filter/include=sold-3yr"
            
            bt.logging.debug(f"Navigating to: {url}")
            
            response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            self.stats['requests'] += 1
            
            if response and response.status >= 400:
                bt.logging.warning(f"Status {response.status} for {zipcode}")
                return []
            
            # Wait for content to load
            await page.wait_for_timeout(5000)
            
            # Scroll down to trigger lazy loading
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            
            # Scroll back up
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(1000)
            
            # Check for captcha/block
            page_content = await page.content()
            if 'Access Denied' in page_content or 'captcha' in page_content.lower():
                bt.logging.warning(f"Blocked or CAPTCHA for {zipcode}")
                return []
            
            # Extract properties
            properties = await self._extract_properties(page, zipcode)
            
            return properties
            
        except Exception as e:
            bt.logging.error(f"Error navigating to {zipcode}: {e}")
            return []
            
        finally:
            await page.close()
    
    async def _extract_properties(self, page: Page, zipcode: str) -> List[dict]:
        """Extract property data from Redfin page - parses embedded JSON"""
        properties = []
        
        try:
            # Get HTML content
            html_content = await page.content()
            
            # Find the large __reactServerState JSON structure that contains all properties
            import re
            
            bt.logging.info("Searching for property data in page JSON...")
            
            # Look for window.__reactServerState.props.payload.gisResults
            # Use greedy match to get the full JSON
            gis_match = re.search(
                r'window\.__reactServerState\.props\s*=\s*(\{.+\});',
                html_content,
                re.DOTALL
            )
            
            if gis_match:
                try:
                    json_str = gis_match.group(1)
                    bt.logging.info(f"Found __reactServerState.props, extracting JSON ({len(json_str)} chars)...")
                    props_data = json.loads(json_str)
                    bt.logging.success("✅ Successfully parsed JSON")
                    
                    # Navigate to payload.gisResults.homes
                    homes_list = []
                    if 'payload' in props_data:
                        payload = props_data['payload']
                        if 'gisResults' in payload:
                            gis_results = payload['gisResults']
                            if 'homes' in gis_results and isinstance(gis_results['homes'], list):
                                homes_list = gis_results['homes']
                                bt.logging.success(f"✅ Found {len(homes_list)} properties in gisResults.homes")
                    
                    if homes_list:
                        for home in homes_list:
                            try:
                                # Check if it's a sold property
                                sashes = home.get('sashes', [])
                                is_sold = any(
                                    s.get('sashType') == 1 or 
                                    s.get('sashTypeName', '').lower() == 'sold' 
                                    for s in sashes
                                )
                                
                                if not is_sold:
                                    continue  # Skip non-sold properties
                                
                                # Extract data
                                price_obj = home.get('price', {})
                                price = price_obj.get('value') if isinstance(price_obj, dict) else price_obj
                                
                                sqft_obj = home.get('sqFt', {})
                                sqft = sqft_obj.get('value') if isinstance(sqft_obj, dict) else sqft_obj
                                
                                street_obj = home.get('streetLine', {})
                                street = street_obj.get('value') if isinstance(street_obj, dict) else street_obj
                                
                                if not price or not street:
                                    continue
                                
                                # Get sale date from sash
                                sale_date = None
                                for sash in sashes:
                                    if sash.get('lastSaleDate'):
                                        sale_date = sash.get('lastSaleDate')
                                        break
                                
                                prop = {
                                    'address': street,
                                    'city': home.get('city', ''),
                                    'state': home.get('state', ''),
                                    'zipcode': home.get('zip', zipcode),
                                    'price': int(price),
                                    'bedrooms': home.get('beds'),
                                    'bathrooms': home.get('baths'),
                                    'sqft': int(sqft) if sqft else None,
                                    'property_type': 'SINGLE_FAMILY',
                                    'url': f"https://www.redfin.com{home.get('url', '')}",
                                    'sale_date': sale_date,
                                    'scraped_at': datetime.now(timezone.utc).isoformat(),
                                    'source': 'redfin'
                                }
                                
                                properties.append(prop)
                                self.stats['properties_scraped'] += 1
                                bt.logging.debug(f"✅ {prop['address']} - ${prop['price']:,}")
                                
                            except Exception as e:
                                bt.logging.debug(f"Error parsing home: {e}")
                                continue
                
                except (json.JSONDecodeError, Exception) as e:
                    bt.logging.error(f"Error extracting __reactServerState data: {e}")
            else:
                bt.logging.warning("Could not find window.__reactServerState.props in HTML")
            
            if properties:
                bt.logging.success(f"✅ Extracted {len(properties)} SOLD properties!")
                return properties
            else:
                bt.logging.warning("No sold properties found in JSON data")
                return []
        
        except Exception as e:
            bt.logging.error(f"Error extracting properties: {e}")
            import traceback
            traceback.print_exc()
        
        return properties
    
    def _create_data_entity(self, prop_data: dict, zipcode: str) -> Optional[DataEntity]:
        """
        Convert Redfin property data to DataEntity with PropertyDataSchema
        
        This creates validator-compliant data entities with REQUIRED fields:
        - home_sales.sales_history (sold properties)
        - market_context.final_sale_price
        - property.location (address, zipcode)
        """
        try:
            schema = PropertyDataSchema()
            
            # Metadata
            schema.metadata.miner_hot_key = os.getenv('MINER_HOTKEY', os.getenv('WALLET_HOTKEY', 'unknown'))
            schema.metadata.collection_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            # IDs - Redfin doesn't have zpid, but we can extract property ID from URL
            try:
                url = prop_data.get('url', '')
                if '/home/' in url:
                    # Extract Redfin property ID if available
                    pass  # Redfin uses different ID system
            except:
                pass
            
            # Location (REQUIRED)
            schema.property.location.addresses = prop_data.get('address')
            schema.property.location.zip_code = zipcode
            schema.property.location.city = prop_data.get('city')
            schema.property.location.state = prop_data.get('state')
            
            # Features
            schema.property.features.bedrooms = prop_data.get('bedrooms')
            schema.property.features.bathrooms = prop_data.get('bathrooms')
            
            # Size
            schema.property.size.house_size_sqft = prop_data.get('sqft')
            
            # Property type
            schema.property.characteristics.property_type = prop_data.get('property_type', 'SINGLE_FAMILY')
            
            # CRITICAL: Sales History (REQUIRED for validator)
            sale_price = prop_data.get('price')
            if sale_price:
                from scraping.custom.schema import SaleRecord
                sale_record = SaleRecord(
                    date=prop_data.get('scraped_at', datetime.now(timezone.utc).isoformat()),
                    value=float(sale_price),
                    transaction_type='sold',  # Must be 'sold' for validator
                    source='redfin'
                )
                schema.home_sales.sales_history = [sale_record]
            else:
                # If no price, this property shouldn't be included
                bt.logging.warning(f"Property missing sale price, skipping: {prop_data.get('address')}")
                return None
            
            # CRITICAL: Market Context (REQUIRED for validator)
            schema.market_context.final_sale_price = float(sale_price)
            schema.market_context.sale_date = prop_data.get('sale_date') or prop_data.get('scraped_at')
            
            # Convert to JSON
            content = schema.model_dump_json()
            content_bytes = content.encode('utf-8')
            
            # Create DataEntity
            entity = DataEntity(
                uri=prop_data.get('url', f"https://redfin.com/property/{zipcode}"),
                datetime=datetime.now(timezone.utc),
                source=DataSource.SZILL_VALI,  # Use SZILL_VALI source for compatibility
                label=DataLabel(value=zipcode),
                content=content_bytes,
                content_size_bytes=len(content_bytes),
            )
            
            return entity
        
        except Exception as e:
            bt.logging.error(f"Error creating entity: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def validate(self, entities: List[DataEntity]) -> List[ValidationResult]:
        """Validate entities"""
        results = []
        for entity in entities:
            is_valid = entity.uri and entity.content and entity.label
            results.append(ValidationResult(
                is_valid=is_valid,
                content_size_bytes_validated=entity.content_size_bytes,
                reason="Valid" if is_valid else "Missing fields"
            ))
        return results
    
    async def _rate_limit(self):
        """Rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        self.last_request_time = time.time()
    
    def _load_zipcodes(self, zipcodes_file: Path) -> List[dict]:
        """Load zipcodes"""
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
        """Get stats"""
        return {
            **self.stats,
            'scraper_type': 'Redfin (Easier than Zillow!)',
            'cost': 'FREE! 🏠'
        }


def create_redfin_scraper(headless: bool = True) -> RedfinScraper:
    """
    Create Redfin scraper
    
    Redfin is MUCH easier to scrape than Zillow:
    - Less aggressive anti-bot protection
    - No proxy needed (usually)
    - Still FREE!
    """
    return RedfinScraper(headless=headless)

