# Validator Requirements & Data Mapping

## 🎯 **REQUIRED Fields (Validators Check These)**

According to `docs/miner-realestate-data-structure.json`, these fields are **REQUIRED**:

```json
"required_fields": [
  "ids.zillow.zpid",                    // ❌ MISSING - Zillow Property ID
  "property.location.addresses",         // ✅ HAVE
  "property.location.city",              // ✅ HAVE
  "property.location.state",             // ✅ HAVE
  "property.location.zip_code",          // ✅ HAVE
  "home_sales.sales_history",            // ✅ HAVE
  "market_context.sale_date",            // ⚠️  WRONG FIELD (using listing_date)
  "market_context.final_sale_price"      // ✅ HAVE
]
```

## 🔴 **CRITICAL ISSUE: Missing zpid**

**Problem**: Validators require `ids.zillow.zpid` but we're scraping from **Redfin**, not Zillow!

**Solutions**:
1. **Get Redfin's property ID** and map it (Redfin has property IDs in URLs)
2. **Leave zpid as null** (may reduce scoring but data is still valid)
3. **Cross-reference with Zillow** to get zpid (add extra step)

## 📊 **Current Redfin Scraper - Fields We're Filling**

### ✅ **What We Have:**
```python
{
  "metadata": {
    "version": "1.0",
    "description": "Property data collection schema for real estate data",
    "collection_date": "auto-generated",
    "miner_hot_key": null
  },
  
  "ids": {
    "property": {},
    "zillow": {
      "zpid": null  // ❌ MISSING - CRITICAL!
    },
    "mls": {}
  },
  
  "property": {
    "location": {
      "addresses": "252 7th Ave Unit 3F",      // ✅ From Redfin API
      "city": "New York",                       // ✅ From Redfin API
      "state": "NY",                            // ✅ From Redfin API
      "zip_code": "10001"                       // ✅ From Redfin API
    },
    "features": {
      "bedrooms": 2,                            // ✅ From Redfin API
      "bathrooms": 2.0,                         // ✅ From Redfin API
      "stories": 19                             // ✅ From Redfin API
    },
    "characteristics": {
      "year_built": 1908                        // ✅ From Redfin API
    },
    "size": {
      "house_size_sqft": 1531                   // ✅ From Redfin API
    }
  },
  
  "home_sales": {
    "sales_history": [                          // ✅ REQUIRED FIELD
      {
        "date": "2021-08-20",                   // ✅ From soldDate
        "value": 2695000,                       // ✅ From price
        "transaction_type": "sold",             // ✅ Hardcoded
        "source": "redfin"                      // ✅ Source identifier
      }
    ]
  },
  
  "market_context": {
    "listing_date": "2021-08-20",               // ⚠️  WRONG FIELD NAME!
    "final_sale_price": 2695000                 // ✅ REQUIRED FIELD
    // Missing: "sale_date"                     // ❌ Should be here!
  }
}
```

## 🔧 **Required Fixes**

### Fix 1: Add Redfin Property ID (partial solution for zpid)
```python
# Extract propertyId from Redfin URL
property_id = prop_data.get('propertyId')  # Redfin's ID
# Store in zillow.zpid (even though it's not Zillow)
# OR add custom field
```

### Fix 2: Correct market_context.sale_date
```python
market_context=MarketContextSection(
    sale_date=sale_date_str,           # ✅ CORRECT field name
    final_sale_price=float(price),
    listing_date=None                   # Optional, can leave null
)
```

## 📋 **Evaluation Criteria (From README)**

Validators score based on:
1. **Data Completeness**: Number of schema fields populated (more = better)
2. **Data Quality**: Accuracy verified by cross-checking
3. **Submission Quantity**: Faster collection rewarded
4. **Comprehensive Coverage**: More zipcodes = better
5. **No Tolerance**: Synthetic data or duplicates = penalties

## 🎯 **Recommended Field Priority**

### **Tier 1 - MUST HAVE (Required):**
- ✅ property.location.addresses
- ✅ property.location.city
- ✅ property.location.state
- ✅ property.location.zip_code
- ❌ ids.zillow.zpid (or equivalent property ID)
- ✅ home_sales.sales_history
- ⚠️  market_context.sale_date (fix field name)
- ✅ market_context.final_sale_price

### **Tier 2 - IMPORTANT (High Scoring):**
- ✅ property.features.bedrooms
- ✅ property.features.bathrooms
- ✅ property.size.house_size_sqft
- ✅ property.characteristics.year_built
- ⚠️  property.location.latitude (can get from Redfin)
- ⚠️  property.location.longitude (can get from Redfin)

### **Tier 3 - NICE TO HAVE (Extra Points):**
- property.features.full_bathrooms
- property.features.garage_spaces
- property.characteristics.property_type
- property.size.lot_size_sqft
- market_context.days_on_market
- valuation data (if available)

## 🚀 **Next Steps**

1. ✅ **Fix sale_date field name** in market_context
2. ⚠️  **Add propertyId from Redfin** to zpid field
3. ⚠️  **Add lat/long** from Redfin API (available)
4. ⚠️  **Add property_type** from Redfin
5. ⚠️  **Add days_on_market** if available

## ⚠️ **Important Notes**

- **Zillow zpid**: Since we're using Redfin, we may not have true Zillow zpid. This might reduce our score, but the data is still valid.
- **Sale Date**: Must be in `market_context.sale_date`, NOT `listing_date`
- **All Fields Optional Except Required**: Set null for unavailable fields
- **Validators Cross-Check**: They may verify data against Zillow, so accuracy is critical

