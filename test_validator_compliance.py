#!/usr/bin/env python3
"""
Test validator compliance - verify all REQUIRED fields are populated
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import json
import bittensor as bt
from scraping.custom.redfin_api_scraper_complete import create_redfin_api_scraper_complete
from scraping.scraper import ScrapeConfig
from datetime import datetime, timedelta
from common.data import DateRange, DataLabel


# REQUIRED FIELDS according to docs/miner-realestate-data-structure.json
REQUIRED_FIELDS = [
    "ids.zillow.zpid",
    "property.location.addresses",
    "property.location.city", 
    "property.location.state",
    "property.location.zip_code",
    "home_sales.sales_history",
    "market_context.sale_date",
    "market_context.final_sale_price"
]


def check_required_fields(data: dict) -> tuple:
    """Check if all required fields are present and not null"""
    missing = []
    present = []
    
    for field_path in REQUIRED_FIELDS:
        parts = field_path.split('.')
        current = data
        found = True
        
        try:
            for part in parts:
                if isinstance(current, dict):
                    if part in current:
                        current = current[part]
                    else:
                        found = False
                        break
                else:
                    found = False
                    break
            
            # Check if value is not null/empty
            if found:
                if current is None or current == '' or (isinstance(current, list) and len(current) == 0):
                    missing.append(field_path)
                else:
                    present.append(field_path)
            else:
                missing.append(field_path)
                
        except Exception as e:
            missing.append(field_path)
    
    return present, missing


async def test_validator_compliance():
    """Test that scraper produces validator-compliant data"""
    
    print("="*70)
    print("🔍 VALIDATOR COMPLIANCE TEST")
    print("="*70)
    print("\nTesting scraper against required fields...")
    print()
    
    scraper = create_redfin_api_scraper_complete()
    
    config = ScrapeConfig(
        entity_limit=10,
        date_range=DateRange(
            start=datetime.now() - timedelta(days=1095),
            end=datetime.now()
        ),
        labels=[DataLabel(value="10001")]  # NYC
    )
    
    print("🔄 Scraping properties...\n")
    entities = await scraper.scrape(config)
    
    if not entities:
        print("❌ No entities scraped!")
        return
    
    print(f"✅ Scraped {len(entities)} properties\n")
    print("="*70)
    print("CHECKING REQUIRED FIELDS")
    print("="*70)
    
    # Check first property in detail
    first_entity = entities[0]
    data = json.loads(first_entity.content)
    
    present, missing = check_required_fields(data)
    
    print(f"\n📊 Compliance Score: {len(present)}/{len(REQUIRED_FIELDS)} required fields")
    print()
    
    # Show status of each required field
    for field in REQUIRED_FIELDS:
        status = "✅" if field in present else "❌"
        
        # Get actual value
        parts = field.split('.')
        current = data
        value = None
        try:
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    current = None
                    break
            value = current
        except:
            value = None
        
        if field in present:
            if isinstance(value, str) and len(str(value)) > 50:
                value_str = str(value)[:47] + "..."
            elif isinstance(value, list):
                value_str = f"[{len(value)} item(s)]"
            else:
                value_str = str(value)
            print(f"  {status} {field}: {value_str}")
        else:
            print(f"  {status} {field}: MISSING or NULL")
    
    print()
    print("="*70)
    print("ADDITIONAL FIELDS (Nice to have)")
    print("="*70)
    
    # Check optional but valuable fields
    optional_fields = {
        "property.features.bedrooms": data.get('property', {}).get('features', {}).get('bedrooms'),
        "property.features.bathrooms": data.get('property', {}).get('features', {}).get('bathrooms'),
        "property.features.full_bathrooms": data.get('property', {}).get('features', {}).get('full_bathrooms'),
        "property.features.half_bathrooms": data.get('property', {}).get('features', {}).get('half_bathrooms'),
        "property.size.house_size_sqft": data.get('property', {}).get('size', {}).get('house_size_sqft'),
        "property.size.lot_size_sqft": data.get('property', {}).get('size', {}).get('lot_size_sqft'),
        "property.characteristics.year_built": data.get('property', {}).get('characteristics', {}).get('year_built'),
        "property.characteristics.property_type": data.get('property', {}).get('characteristics', {}).get('property_type'),
        "property.location.latitude": data.get('property', {}).get('location', {}).get('latitude'),
        "property.location.longitude": data.get('property', {}).get('location', {}).get('longitude'),
        "market_context.days_on_market": data.get('market_context', {}).get('days_on_market'),
        "ids.mls.mls_number": data.get('ids', {}).get('mls', {}).get('mls_number'),
    }
    
    for field, value in optional_fields.items():
        status = "✅" if value is not None else "⚠️"
        value_str = str(value) if value is not None else "Not available"
        print(f"  {status} {field}: {value_str}")
    
    print()
    print("="*70)
    print("SAMPLE PROPERTY DATA")
    print("="*70)
    
    # Show first property as example
    loc = data.get('property', {}).get('location', {})
    features = data.get('property', {}).get('features', {})
    size = data.get('property', {}).get('size', {})
    ids = data.get('ids', {}).get('zillow', {})
    mc = data.get('market_context', {})
    
    print(f"""
📍 Property Details:
   Address: {loc.get('addresses', 'N/A')}
   City: {loc.get('city', 'N/A')}, {loc.get('state', 'N/A')} {loc.get('zip_code', 'N/A')}
   Coordinates: ({loc.get('latitude', 'N/A')}, {loc.get('longitude', 'N/A')})
   
🏠 Features:
   Bedrooms: {features.get('bedrooms', 'N/A')}
   Bathrooms: {features.get('bathrooms', 'N/A')} ({features.get('full_bathrooms', 'N/A')} full, {features.get('half_bathrooms', 'N/A')} half)
   Square Feet: {size.get('house_size_sqft', 'N/A'):,} sqft
   Lot Size: {size.get('lot_size_sqft', 'N/A')} sqft
   
💰 Sale Info:
   Property ID (zpid): {ids.get('zpid', 'N/A')}
   Sale Date: {mc.get('sale_date', 'N/A')[:10] if mc.get('sale_date') else 'N/A'}
   Sale Price: ${mc.get('final_sale_price', 0):,.0f}
   Days on Market: {mc.get('days_on_market', 'N/A')}
   
🔗 Source: {first_entity.uri}
    """)
    
    print("="*70)
    
    if len(missing) == 0:
        print("✅ PASS: All required fields are present!")
        print("🎉 Scraper is VALIDATOR COMPLIANT")
    else:
        print(f"⚠️  WARNING: {len(missing)} required field(s) missing:")
        for field in missing:
            print(f"   - {field}")
        print("\n⚠️  This may result in lower scores from validators")
    
    print("="*70)


if __name__ == "__main__":
    asyncio.run(test_validator_compliance())

