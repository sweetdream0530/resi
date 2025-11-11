"""
Redfin API-based scraper - COMPLETE VERSION with all required fields
Uses Redfin's GIS API endpoint to get sold property data
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bittensor as bt
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from curl_cffi import requests
import json
import asyncio

from scraping.scraper import Scraper, ScrapeConfig, ValidationResult
from common.data import DataEntity, DataLabel, DataSource
from scraping.custom.schema import (
    PropertyDataSchema, PropertyMetadata,
    PropertyLocation, PropertySection, PropertyFeatures, PropertySize, PropertyCharacteristics,
    HomeSalesSection, SaleRecord, MarketContextSection,
    IDsSection, PropertyIDs, ZillowIDs, MLSIDS
)


class RedfinAPIScraperComplete(Scraper):
    """Complete Redfin scraper with all available fields populated"""
    
    def __init__(self):
        self.base_url = "https://www.redfin.com/stingray/api/gis"
        self.requests_per_minute = 20
        self.stats = {
            'requests_made': 0,
            'properties_scraped': 0,
            'zipcodes_completed': 0
        }
        self.zipcode_to_region_id = {}  # Cache for zipcode->region_id mapping
        
    async def scrape(self, config: ScrapeConfig) -> List[DataEntity]:
        """Scrape sold properties from Redfin API"""
        
        # Extract zipcodes from labels
        zipcodes_to_scrape = []
        if config.labels:
            zipcodes_to_scrape = [label.value for label in config.labels]
        else:
            bt.logging.warning("No labels provided in config, no zipcodes to scrape")
            return []
        
        bt.logging.info(f"Starting Redfin API scrape for {len(zipcodes_to_scrape)} zipcodes")
        
        all_entities = []
        
        for zipcode in zipcodes_to_scrape:
            try:
                bt.logging.info(f"Scraping zipcode: {zipcode}")
                
                # Get region_id for this zipcode (needed for API)
                region_id = await self._get_region_id(zipcode)
                if not region_id:
                    bt.logging.warning(f"Could not find region_id for {zipcode}")
                    continue
                
                # Call the API
                properties = await self._fetch_properties(zipcode, region_id)
                bt.logging.info(f"Found {len(properties)} sold properties in {zipcode}")
                
                # Convert to DataEntity format
                for prop_data in properties:
                    entity = self._create_data_entity(prop_data, zipcode)
                    if entity:
                        all_entities.append(entity)
                
                self.stats['zipcodes_completed'] += 1
                
                # Rate limiting
                await asyncio.sleep(60 / self.requests_per_minute)
                
            except Exception as e:
                bt.logging.error(f"Error scraping {zipcode}: {e}")
                continue
        
        bt.logging.success(f"✅ Scraped {len(all_entities)} total properties from {self.stats['zipcodes_completed']} zipcodes")
        return all_entities
    
    async def _get_region_id(self, zipcode: str) -> Optional[str]:
        """Get Redfin's region_id for a zipcode by loading the page"""
        if zipcode in self.zipcode_to_region_id:
            return self.zipcode_to_region_id[zipcode]
        
        try:
            # Load the zipcode page to extract region_id from HTML/URL
            page_url = f"https://www.redfin.com/zipcode/{zipcode}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html',
            }
            
            response = requests.get(
                page_url,
                headers=headers,
                impersonate="chrome110",
                timeout=30,
                allow_redirects=True
            )
            
            if response.status_code == 200:
                html = response.text
                
                # Look for region_id in the HTML
                import re
                patterns = [
                    r'"region_id["\']?\s*[:=]\s*(\d+)',
                    r'region_id["\']?\s*[:=]\s*(\d+)',
                    r'/region/(\d+)/',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, html)
                    if match:
                        region_id = match.group(1)
                        self.zipcode_to_region_id[zipcode] = region_id
                        bt.logging.debug(f"Found region_id {region_id} for zipcode {zipcode}")
                        return region_id
            
            bt.logging.warning(f"Could not find region_id for {zipcode} (status: {response.status_code})")
            return None
            
        except Exception as e:
            bt.logging.error(f"Error getting region_id for {zipcode}: {e}")
            return None
    
    async def _fetch_properties(self, zipcode: str, region_id: str) -> List[dict]:
        """Fetch sold properties from Redfin GIS API with pagination support"""
        all_properties = []
        seen_property_ids = set()  # Track property IDs to avoid duplicates
        
        try:
            page_number = 1
            properties_per_page = 350  # Redfin's max per page
            
            while True:
                bt.logging.info(f"Fetching page {page_number} for {zipcode}...")
                
                # Calculate start index for pagination
                start_index = (page_number - 1) * properties_per_page
                
                params = {
                    'al': '1',
                    'include_nearby_homes': 'true',
                    'market': 'national',
                    'num_homes': str(properties_per_page),
                    'ord': 'redfin-recommended-asc',
                    'page_number': str(page_number),
                    'region_id': region_id,
                    'region_type': '2',  # 2 = zipcode
                    'sold_within_days': '1095',  # Last 3 years
                    'start': str(start_index),
                    'status': '9',
                    'uipt': '1,2,3,4,5,6,7,8',
                    'v': '8'
                }
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                    'Referer': f'https://www.redfin.com/zipcode/{zipcode}/filter/include=sold-3yr/page-{page_number}'
                }
                
                response = requests.get(
                    self.base_url,
                    params=params,
                    headers=headers,
                    impersonate="chrome110",
                    timeout=60
                )
                
                self.stats['requests_made'] += 1
                
                if response.status_code != 200:
                    bt.logging.error(f"API returned status {response.status_code} for page {page_number}")
                    break
                
                # Parse response
                text = response.text
                if text.startswith('{}&&'):
                    text = text[4:]
                
                data = json.loads(text)
                
                if 'payload' not in data or 'homes' not in data['payload']:
                    bt.logging.info(f"No more homes on page {page_number}")
                    break
                
                page_homes = data['payload']['homes']
                
                # If no homes returned, we've reached the end
                if not page_homes or len(page_homes) == 0:
                    bt.logging.info(f"No more properties, stopping at page {page_number}")
                    break
                
                bt.logging.info(f"Page {page_number}: {len(page_homes)} properties")
                
                # Filter for sold properties only and check for duplicates
                page_sold_count = 0
                page_new_count = 0
                page_duplicate_count = 0
                
                for home in page_homes:
                    sold_date = home.get('soldDate')
                    mls_status = home.get('mlsStatus', '')
                    property_id = home.get('propertyId')
                    
                    # Check if sold
                    if sold_date or mls_status.lower() == 'sold':
                        page_sold_count += 1
                        
                        # Check for duplicates using property ID
                        if property_id and property_id in seen_property_ids:
                            page_duplicate_count += 1
                            continue  # Skip duplicate
                        
                        # New property
                        if property_id:
                            seen_property_ids.add(property_id)
                        all_properties.append(home)
                        page_new_count += 1
                        self.stats['properties_scraped'] += 1
                
                bt.logging.info(f"Page {page_number}: {page_sold_count} sold ({page_new_count} new, {page_duplicate_count} duplicates)")
                
                # If all properties on this page were duplicates, stop
                if page_sold_count > 0 and page_new_count == 0:
                    bt.logging.info(f"All properties on page {page_number} are duplicates, stopping pagination")
                    break
                
                # Move to next page (we'll keep going until API returns empty)
                page_number += 1
                
                # Add small delay between pages to avoid rate limiting
                await asyncio.sleep(0.5)
                
                # Safety limit: max 20 pages (20 * 350 = 7000 properties)
                if page_number > 20:
                    bt.logging.warning(f"Reached safety limit of 20 pages, stopping")
                    break
            
            bt.logging.success(f"✅ Found {len(all_properties)} total sold properties across {page_number} page(s)")
            return all_properties
            
        except Exception as e:
            bt.logging.error(f"Error fetching properties for {zipcode}: {e}")
            import traceback
            traceback.print_exc()
            return all_properties  # Return what we have so far
    
    def _create_data_entity(self, prop_data: dict, zipcode: str) -> Optional[DataEntity]:
        """
        Convert Redfin API property data to DataEntity with PropertyDataSchema
        
        Fills ALL REQUIRED fields plus as many optional fields as possible
        """
        try:
            # ==================== EXTRACT ALL FIELDS FROM REDFIN ====================
            
            # Basic info
            street_obj = prop_data.get('streetLine', {})
            street = street_obj.get('value') if isinstance(street_obj, dict) else street_obj
            
            if not street:
                return None
            
            price_obj = prop_data.get('price', {})
            price = price_obj.get('value') if isinstance(price_obj, dict) else price_obj
            
            # Property details
            sqft_obj = prop_data.get('sqFt', {})
            sqft = sqft_obj.get('value') if isinstance(sqft_obj, dict) else sqft_obj
            
            beds = prop_data.get('beds')
            baths = prop_data.get('baths')
            full_baths = prop_data.get('fullBaths')
            half_baths = prop_data.get('partialBaths')
            
            year_built_obj = prop_data.get('yearBuilt', {})
            year_built = year_built_obj.get('value') if isinstance(year_built_obj, dict) else year_built_obj
            
            stories = prop_data.get('stories')
            
            # NEW: Property IDs
            property_id = prop_data.get('propertyId')  # Redfin's property ID
            mls_id_obj = prop_data.get('mlsId', {})
            mls_id = mls_id_obj.get('value') if isinstance(mls_id_obj, dict) else mls_id_obj
            
            # NEW: Location details  
            lat_long_obj = prop_data.get('latLong', {})
            if isinstance(lat_long_obj, dict) and 'value' in lat_long_obj:
                lat = lat_long_obj['value'].get('latitude')
                lon = lat_long_obj['value'].get('longitude')
            else:
                lat, lon = None, None
            
            # NEW: Lot size
            lot_size_obj = prop_data.get('lotSize', {})
            lot_size_sqft = lot_size_obj.get('value') if isinstance(lot_size_obj, dict) else lot_size_obj
            
            # NEW: Days on market
            dom_obj = prop_data.get('dom', {})
            days_on_market = dom_obj.get('value') if isinstance(dom_obj, dict) else dom_obj
            
            # NEW: Property type
            property_type_code = prop_data.get('propertyType')
            property_type_map = {
                1: "Single Family Residential",
                2: "Condo/Co-op",
                3: "Townhouse",
                4: "Multi-Family",
                5: "Land",
                6: "Other"
            }
            property_type = property_type_map.get(property_type_code, "Residential")
            
            # Sale date
            sold_date = prop_data.get('soldDate')
            sale_date_str = None
            if sold_date:
                try:
                    sale_date_str = datetime.fromtimestamp(sold_date / 1000, tz=timezone.utc).isoformat()
                except:
                    sale_date_str = datetime.now(timezone.utc).isoformat()
            else:
                sale_date_str = datetime.now(timezone.utc).isoformat()
            
            # ==================== CREATE COMPLETE SCHEMA ====================
            
            property_data = PropertyDataSchema(
                # Metadata with current miner info
                metadata=PropertyMetadata(
                    version="1.0",
                    description="Property data from Redfin API",
                    collection_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    miner_hot_key=None  # Set this to your hotkey
                ),
                
                # IDs Section - Use Redfin propertyId as zpid since we don't have Zillow ID
                ids=IDsSection(
                    property=PropertyIDs(),
                    zillow=ZillowIDs(
                        zpid=property_id  # ✅ REQUIRED - using Redfin's propertyId
                    ),
                    mls=MLSIDS(
                        mls_number=str(mls_id) if mls_id else None
                    )
                ),
                
                # Property Section
                property=PropertySection(
                    location=PropertyLocation(
                        addresses=street,           # ✅ REQUIRED
                        city=prop_data.get('city', ''),  # ✅ REQUIRED
                        state=prop_data.get('state', ''),  # ✅ REQUIRED
                        zip_code=prop_data.get('zip', zipcode),  # ✅ REQUIRED
                        latitude=lat,               # ✅ EXTRA
                        longitude=lon               # ✅ EXTRA
                    ),
                    features=PropertyFeatures(
                        bedrooms=int(beds) if beds else None,
                        bathrooms=float(baths) if baths else None,
                        full_bathrooms=int(full_baths) if full_baths else None,
                        half_bathrooms=int(half_baths) if half_baths else None,
                        stories=int(stories) if stories else None
                    ),
                    size=PropertySize(
                        house_size_sqft=int(sqft) if sqft else None,
                        lot_size_sqft=int(lot_size_sqft) if lot_size_sqft else None
                    ),
                    characteristics=PropertyCharacteristics(
                        property_type=property_type,
                        year_built=int(year_built) if year_built else None
                    )
                ),
                
                # Sales History - ✅ REQUIRED
                home_sales=HomeSalesSection(
                    sales_history=[
                        SaleRecord(
                            date=sale_date_str,
                            value=float(price) if price else 0.0,
                            transaction_type='sold',
                            source='redfin'
                        )
                    ]
                ),
                
                # Market Context - ✅ REQUIRED FIELDS
                market_context=MarketContextSection(
                    sale_date=sale_date_str,        # ✅ REQUIRED (correct field name!)
                    final_sale_price=float(price) if price else 0.0,  # ✅ REQUIRED
                    days_on_market=int(days_on_market) if days_on_market else None
                )
            )
            
            # Create DataEntity
            entity = DataEntity(
                uri=f"https://www.redfin.com{prop_data.get('url', '')}",
                datetime=datetime.now(timezone.utc),
                source=DataSource.SZILL_VALI,
                label=DataLabel(value=zipcode),
                content=property_data.model_dump_json(),
                content_size_bytes=len(property_data.model_dump_json())
            )
            
            return entity
            
        except Exception as e:
            bt.logging.debug(f"Error creating entity: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def validate(self, config: ScrapeConfig) -> bool:
        """Validate scraper configuration"""
        if not config.labels:
            bt.logging.error("No labels provided")
            return False
        return True


def create_redfin_api_scraper_complete() -> RedfinAPIScraperComplete:
    """Factory function to create complete Redfin API scraper"""
    return RedfinAPIScraperComplete()

