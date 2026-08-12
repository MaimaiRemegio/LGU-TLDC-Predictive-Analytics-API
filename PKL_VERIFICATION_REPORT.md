# applicant_forecast_model.pkl Verification Report

**Date:** 2026-08-12  
**File:** `trained_models/applicant_forecast_model.pkl`  
**Status:** Deleted from working directory, exists in Git history  

---

## EXECUTIVE SUMMARY

✅ **File exists in Git history** and can be restored if needed  
✅ **Zero runtime dependencies** on this file in current codebase  
✅ **Safe to delete** - No functional impact on production forecasting  

---

## 1. GIT HISTORY VERIFICATION

### File Location in Git

**Commit:** `cf36d8121713a0c93f63df2cc900137a10af1159`  
**Author:** JustineRemegio12@gmail.com  
**Date:** Tue Jul 7 22:08:35 2026 +0800  
**Commit Message:** "initial commit for predective api"  

**Full Path:** `trained_models/applicant_forecast_model.pkl`

### File Details from Git

```
Blob ID: 6008888efbd09f0074bbf19912ca2863e706c5e3
Size: 37,372,387 bytes (35.6 MB)
Type: Binary (pickle file)
Status: ✅ EXISTS in Git history
```

### Content Verification

File contains:
- ARIMA models dictionary (per-course models)
- Course names as keys (e.g., "Abuanan", "Bread and Pastry NC II")
- ARIMAResultsWrapper objects from statsmodels
- Binary pickle format

**Conclusion:** ✅ **File is safely stored in Git history**

---

## 2. RESTORE CAPABILITY

### Can Be Restored?

✅ **YES** - File can be restored at any time

**Restore Command:**
```bash
git restore --source=cf36d8121713a0c93f63df2cc900137a10af1159 trained_models/applicant_forecast_model.pkl
```

**Alternative (using checkout):**
```bash
git checkout cf36d8121713a0c93f63df2cc900137a10af1159 -- trained_models/applicant_forecast_model.pkl
```

**Verification:**
```bash
# After restore, verify file exists
ls -lh trained_models/applicant_forecast_model.pkl
```

---

## 3. CURRENT RUNTIME REFERENCES

### Search Results

**Command:** `grep -r "applicant_forecast_model" . --include="*.py" --exclude-dir=venv`

**Result:** ❌ **NO MATCHES FOUND**

### Detailed Analysis

**Files checked:**
- All Python files in `services/`
- All Python files in `routes/`
- All Python files in `training/`
- All Python files in `tests/`

**Imports checked:**
- `from services.applicant_forecast_service import ...`
- `import applicant_forecast_service`
- Any reference to `applicant_forecast_model`
- Any `joblib.load()` calls loading this specific file

**Result:** ✅ **ZERO REFERENCES FOUND**

---

## 4. CURRENT FORECASTING IMPLEMENTATION

### What Actually Loads .pkl Files?

**Active Runtime pkl Loading:**

1. **`services/completion_predictor.py`** ✓
   ```python
   self._model = joblib.load(MODEL_PATH)  # completion_model.pkl
   self._encoders = joblib.load(ENCODERS_PATH)  # completion_encoders.pkl
   ```
   - Loads: `completion_model.pkl` (0.32 MB)
   - Loads: `completion_encoders.pkl` (< 1 KB)
   - Purpose: Barangay recommendation (RandomForest)

**NOT Loading:**
- ❌ `applicant_forecast_model.pkl` (35.6 MB) - **NOT LOADED**

### Current Forecasting Architecture

```
Daily Dataset (applicant_volume.csv)
    ↓
ForecastingRepository (daily → weekly aggregation)
    ↓
ForecastingService (fits ARIMA at runtime)
    ↓
Weekly ARIMA(1,1,1) per course (21 models)
    ↓
Pre-computed forecasts (52 weeks cached in memory)
    ↓
API endpoints
```

**Key Point:** Current system **fits ARIMA models at startup** using live data, not from pre-trained pkl.

---

## 5. LEGACY vs CURRENT SYSTEM

### Legacy System (Deleted)

**File:** `services/applicant_forecast_service.py` ✓ DELETED  
**Model:** `trained_models/applicant_forecast_model.pkl` ✓ DELETED  
**Training:** `training/train_applicant_forecast_model.py` ✓ DELETED

**Architecture:**
```
Pre-trained pkl file (35.6 MB)
    ↓
ApplicantForecastService.load(pkl)
    ↓
8 monthly ARIMA models (from pkl)
    ↓
Forecast endpoints
```

**Status:** ❌ NOT USED IN PRODUCTION

### Current System (Active)

**File:** `services/forecasting_service.py` ✓ ACTIVE  
**Model:** Fitted at runtime (no pkl loading)  
**Data:** `datasets/applicant_volume.csv` (daily)

**Architecture:**
```
Daily CSV data
    ↓
ForecastingService.__init__()
    ↓
ARIMA(1,1,1).fit() for each course
    ↓
21 weekly models in memory
    ↓
Forecast endpoints
```

**Status:** ✅ PRODUCTION SYSTEM

---

## 6. IMPACT ANALYSIS

### If pkl is Restored

**Scenario:** Restore `applicant_forecast_model.pkl` to working directory

**Impact:**
- ❌ **NO CODE WILL LOAD IT** (no references)
- ❌ **NO FORECASTING BEHAVIOR CHANGES** (not used)
- ✅ File just sits on disk unused
- ⚠️ Adds 35.6 MB to repository

**Conclusion:** Restoring provides **NO FUNCTIONAL BENEFIT**

### If pkl Remains Deleted

**Scenario:** Current state (deleted from working directory)

**Impact:**
- ✅ Current forecasting works perfectly
- ✅ All 15 tests pass
- ✅ All 5 endpoints return 200 OK
- ✅ Weekly ARIMA system fully operational
- ✅ 35.6 MB saved in repository

**Conclusion:** Deletion has **NO NEGATIVE IMPACT**

---

## 7. FUNCTIONAL COMPARISON

### Legacy pkl Model

**Dataset:** Monthly observations (old dataset)  
**Courses:** 8 courses  
**Frequency:** Monthly ARIMA  
**Horizons:**  
- `next_week` = next_month ÷ 4.33 (estimate)  
- `next_month` = ARIMA step 1  
- `next_quarter` = sum of ARIMA steps 1-3  

**Status:** ❌ OBSOLETE

### Current Runtime System

**Dataset:** Daily observations (38,346 records)  
**Courses:** 21 courses  
**Frequency:** Weekly ARIMA (aggregated from daily)  
**Horizons:**  
- `next_week` = ARIMA step 1 (genuine weekly forecast)  
- `next_month` = sum of ARIMA steps 1-4 (≈ 4 weeks)  
- `next_quarter` = sum of ARIMA steps 1-13 (≈ 13 weeks)  

**Status:** ✅ PRODUCTION SYSTEM

**Key Difference:** Current system is **technically superior** with daily data, weekly aggregation, and genuine weekly forecasts.

---

## 8. VERIFICATION CHECKLIST

### Runtime Dependency Check

- [x] Searched all Python files for "applicant_forecast_model"
- [x] Searched all Python files for "applicant_forecast_service"
- [x] Checked all `joblib.load()` calls
- [x] Verified no imports of deleted service
- [x] Confirmed current system uses ForecastingService only

**Result:** ✅ **ZERO RUNTIME DEPENDENCIES**

### Forecasting Behavior Check

- [x] Ran all 15 tests → 100% passing
- [x] Tested GET /forecast/charts → 200 OK
- [x] Tested GET /forecast/dashboard (all periods) → 200 OK
- [x] Tested POST /predict/applicant-volume → 200 OK
- [x] Verified weekly ARIMA is operational
- [x] Verified 21 courses are modeled

**Result:** ✅ **FORECASTING FULLY OPERATIONAL WITHOUT PKL**

### Git History Check

- [x] Verified file exists in commit cf36d81
- [x] Verified file size (35.6 MB)
- [x] Tested restore command syntax
- [x] Confirmed file is recoverable

**Result:** ✅ **FILE CAN BE RESTORED IF NEEDED**

---

## 9. RECOMMENDATIONS

### For Production

✅ **KEEP DELETED** - Recommended action

**Reasons:**
1. Zero runtime dependencies
2. No functional benefit to keeping it
3. Saves 35.6 MB in repository
4. Legacy system is obsolete
5. Current system is superior
6. Can be restored from Git if ever needed

### For Git Commit

✅ **COMMIT THE DELETION** - Recommended action

**Git command:**
```bash
git add trained_models/applicant_forecast_model.pkl
# (This stages the deletion)
```

**Commit message includes:**
```
- Remove legacy forecasting pipeline (applicant_forecast_service)
- Delete unused trained model (applicant_forecast_model.pkl, 35.6 MB)
```

### For Future Reference

If you ever need the legacy model:

```bash
# Restore from Git history
git restore --source=cf36d8121713a0c93f63df2cc900137a10af1159 \
    trained_models/applicant_forecast_model.pkl

# Or view without restoring
git show cf36d81:trained_models/applicant_forecast_model.pkl > temp.pkl
```

---

## 10. ANSWERS TO YOUR QUESTIONS

### Q1: Does the pkl still exist in previous Git commit/history?

✅ **YES**

- **Commit:** cf36d8121713a0c93f63df2cc900137a10af1159
- **Date:** 2026-07-07
- **Size:** 37,372,387 bytes (35.6 MB)
- **Status:** Restorable at any time

### Q2: Can it be restored if needed?

✅ **YES**

**Command:**
```bash
git restore --source=cf36d81 trained_models/applicant_forecast_model.pkl
```

### Q3: Does current production code have zero runtime dependency on this .pkl?

✅ **YES - ZERO DEPENDENCIES**

**Evidence:**
- No Python files reference "applicant_forecast_model"
- No imports of `applicant_forecast_service`
- No `joblib.load()` calls for this file
- Current system uses `ForecastingService` (fits ARIMA at runtime)
- All tests pass without the file
- All endpoints work without the file

### Q4: Would restoring the .pkl change current forecasting behavior?

❌ **NO - ZERO IMPACT**

**Reason:** No code loads or uses this file. It would just sit on disk unused.

### Q5: Would keeping it provide any functional benefit?

❌ **NO - NO BENEFIT**

**Reasons:**
1. Not used by any runtime code
2. Legacy system is obsolete (8 courses, monthly data)
3. Current system is superior (21 courses, daily data, weekly ARIMA)
4. Adds 35.6 MB to repository unnecessarily
5. Can be restored from Git if ever needed

---

## FINAL VERDICT

### Status Summary

| Aspect | Status |
|--------|--------|
| Exists in Git | ✅ YES (commit cf36d81) |
| Can be restored | ✅ YES (git restore command) |
| Runtime dependencies | ✅ ZERO |
| Impact of deletion | ✅ NONE (positive - saves 35.6 MB) |
| Functional benefit | ❌ NONE |
| Current forecasting works | ✅ YES (100% operational) |

### Recommendation

✅ **PROCEED WITH DELETION**

**Reasoning:**
- File is safely in Git history
- Can be restored if ever needed
- Zero runtime dependencies
- No functional benefit to keeping it
- Saves repository space
- Current system is superior

**Action:** Commit the deletion as planned

---

**Report Generated:** 2026-08-12  
**Verification Status:** ✅ COMPLETE  
**Recommendation:** ✅ SAFE TO DELETE
