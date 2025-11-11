#!/usr/bin/env python3
"""Test different Redfin API parameters to get ONLY sold properties"""

from curl_cffi import requests
import json

def test_filter(status_val, uipt_val, description):
    """Test different API parameters"""
    print(f"\n{'='*70}")
    print(f"🧪 Testing: {description}")
    print(f"   status={status_val}, uipt={uipt_val}")
    print('='*70)
    
    url = "https://www.redfin.com/stingray/api/gis"
    params = {
        'al': '1',
        'market': 'national',
        'num_homes': '350',
        'region_id': '3243',  # 10001 zipcode
        'region_type': '2',
        'sold_within_days': '1095',
        'status': status_val,
        'uipt': uipt_val,
        'v': '8'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.redfin.com/zipcode/10001/filter/include=sold-3yr'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, 
                               impersonate='chrome110', timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error: Status {response.status_code}")
            return
        
        text = response.text
        if text.startswith('{}&&'):
            text = text[4:]
        
        data = json.loads(text)
        homes = data.get('payload', {}).get('homes', [])
        
        # Analyze statuses
        sold_count = sum(1 for h in homes if h.get('soldDate'))
        active_count = sum(1 for h in homes if h.get('searchStatus') == 1)
        
        print(f"📊 Total properties: {len(homes)}")
        print(f"   ✅ SOLD (with soldDate): {sold_count}")
        print(f"   🏠 ACTIVE: {active_count}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔍 TESTING REDFIN API FILTERS FOR SOLD PROPERTIES")
    print("="*70)
    
    # Test different status values
    # From Redfin docs/observations:
    # status: 1=for sale, 2=for rent, 3=sold, 9=all
    
    test_filter('9', '1,2,3,4,5,6,7,8', 'Current (status=9, all types)')
    test_filter('3', '1,2,3,4,5,6,7,8', 'Sold only (status=3, all types)')
    test_filter('1', '1,2,3,4,5,6,7,8', 'For sale only (status=1, all types)')
    
    print("\n" + "="*70)
    print("✅ RECOMMENDATION:")
    print("="*70)
    print("Use status=3 for SOLD properties only!")
    print("="*70 + "\n")

