#!/usr/bin/env python3
"""
Quick Test Script for FREE Zillow Scraper
==========================================

This script tests the free scraper to make sure it works before integrating with your miner.

Usage:
    python test_free_scraper.py
"""

import asyncio
import sys
import datetime as dt
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import bittensor as bt
from scraping.custom.zillow_playwright_scraper import create_playwright_scraper
from scraping.scraper import ScrapeConfig
from common.date_range import DateRange
from common.data import DataLabel


async def test_free_scraper():
    """Test the Playwright scraper with a few zipcodes"""
    
    print("=" * 60)
    print("🎭 PLAYWRIGHT ZILLOW SCRAPER TEST")
    print("=" * 60)
    print()
    
    # Configure logging
    bt.logging.set_trace(True)
    bt.logging.set_debug(True)
    
    # Create Playwright scraper with proxy from environment
    proxy_url = os.getenv('PROXY_URL')
    if proxy_url:
        print("Creating Playwright scraper with proxy from .env...")
        print(f"Proxy: {proxy_url.split('@')[1] if '@' in proxy_url else proxy_url}")
        scraper = create_playwright_scraper(proxy_url=proxy_url, headless=True)
    else:
        print("Creating Playwright scraper without proxy...")
        print("(Set PROXY_URL in .env to use a proxy)")
        scraper = create_playwright_scraper(headless=True)
    print(f"✅ Scraper created successfully (Real Browser - FREE!)")
    print()
    
    # Test with a few zipcodes
    test_zipcodes = [
        "90210",  # Beverly Hills, CA
        "10001",  # NYC, NY
        "60601",  # Chicago, IL
    ]
    
    print(f"Testing with zipcodes: {test_zipcodes}")
    print()
    
    # Create scrape config
    config = ScrapeConfig(
        entity_limit=20,  # Just scrape a few to test
        date_range=DateRange(
            start=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=365),
            end=dt.datetime.now(dt.timezone.utc)
        ),
        labels=[DataLabel(value=zipcode) for zipcode in test_zipcodes]
    )
    
    print("Starting scrape...")
    print("-" * 60)
    
    try:
        # Run the scraper
        entities = await scraper.scrape(config)
        
        print("-" * 60)
        print()
        print("=" * 60)
        print("✅ TEST SUCCESSFUL!")
        print("=" * 60)
        print()
        print(f"📊 Results:")
        print(f"   - Properties scraped: {len(entities)}")
        print(f"   - Zipcodes tested: {len(test_zipcodes)}")
        print(f"   - Cost: $0.00 💰")
        print()
        
        # Show stats
        stats = scraper.get_stats()
        print(f"📈 Statistics:")
        print(f"   - Total requests: {stats['requests']}")
        print(f"   - Properties found: {stats['properties_scraped']}")
        print(f"   - Errors: {stats['errors']}")
        print(f"   - Total cost: ${stats['total_cost']:.2f}")
        print()
        
        # Show sample properties
        if entities:
            print(f"📋 Sample Properties:")
            for i, entity in enumerate(entities[:3], 1):
                import json
                try:
                    content = json.loads(entity.content.decode('utf-8'))
                    address = content.get('property', {}).get('location', {}).get('addresses', 'Unknown')
                    price = content.get('market_context', {}).get('final_sale_price', 'Unknown')
                    print(f"   {i}. {address}")
                    print(f"      Price: ${price:,.0f}" if isinstance(price, (int, float)) else f"      Price: {price}")
                    print(f"      URI: {entity.uri}")
                except Exception as e:
                    print(f"   {i}. [Could not parse entity: {e}]")
            print()
        
        print("=" * 60)
        print("🎉 Your Playwright scraper is working!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Use this in your miner by importing create_playwright_scraper")
        print("2. Update scraping/miner_provider.py to use this scraper")
        print("3. Start mining with FREE browser automation!")
        print()
        print("💰 Cost: $0/month (vs $54-270/month for paid APIs)")
        print("🎭 Uses real Chrome browser (much harder to detect)")
        print()
        
        return True
        
    except Exception as e:
        print("-" * 60)
        print()
        print("=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print()
        print(f"Error: {e}")
        print()
        print("Common issues:")
        print("1. CAPTCHA detected - Set headless=False to solve manually:")
        print("   scraper = create_playwright_scraper(proxy_url='...', headless=False)")
        print("2. Network connectivity - Check your internet connection")
        print("3. Rate limiting - Wait a few minutes and try again")
        print("4. Blocked by Zillow - Try with a proxy (set PROXY_URL in .env)")
        print()
        print("For help, see:")
        print("- ZILLOW_SCRAPING_CHALLENGES.md")
        print("- scraping/custom/zillow_playwright_scraper.py")
        print()
        
        import traceback
        print("Full error traceback:")
        print("-" * 60)
        traceback.print_exc()
        print("-" * 60)
        
        return False


async def test_with_visible_browser():
    """Test with visible browser (useful for debugging/CAPTCHAs)"""
    
    print()
    print("=" * 60)
    print("Testing with VISIBLE BROWSER")
    print("=" * 60)
    print()
    print("This will open a real Chrome window so you can see what's happening.")
    print("Useful for debugging or solving CAPTCHAs manually.")
    print()
    
    proxy_url = os.getenv('PROXY_URL')
    
    scraper = create_playwright_scraper(proxy_url=proxy_url, headless=False)
    
    config = ScrapeConfig(
        entity_limit=5,
        date_range=DateRange(
            start=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=365),
            end=dt.datetime.now(dt.timezone.utc)
        ),
        labels=[DataLabel(value="90210")]
    )
    
    try:
        entities = await scraper.scrape(config)
        print(f"✅ Visible browser test successful! Scraped {len(entities)} properties")
        return True
    except Exception as e:
        print(f"❌ Visible browser test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    
    # Test basic scraper
    success = asyncio.run(test_free_scraper())
    
    # If failed, offer visible browser test
    if not success:
        print()
        response = input("Would you like to test with a visible browser? (y/n): ").strip().lower()
        if response == 'y':
            asyncio.run(test_with_visible_browser())


if __name__ == "__main__":
    main()




