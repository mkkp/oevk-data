<!--
DOCUMENT METADATA
=================
Title: Impact Analysis - Allowing NULL House Numbers
Type: Analysis
Category: Feature
Status: Completed
Version: 1.0
Created: 2025-10-29
Last Updated: 2025-10-29
Author: System

Related Documents:
- Implementation (CHANGES_NULL_HOUSE_NUMBERS.md)
- Invalid Addresses Analysis (INVALID_ADDRESSES_ANALYSIS.md)

Related Code:
- src/etl/deduplicate.py (_clean_house_number, _format_full_address)

Dependencies:
- DuckDB for analysis queries

Keywords: impact-analysis, null-house-numbers, data-quality, validation, infrastructure-addresses, complex-buildings

Summary:
Comprehensive impact analysis of allowing addresses without house numbers (all-zero values). Analyzes 7,551 filtered addresses: 2,091 (28%) have building/staircase identifiers making them valid complex buildings, 4,660 (62%) are infrastructure addresses like railway stations and landmarks. Includes category breakdown, examples, recommendations, and implementation considerations for schema and validation changes.

Audience:
Product managers, data architects, developers deciding on address validation rules.
-->

# Impact Analysis: Allowing NULL House Numbers

**Date:** October 29, 2025  
**Issue:** Should addresses with house_number = "000000" (no house number) be considered valid?

---

## Current Situation

**Currently filtered out:** 7,551 addresses with all-zero house numbers
- **With building/staircase info:** 2,091 addresses (27.7%)
- **Without any additional info:** 4,660 addresses (61.7%)
- **With slash/range patterns:** 794 addresses (10.5%)

---

## Analysis by Address Category

### Category 1: Infrastructure & Landmarks (4,660 addresses)
**No house number, no building, no staircase**

Examples:
- Railway stations: "Vasútállomás", "MÁV pályaudvar" (96 cases)
- Gatekeeper houses: "Gátőrház" (63 cases)
- Industrial sites: "Tégla gyár" (brick factory)
- Landmarks: "Vajdahunyadvár" (castle)
- Areas: "Kültelek" (outskirts), "Szőlőhegy" (vineyard hill)
- Farms: "Tanya" (15 cases)

**Question:** Are these valid addresses?
- **Yes, they represent real locations** that voters are registered to
- They don't have house numbers because they're area-based addresses
- Examples: railway workers living at stations, farmers on unnamed farms

---

### Category 2: Complex Buildings (2,091 addresses)
**No house number, BUT have building/staircase identifiers**

Examples:
- "Gázgyári lakótelep 000000, Building: 0001, Staircase: 0001-0011" (89 cases)
- "József Attila lakótelep 000000, Building: A-G, Staircase: various"

**Question:** Are these valid addresses?
- **Yes, these are clearly valid!** They have specific building/staircase identifiers
- The lack of house number is a data format issue, not invalidity
- Full address: "Street Name, Building X, Staircase Y"

---

### Category 3: Range/Slash Patterns (794 addresses)
**House number like "000000/1152", "000020-", "000038-"**

Examples:
- "000000/1152" - building/unit number after slash
- "000020-" - incomplete range
- "000038-" - incomplete range

**Question:** Are these valid?
- **Partially valid** - patterns with actual numbers after slash/dash
- **Invalid** - incomplete ranges like "000020-" (ending with dash)

---

## Impact Assessment

### If We Keep Current Logic (Filter All-Zero House Numbers)

#### Lost Data:
1. **2,091 complex building addresses** - SIGNIFICANT LOSS
   - These have building/staircase info and are clearly valid
   - Example: "Gázgyári lakótelep, Building 1, Staircase 1"
   
2. **4,660 infrastructure/area addresses** - MODERATE LOSS
   - Railway stations, landmarks, farms
   - Valid locations but no street-level house numbers

#### Benefits:
- Clean data model (house_number NOT NULL)
- Simpler queries (no NULL handling needed)
- Clear address format

---

### If We Allow NULL House Numbers

#### Retained Data:
1. **All 7,551 currently filtered addresses** would be kept
2. **2,091 complex buildings** with full identifiers
3. **4,660 infrastructure addresses** for special locations

#### Impacts:

##### 1. Schema Changes Required

**PostgreSQL Schema:**
```sql
-- Current (would need to change):
house_number TEXT NOT NULL,

-- New (allow NULL):
house_number TEXT,  -- Can be NULL or empty
```

##### 2. Full Address Generation Logic

**Current Logic:**
```python
def _format_full_address(...):
    cleaned_house = self._clean_house_number(house_num)
    if cleaned_house is None:
        return None  # Invalid address
    # Build address with house number
```

**New Logic:**
```python
def _format_full_address(...):
    cleaned_house = self._clean_house_number(house_num)
    
    # Allow NULL/empty house number IF building/staircase exists
    if cleaned_house is None:
        if building or staircase:
            # Valid: "Street Name, Building X, Staircase Y"
            return format_without_house_number(...)
        else:
            # Valid for infrastructure: "Street Name" only
            return format_area_address(...)
```

##### 3. Deduplication Impact

**Current:** Addresses without house numbers → filtered out → not in dedup

**New:** Addresses without house numbers → kept → need deduplication

**Deduplication Hash:**
```python
# Current:
hash(street + house_number + building + staircase)

# New (if house_number is None):
hash(street + "" + building + staircase)  # Empty string for NULL
```

**Risk:** Multiple addresses at same street with no house number might collapse:
- "Railway Station, Building A" 
- "Railway Station, Building B"
- Both would need distinct building identifiers to avoid merging

##### 4. Geocoding Impact

**Challenge:** How to geocode addresses without house numbers?

**Options:**
1. **Street-level geocoding:**
   - "Kossuth utca" → geocode to street centroid
   - Accuracy: ±50-200 meters

2. **Settlement-level geocoding:**
   - "Vasútállomás" → geocode to settlement center
   - Accuracy: ±500-2000 meters

3. **Skip geocoding:**
   - Mark as `geocoding_quality = "no_house_number"`
   - `latitude = NULL`, `longitude = NULL`

##### 5. Database Queries

**Current queries work fine:**
```sql
-- This still works even with NULL house numbers
SELECT * FROM address WHERE house_number = '5';
SELECT * FROM address WHERE house_number IS NULL;  -- Would need to add
```

**New queries needed:**
```sql
-- Find area-based addresses (no house number)
SELECT * FROM address WHERE house_number IS NULL OR house_number = '';

-- Find complex buildings (no house but has building)
SELECT * FROM address 
WHERE (house_number IS NULL OR house_number = '') 
  AND (building IS NOT NULL OR staircase IS NOT NULL);
```

##### 6. Export Impact

**CSV Export:**
- house_number column would have empty values
- Importing tools must handle NULL properly

**PostgreSQL Import:**
```sql
-- Current COPY expects house_number to be NOT NULL
-- New COPY must handle empty/NULL values
COPY address FROM 'addresses.csv' WITH (FORMAT CSV, NULL '');
```

##### 7. Address Display/Formatting

**Current:** "Street Type HouseNumber Building Staircase"

**New:**
```
With house number: "Kossuth utca 5. A. ép. 2. lph."
No house number:   "Kossuth utca A. ép. 2. lph."
Area only:         "Vasútállomás"
```

---

## Validation Impact

### Current Validation Rules

```python
# House number is required
if not house_number or house_number == "000000":
    if not building and not staircase:
        return None  # Invalid
```

### Proposed Validation Rules

```python
# House number can be NULL/empty IF:
# 1. Building OR staircase exists, OR
# 2. It's an infrastructure/area address

if not house_number or house_number == "000000":
    # Valid if has building/staircase
    if building or staircase:
        return format_with_building(...)
    
    # Valid for special location types
    if is_infrastructure_address(street_type):
        return format_area_address(...)
    
    # Invalid only if nothing identifies the address
    if not building and not staircase:
        return None  # Truly invalid
```

---

## Code Impact Assessment

### Files Requiring Changes

#### 1. Schema Definition (`src/etl/export.py`)
```python
# Line ~593: Change NOT NULL constraint
house_number TEXT NOT NULL,  # OLD
house_number TEXT,            # NEW
```

#### 2. Deduplication Logic (`src/etl/deduplicate.py`)

**Lines 373-428:** `_clean_house_number()`
```python
# OLD: Returns None for all-zeros
def _clean_house_number(self, house_num: str) -> str:
    cleaned = house_num.lstrip("0")
    if not cleaned:
        return None  # All zeros = invalid
    return cleaned

# NEW: Returns empty string for all-zeros (valid)
def _clean_house_number(self, house_num: str) -> str:
    if not house_num:
        return ""  # Allow NULL/empty
    cleaned = house_num.lstrip("0")
    if not cleaned:
        return ""  # All zeros = empty, not invalid
    return cleaned
```

**Lines 479-515:** `_format_full_address()`
```python
# OLD: Reject if house number is None
if cleaned_house is None:
    return None

# NEW: Allow empty house number
if not cleaned_house:
    # Valid if has building/staircase
    if building or staircase:
        return self._format_without_house_number(...)
    # Valid for area addresses
    return self._format_area_address(...)
```

#### 3. Hash Generation (`src/etl/hashing.py`, `src/etl/hashing_polars.py`)
```python
# Line ~211: Handle NULL house numbers in hash
house_number = house_number if house_number is not None else ""
# Already handles NULL correctly with empty string ✓
```

#### 4. Full Address Formatting (`src/etl/string_ops_polars.py`)
```python
# Line ~105: Add NULL handling
if house_number:
    components.append(str(house_number))
# Already handles missing house_number ✓
```

---

## Recommendation

### Option 1: Keep Current Logic (Filter All-Zero House Numbers)
**Pros:**
- Simple, clean data model
- No schema changes needed
- No NULL handling complexity

**Cons:**
- Lose 2,091 valid complex building addresses
- Lose 4,660 infrastructure addresses
- **Data loss: 7,551 valid addresses (0.23% of total)**

### Option 2: Allow NULL House Numbers
**Pros:**
- Retain all 7,551 addresses
- More complete dataset
- Better reflects real-world address diversity

**Cons:**
- Schema change (NOT NULL → nullable)
- More complex validation logic
- NULL handling in all queries
- Geocoding challenges

---

## My Recommendation: **OPTION 2 - Allow NULL House Numbers**

### Why:

1. **Data Completeness:** 2,091 addresses with building/staircase are clearly valid and should not be lost

2. **Real-World Accuracy:** Infrastructure addresses (railway stations, landmarks) are valid voting locations

3. **Implementation Impact is Manageable:**
   - Schema change is simple (remove NOT NULL)
   - Hash generation already handles NULL
   - Most formatting logic already handles missing house numbers
   - Main changes needed in validation and full_address generation

4. **Low Risk:**
   - Only 7,551 addresses affected (0.23% of dataset)
   - Clear rules for when NULL is valid (has building/staircase OR infrastructure type)

### Implementation Priority:

**High Priority (Must Fix):**
1. Change schema: `house_number TEXT NOT NULL` → `house_number TEXT`
2. Update `_clean_house_number()` to return `""` instead of `None` for all-zeros
3. Update `_format_full_address()` to handle empty house numbers

**Medium Priority (Should Fix):**
4. Add validation for building/staircase when house number is empty
5. Update geocoding to handle addresses without house numbers
6. Add database queries examples for NULL house numbers

**Low Priority (Nice to Have):**
7. Create address type classification (residential vs infrastructure)
8. Optimize deduplication for NULL house number cases

---

## Conclusion

**Current logic is too restrictive.** Filtering out all addresses with "000000" house numbers loses 7,551 valid addresses, including 2,091 with clear building/staircase identifiers.

**Recommendation:** Modify logic to allow NULL/empty house numbers when:
1. Building OR staircase exists, OR
2. Address represents infrastructure/area location

This requires schema changes and validation logic updates, but the impact is manageable and the benefit (retaining valid data) is significant.
