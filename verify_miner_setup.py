#!/usr/bin/env python3
"""
Comprehensive miner setup verification script
Run this to ensure everything is configured correctly
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
from datetime import datetime, timedelta

def test_imports():
    """Test 1: Verify all imports work"""
    print("1️⃣  Testing imports...")
    try:
        from scraping.miner_provider import MinerScraperProvider
        from common.data import DataSource, DataLabel, DateRange
        from scraping.scraper import ScrapeConfig
        from scraping.custom.redfin_api_scraper_complete import create_redfin_api_scraper_complete
        print("   ✅ All imports successful")
        return True
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        return False


def test_scraper_registration():
    """Test 2: Verify scraper is registered"""
    print("\n2️⃣  Testing scraper registration...")
    try:
        from scraping.miner_provider import MinerScraperProvider
        from common.data import DataSource
        
        provider = MinerScraperProvider()
        scraper = provider.get(DataSource.SZILL_VALI)
        
        print(f"   ✅ Scraper registered: {scraper.__class__.__name__}")
        return True
    except Exception as e:
        print(f"   ❌ Registration error: {e}")
        return False


async def test_scraping():
    """Test 3: Verify scraping works"""
    print("\n3️⃣  Testing scraping functionality...")
    try:
        from scraping.custom.redfin_api_scraper_complete import create_redfin_api_scraper_complete
        from scraping.scraper import ScrapeConfig
        from common.data import DateRange, DataLabel
        
        scraper = create_redfin_api_scraper_complete()
        config = ScrapeConfig(
            entity_limit=100,
            date_range=DateRange(
                start=datetime.now() - timedelta(days=1095),
                end=datetime.now()
            ),
            labels=[DataLabel(value="90210")]  # Beverly Hills - usually has good data
        )
        
        print("   🔄 Scraping test zipcode 90210...")
        entities = await scraper.scrape(config)
        
        if len(entities) > 0:
            print(f"   ✅ Successfully scraped {len(entities)} properties")
            return True, entities
        else:
            print("   ⚠️  No properties scraped (may be API issue)")
            return False, []
    except Exception as e:
        print(f"   ❌ Scraping error: {e}")
        import traceback
        traceback.print_exc()
        return False, []


def test_data_format(entities):
    """Test 4: Verify data format is correct"""
    print("\n4️⃣  Testing data format...")
    
    if not entities:
        print("   ⚠️  No entities to test (skipped)")
        return True
    
    try:
        import json
        
        # Check first entity
        entity = entities[0]
        data = json.loads(entity.content)
        
        # Check required fields
        required_fields = [
            "ids.zillow.zpid",
            "property.location.addresses",
            "property.location.city",
            "property.location.state",
            "property.location.zip_code",
            "home_sales.sales_history",
            "market_context.sale_date",
            "market_context.final_sale_price"
        ]
        
        missing = []
        for field_path in required_fields:
            parts = field_path.split('.')
            current = data
            found = True
            
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    found = False
                    break
            
            if not found or current is None or (isinstance(current, list) and len(current) == 0):
                missing.append(field_path)
        
        if not missing:
            print(f"   ✅ All {len(required_fields)} required fields present")
            return True
        else:
            print(f"   ❌ Missing {len(missing)} required field(s):")
            for field in missing:
                print(f"      - {field}")
            return False
            
    except Exception as e:
        print(f"   ❌ Format validation error: {e}")
        return False


def test_miner_config():
    """Test 5: Check miner configuration file"""
    print("\n5️⃣  Checking miner configuration...")
    try:
        miner_file = Path(__file__).parent / "neurons" / "miner.py"
        if miner_file.exists():
            print(f"   ✅ Miner file found: {miner_file}")
            return True
        else:
            print(f"   ❌ Miner file not found: {miner_file}")
            return False
    except Exception as e:
        print(f"   ❌ Config check error: {e}")
        return False


async def run_all_tests():
    """Run all verification tests"""
    print("="*70)
    print("🔍 MINER SETUP VERIFICATION")
    print("="*70)
    
    results = []
    
    # Test 1: Imports
    results.append(test_imports())
    
    # Test 2: Registration
    results.append(test_scraper_registration())
    
    # Test 3: Scraping
    scrape_success, entities = await test_scraping()
    results.append(scrape_success)
    
    # Test 4: Data format
    results.append(test_data_format(entities))
    
    # Test 5: Miner config
    results.append(test_miner_config())
    
    # Summary
    print("\n" + "="*70)
    print("📊 VERIFICATION SUMMARY")
    print("="*70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nTests passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED!")
        print("\n🚀 Your miner is ready to run!")
        print("\nNext steps:")
        print("  1. Make sure you have a Bittensor wallet configured")
        print("  2. Run: python neurons/miner.py --netuid 51 --subtensor.network test --wallet.name YOUR_WALLET --wallet.hotkey YOUR_HOTKEY")
        print("  3. Monitor logs for scrape requests and scores")
        print("\n📖 See MINER_SETUP_GUIDE.md for detailed instructions")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        print("\n❌ Please fix the issues above before running your miner")
        print("\n🔧 Troubleshooting:")
        print("  - Check that virtual environment is activated")
        print("  - Run: pip install -r requirements.txt")
        print("  - Verify scraper is registered in scraping/miner_provider.py")
    
    print("="*70 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

