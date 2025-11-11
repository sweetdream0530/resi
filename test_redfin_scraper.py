#!/usr/bin/env python3
"""
Test Redfin Scraper - EASIER than Zillow!
"""

import asyncio
import sys
import datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bittensor as bt
from scraping.custom.redfin_scraper import create_redfin_scraper
from scraping.scraper import ScrapeConfig
from common.date_range import DateRange
from common.data import DataLabel


async def test_redfin():
    """Test Redfin scraper"""
    
    print("=" * 60)
    print("🏠 REDFIN SCRAPER TEST (Easier than Zillow!)")
    print("=" * 60)
    print()
    
    bt.logging.set_trace(True)
    bt.logging.set_debug(True)
    
    print("Creating Redfin scraper...")
    scraper = create_redfin_scraper(headless=True)
    print("✅ Scraper created!")
    print()
    
    test_zipcodes = [
        "90210",  # Beverly Hills
        "10001",  # NYC
    ]
    
    print(f"Testing with zipcodes: {test_zipcodes}")
    print()
    
    config = ScrapeConfig(
        entity_limit=20,
        date_range=DateRange(
            start=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=365),
            end=dt.datetime.now(dt.timezone.utc)
        ),
        labels=[DataLabel(value=z) for z in test_zipcodes]
    )
    
    print("Starting scrape...")
    print("-" * 60)
    
    try:
        entities = await scraper.scrape(config)
        
        print("-" * 60)
        print()
        print("=" * 60)
        print("✅ SUCCESS!")
        print("=" * 60)
        print()
        print(f"📊 Results:")
        print(f"   - Properties: {len(entities)}")
        print(f"   - Cost: $0.00 💰")
        print()
        
        stats = scraper.get_stats()
        print(f"📈 Stats:")
        print(f"   - Requests: {stats['requests']}")
        print(f"   - Properties: {stats['properties_scraped']}")
        print(f"   - Errors: {stats['errors']}")
        print()
        
        if entities:
            print("📋 Sample Properties:")
            for i, entity in enumerate(entities[:3], 1):
                import json
                try:
                    content = json.loads(entity.content.decode('utf-8'))
                    address = content.get('property', {}).get('location', {}).get('addresses', 'Unknown')
                    price = content.get('market_context', {}).get('final_sale_price', 'Unknown')
                    print(f"   {i}. {address}")
                    print(f"      Price: ${price:,.0f}" if isinstance(price, (int, float)) else f"      Price: {price}")
                except Exception as e:
                    print(f"   {i}. [Parse error: {e}]")
            print()
        
        print("=" * 60)
        print("🎉 Redfin scraper works!")
        print("=" * 60)
        print()
        print("Why Redfin is better:")
        print("✅ Less aggressive anti-bot protection")
        print("✅ No proxy needed (usually)")
        print("✅ Still FREE!")
        print("✅ Good property data")
        print()
        
    except Exception as e:
        print("-" * 60)
        print()
        print("❌ FAILED")
        print(f"Error: {e}")
        print()
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_redfin())

