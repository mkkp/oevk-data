# Documentation Updates Needed for INTERPOLATED Quality Level

## Summary of Change

**INTERPOLATED** is now a separate quality level instead of being included in EXACT.

## Files That Need Manual Review/Update

The following files mention quality statistics and should be reviewed to ensure they reflect the new 5-level quality system:

### High Priority (Direct statistics mentions)

1. **docs/GEOCODING_IMPROVEMENTS_2025.md**
   - Update all statistics to show INTERPOLATED separately
   - Lines mentioning "Exact: 45-55%" should clarify this is EXACT + INTERPOLATED combined

2. **docs/GEOCODING_INTERPOLATION.md**
   - Update to clarify interpolated addresses get INTERPOLATED quality, not EXACT
   - Update expected impact statistics

3. **docs/HERE_GEOCODING.md**
   - Update quality improvement tables
   - Update examples showing quality levels

4. **IMPLEMENTATION_COMPLETE.md**
   - Update final statistics
   - Update quality distribution tables

5. **INTERPOLATION_SUMMARY.md**
   - Update quality improvement statistics
   - Clarify INTERPOLATED vs EXACT distinction

6. **INTERPOLATION_VISUAL.txt**
   - Update text showing quality changes
   - Update "EXACT: 100%" to show EXACT + INTERPOLATED breakdown

7. **README_GEOCODING_SECTION.md**
   - Update quality statistics
   - Add INTERPOLATED to quality level listings

8. **GEOCODING_QUICK_START.md**
   - Update quality improvement table
   - Add INTERPOLATED explanation

### Medium Priority (May need review)

9. **docs/011_RESOLVE_ADDRESS_COORDINATE.md**
   - Original specification - may need note about INTERPOLATED

10. **docs/00_SPECIFICATION.md**
    - Check if quality levels are mentioned

11. **docs/CACHE_MIGRATION_REPORT.md**
    - Check for quality statistics

12. **README.md**
    - Search for quality statistics mentions
    - Update geocoding section if present

## Key Statistics to Update

### Old Statistics (Interpolated included in EXACT)
```
Exact: 45-55%
Street: 35-45%
Settlement: 5-7%
Failed: 0.1-0.2%
```

### New Statistics (Interpolated separate)
```
Exact: 19-25% (from geocoding services)
Interpolated: 20-30% (calculated)
Street: 35-45%
Settlement: 5-7%
Failed: 0.1-0.2%

High-Precision (Exact + Interpolated): 45-55%
```

## Search Terms to Find Mentions

```bash
# Find files with quality statistics
grep -r "19%" --include="*.md" --include="*.txt" .
grep -r "73%" --include="*.md" --include="*.txt" .
grep -r "exact.*street.*settlement" -i --include="*.md" .
grep -r "45-55%" --include="*.md" .

# Find quality level lists
grep -r "EXACT.*STREET.*SETTLEMENT" --include="*.md" .
grep -r "exact.*house.*level" -i --include="*.md" .
```

## Recommended Approach

1. **Use GEOCODING_QUALITY_LEVELS.md as reference** - This is the authoritative source
2. **Update statistics to show 5 levels** - Always list INTERPOLATED separately
3. **Clarify "high-precision"** - When mentioning 45-55%, note this is EXACT + INTERPOLATED
4. **Update examples** - Show INTERPOLATED in quality distribution examples
5. **Add migration notes** - Help users understand the change

## Template for Updates

When you see quality distribution, update like this:

**Before:**
```
Quality Improvement: 19% → 45-55% exact
```

**After:**
```
Quality Improvement:
- Exact: 19% → 19-25% (geocoded)
- Interpolated: 0% → 20-30% (calculated)
- High-Precision Total: 19% → 45-55%
```

**Or more concisely:**
```
Quality Improvement: 19% → 45-55% high-precision (19-25% exact + 20-30% interpolated)
```

## Already Updated

✅ `src/etl/geocoding.py` - Code implementation
✅ `test_interpolation.py` - Test suite  
✅ `QUALITY_LEVEL_CHANGE.md` - Change documentation
✅ `docs/GEOCODING_QUALITY_LEVELS.md` - Complete reference (NEW)
✅ `GEOCODING_QUALITY_UPDATE.md` - Quick summary (NEW)

## Verification Checklist

After updating each file:
- [ ] All quality levels listed include INTERPOLATED
- [ ] Statistics show 5 levels (not 4)
- [ ] "45-55%" is clarified as EXACT + INTERPOLATED
- [ ] Examples show INTERPOLATED quality
- [ ] SQL queries updated to use `IN ('exact', 'interpolated')`
- [ ] No mention of "upgraded to exact" (should be "upgraded to interpolated")

## Note on Backward Compatibility

When updating documentation, include notes that:
- Old queries filtering `quality = 'exact'` may need updating
- Applications should use `IN ('exact', 'interpolated')` for high-precision
- This is a **breaking change** for applications that assume all house-level coordinates are geocoded

## Quick Reference for Writers

**5 Quality Levels (in order):**
1. EXACT - Geocoded house-level
2. INTERPOLATED - Calculated house-level  
3. STREET - Street centroid
4. SETTLEMENT - Settlement centroid
5. FAILED - No coordinates

**High-Precision = EXACT + INTERPOLATED (45-55% combined)**
