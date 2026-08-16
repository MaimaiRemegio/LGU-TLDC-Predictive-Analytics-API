# Production Data Flow - Visual Diagrams

**Date:** 2026-08-13  
**Purpose:** Visual representation of production data ingestion architecture

---

## DIAGRAM 1: CURRENT ARCHITECTURE (Development)

```
┌─────────────────────────────────────────────────────────────┐
│                    CURRENT SYSTEM                            │
│                  (Synthetic CSV Only)                        │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│  datasets/           │
│  applicant_volume.   │
│  csv                 │
│                      │
│  38,346 rows         │
│  2021-2025          │
│  SYNTHETIC DATA      │
└──────────┬───────────┘
           │
           │ Read at startup
           │
           ▼
┌──────────────────────┐
│ ForecastingRepository│
│ ._load_daily()      │
└──────────┬───────────┘
           │
           │ Daily DataFrame
           │
           ▼
┌──────────────────────┐
│ .get_course_series() │
│                      │
│ Daily → Weekly       │
│ Aggregation          │
└──────────┬───────────┘
           │
           │ Weekly Series
           │
           ▼
┌──────────────────────┐
│ ForecastingService   │
│ ._fit_course_models()│
│                      │
│ ARIMA(1,1,1) × 21    │
│ courses              │
└──────────┬───────────┘
           │
           │ Pre-compute 52 weeks
           │
           ▼
┌──────────────────────┐
│ Forecasts cached     │
│ in memory            │
└──────────┬───────────┘
           │
           │
           ▼
┌──────────────────────┐
│ GET /forecast/charts │
│                      │
│ Returns JSON         │
└──────────┬───────────┘
           │
           │
           ▼
┌──────────────────────┐
│ Laravel Dashboard    │
│ Renders Chart        │
└──────────────────────┘

❌ PROBLEM: Requires API restart to update data
❌ PROBLEM: No real TLDC data
```

---

## DIAGRAM 2: PROPOSED ARCHITECTURE (Production)

```
┌─────────────────────────────────────────────────────────────┐
│                   PRODUCTION SYSTEM                          │
│                (Real Laravel Data Flow)                      │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│ Laravel TLDC         │
│ Database             │
│                      │
│ applications table   │
│ - id                 │
│ - application_date   │
│ - course             │
│ - applicant_id       │
│ - ... (more fields)  │
└──────────┬───────────┘
           │
           │ SQL Query: GROUP BY date, course
           │
           ▼
┌──────────────────────┐
│ Laravel Controller   │
│                      │
│ SELECT               │
│   DATE(app_date),    │
│   course,            │
│   COUNT(*)           │
│ FROM applications    │
│ GROUP BY             │
│   date, course       │
└──────────┬───────────┘
           │
           │ HTTP POST (JSON)
           │
           ▼
┌──────────────────────────────────────────────────┐
│ Python Forecasting API                            │
│                                                   │
│ POST /forecast/ingest-data                       │
│                                                   │
│ Body:                                            │
│ {                                                │
│   "sync_type": "incremental",                   │
│   "daily_volumes": [                            │
│     {"date": "2026-01-15",                      │
│      "course": "Cookery NC II",                 │
│      "applicant_count": 8},                     │
│     ...                                          │
│   ]                                              │
│ }                                                │
└──────────┬───────────────────────────────────────┘
           │
           │ 1. Validate data
           │ 2. Store data
           │ 3. Check retraining criteria
           │
           ▼
┌──────────────────────┐
│ Data Validation      │
│                      │
│ ✓ Date format        │
│ ✓ Course names       │
│ ✓ Count >= 0         │
│ ✓ No duplicates      │
└──────────┬───────────┘
           │
           │ Valid data
           │
           ▼
┌──────────────────────┐     ┌──────────────────────┐
│ ForecastingRepository│     │ Decision:            │
│ .upsert_daily_       │────▶│ Should Retrain?      │
│  volumes()           │     │                      │
│                      │     │ ✓ New days >= 30?    │
│ Updates CSV or DB    │     │ ✓ Last train >7d?    │
└──────────────────────┘     │ ✓ Manual trigger?    │
                              │ ✓ Volume drift >20%? │
                              └──────────┬───────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    │                                          │
                    ▼ YES                                      ▼ NO
          ┌──────────────────────┐                  ┌──────────────────────┐
          │ Background Task       │                  │ Keep Existing        │
          │                       │                  │ Models               │
          │ ForecastingService    │                  │                      │
          │ .retrain_models()     │                  │ Return 202 Accepted  │
          │                       │                  └──────────────────────┘
          │ 1. Clear caches       │
          │ 2. Reload data        │
          │ 3. Aggregate weekly   │
          │ 4. Fit ARIMA(1,1,1)   │
          │    × 21 courses       │
          │ 5. Cache forecasts    │
          │                       │
          │ (~10-30 seconds)      │
          └───────────┬───────────┘
                      │
                      │
                      ▼
          ┌──────────────────────┐
          │ Updated Forecasts    │
          │ in Memory            │
          └───────────┬───────────┘
                      │
                      │
                      ▼
          ┌──────────────────────┐
          │ GET /forecast/charts │
          │                      │
          │ Returns UPDATED      │
          │ forecasts            │
          └───────────┬───────────┘
                      │
                      │
                      ▼
          ┌──────────────────────┐
          │ Laravel Dashboard    │
          │ Shows Real Data      │
          └──────────────────────┘

✅ SOLUTION: Real-time data from Laravel
✅ SOLUTION: No API restart needed
✅ SOLUTION: Automatic model updates
```

---

## DIAGRAM 3: DATA AGGREGATION COMPARISON

### Option A: Individual Records (NOT RECOMMENDED)

```
Laravel Database
┌────────────────────────────────────────────┐
│ applications table (INDIVIDUAL RECORDS)    │
├────────┬──────────────┬──────────┬─────────┤
│ id     │ app_date     │ course   │ name    │
├────────┼──────────────┼──────────┼─────────┤
│ 10001  │ 2026-01-15   │ Cookery  │ Juan    │
│ 10002  │ 2026-01-15   │ Cookery  │ Maria   │
│ 10003  │ 2026-01-15   │ Cookery  │ Pedro   │
│ 10004  │ 2026-01-15   │ Driving  │ Ana     │
│ 10005  │ 2026-01-15   │ Driving  │ Carlos  │
│ ...    │ ...          │ ...      │ ...     │
└────────┴──────────────┴──────────┴─────────┘
    │
    │ Send ALL individual records
    │ (Thousands of records!)
    ▼
Python API
┌────────────────────────────────────────────┐
│ POST /forecast/ingest-data                 │
│                                            │
│ Body: {                                    │
│   "applications": [                        │
│     {"id": 10001, "date": "2026-01-15",   │
│      "course": "Cookery", "name": "Juan"},│
│     {"id": 10002, "date": "2026-01-15",   │
│      "course": "Cookery", "name": "Maria"},│
│     ... (thousands more)                   │
│   ]                                        │
│ }                                          │
└────────────────────────────────────────────┘
    │
    │ Python must aggregate
    ▼
┌────────────────────────────────────────────┐
│ Aggregation in Python                      │
│ GROUP BY date, course                      │
└────────────────────────────────────────────┘

❌ Large payload (~MBs)
❌ Slow network transfer
❌ PII transferred (privacy risk)
❌ Unnecessary processing in Python
```

### Option B: Pre-Aggregated Counts (RECOMMENDED) ✅

```
Laravel Database
┌────────────────────────────────────────────┐
│ applications table                         │
├────────┬──────────────┬──────────┬─────────┤
│ id     │ app_date     │ course   │ name    │
├────────┼──────────────┼──────────┼─────────┤
│ 10001  │ 2026-01-15   │ Cookery  │ Juan    │
│ 10002  │ 2026-01-15   │ Cookery  │ Maria   │
│ 10003  │ 2026-01-15   │ Cookery  │ Pedro   │
│ ...    │ ...          │ ...      │ ...     │
└────────┴──────────────┴──────────┴─────────┘
    │
    │ Aggregate in Laravel (SQL)
    ▼
┌────────────────────────────────────────────┐
│ SELECT                                     │
│   DATE(application_date) as date,          │
│   course,                                  │
│   COUNT(*) as applicant_count              │
│ FROM applications                          │
│ GROUP BY date, course                      │
└────────────────────────────────────────────┘
    │
    │ Send ONLY aggregated counts
    │ (Hundreds of records)
    ▼
Python API
┌────────────────────────────────────────────┐
│ POST /forecast/ingest-data                 │
│                                            │
│ Body: {                                    │
│   "daily_volumes": [                       │
│     {"date": "2026-01-15",                │
│      "course": "Cookery NC II",           │
│      "applicant_count": 8},               │
│     {"date": "2026-01-15",                │
│      "course": "Driving NC II",           │
│      "applicant_count": 5}                │
│   ]                                        │
│ }                                          │
└────────────────────────────────────────────┘
    │
    │ Already aggregated!
    ▼
┌────────────────────────────────────────────┐
│ Direct to storage                          │
│ No aggregation needed                      │
└────────────────────────────────────────────┘

✅ Small payload (~KBs)
✅ Fast network transfer
✅ No PII transferred (privacy-safe)
✅ Minimal Python processing
✅ Matches existing CSV structure
```

---

## DIAGRAM 4: RETRAINING DECISION FLOW

```
┌─────────────────────────────────────────┐
│ POST /forecast/ingest-data received     │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Validate & Store Data                   │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Calculate Metrics:                      │
│ - new_data_days (# new daily records)   │
│ - days_since_last_training              │
│ - volume_drift_percent                  │
│ - manual_trigger flag                   │
└────────────────┬────────────────────────┘
                 │
                 ▼
         ┌───────────────┐
         │ Decision Tree │
         └───────┬───────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│ Manual  │  │ New     │  │ Days    │  │ Volume  │
│ Trigger?│  │ Data    │  │ Since   │  │ Drift   │
│         │  │ >= 30   │  │ Last    │  │ > 20%   │
│         │  │ days?   │  │ >= 7?   │  │         │
└────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘
     │            │            │            │
     │ YES        │ YES        │ YES        │ YES
     └────────────┴────────────┴────────────┘
                      │
                      │ ANY condition = YES
                      ▼
              ┌───────────────┐
              │ RETRAIN       │
              │               │
              │ Queue         │
              │ Background    │
              │ Task          │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │ Return 202    │
              │ Accepted      │
              │               │
              │ {             │
              │   "retraining │
              │   _scheduled  │
              │   ": true     │
              │ }             │
              └───────────────┘
                      
                      
     │ ALL conditions = NO
     ▼
┌─────────────────────────────────────────┐
│ KEEP EXISTING MODELS                    │
│                                         │
│ Return 202 Accepted                     │
│                                         │
│ {                                       │
│   "retraining_scheduled": false,        │
│   "reason": "No retraining criteria met"│
│ }                                       │
└─────────────────────────────────────────┘
```

---

## DIAGRAM 5: SYNC SCHEDULES (Recommended)

### Daily Incremental Sync

```
Laravel Cron (Daily at 00:00)
┌─────────────────────────────────────────┐
│ SELECT date, course, COUNT(*)           │
│ FROM applications                       │
│ WHERE application_date > last_sync_date │
│ GROUP BY date, course                   │
└────────────────┬────────────────────────┘
                 │
                 │ Only NEW applications
                 ▼
┌─────────────────────────────────────────┐
│ POST /forecast/ingest-data              │
│ sync_type: "incremental"                │
│                                         │
│ Typical: 10-50 new records/day          │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Append to existing data                 │
│                                         │
│ Retrain if >= 30 new days accumulated  │
└─────────────────────────────────────────┘

Benefits:
✅ Fast (small payload)
✅ Keeps data fresh
✅ Low overhead
```

### Weekly Full Sync

```
Laravel Cron (Weekly Sunday at 02:00)
┌─────────────────────────────────────────┐
│ SELECT date, course, COUNT(*)           │
│ FROM applications                       │
│ GROUP BY date, course                   │
│ ORDER BY date, course                   │
└────────────────┬────────────────────────┘
                 │
                 │ ALL historical data
                 ▼
┌─────────────────────────────────────────┐
│ POST /forecast/ingest-data              │
│ sync_type: "full"                       │
│                                         │
│ Typical: 10,000-50,000 records          │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Replace entire dataset                  │
│                                         │
│ Force retrain with all data             │
└─────────────────────────────────────────┘

Benefits:
✅ Ensures data consistency
✅ Catches any corrections/deletions
✅ Full model refresh
```

---

## DIAGRAM 6: COMPATIBILITY GUARANTEE

### Laravel Dashboard Integration (UNCHANGED)

```
BEFORE (Current)
─────────────────

Laravel Dashboard
    │
    │ GET /forecast/charts
    ▼
┌─────────────────────────────────────────┐
│ Python API                              │
│                                         │
│ Reads: applicant_volume.csv (synthetic) │
│ Returns: JSON forecast data             │
└─────────────────────────────────────────┘
    │
    │ Same JSON structure
    ▼
{
  "applicant_trend_over_time": [...],
  "forecast_curve": [...],
  "summary_points": [...]
}


AFTER (Production)
──────────────────

Laravel Dashboard
    │
    │ GET /forecast/charts
    │ (EXACT SAME REQUEST)
    ▼
┌─────────────────────────────────────────┐
│ Python API                              │
│                                         │
│ Reads: applicant_volume.csv (REAL data)│
│ Returns: JSON forecast data             │
└─────────────────────────────────────────┘
    │
    │ EXACT SAME JSON structure
    ▼
{
  "applicant_trend_over_time": [...],
  "forecast_curve": [...],
  "summary_points": [...]
}

✅ ZERO CHANGES to Laravel dashboard code
✅ Only the DATA SOURCE changes (synthetic → real)
✅ API contract 100% backward compatible
```

---

## DIAGRAM 7: STORAGE OPTIONS

### Option 1: CSV File (Recommended for Capstone)

```
┌──────────────────────────────────────┐
│ POST /forecast/ingest-data           │
└────────────────┬─────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────┐
│ ForecastingRepository                │
│ .upsert_daily_volumes()              │
└────────────────┬─────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────┐
│ pandas DataFrame                     │
│ - Merge with existing data           │
│ - Remove duplicates                  │
│ - Sort by date, course               │
└────────────────┬─────────────────────┘
                 │
                 │ df.to_csv()
                 ▼
┌──────────────────────────────────────┐
│ datasets/applicant_volume.csv        │
│                                      │
│ date,course,applicant_count          │
│ 2021-01-01,Cookery NC II,8           │
│ ...                                  │
└──────────────────────────────────────┘

✅ Simplest
✅ No database setup
✅ Works with existing code
```

### Option 2: SQLite Database

```
┌──────────────────────────────────────┐
│ POST /forecast/ingest-data           │
└────────────────┬─────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────┐
│ SQLite Connection                    │
│                                      │
│ INSERT OR REPLACE INTO daily_volumes │
│ (date, course, applicant_count)      │
│ VALUES (?, ?, ?)                     │
└────────────────┬─────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────┐
│ forecasting.db (SQLite file)         │
│                                      │
│ daily_volumes table                  │
│ - id (PK)                            │
│ - date                               │
│ - course                             │
│ - applicant_count                    │
└──────────────────────────────────────┘

✅ Better for large datasets
✅ SQL queries available
⚠️  Requires schema setup
```

---

## DIAGRAM 8: ERROR HANDLING

```
POST /forecast/ingest-data
    │
    ▼
┌────────────────────────┐
│ Validation             │
└────────┬───────────────┘
         │
         ├─ Invalid date format
         │  → 400 Bad Request
         │     {"error": "Invalid date format"}
         │
         ├─ Unknown course
         │  → 400 Bad Request
         │     {"error": "Unknown course"}
         │
         ├─ Negative count
         │  → 400 Bad Request
         │     {"error": "Count must be >= 0"}
         │
         ├─ Duplicate (date, course)
         │  → 400 Bad Request
         │     {"error": "Duplicate record"}
         │
         ├─ Missing required field
         │  → 422 Unprocessable Entity
         │     {"error": "Missing required field"}
         │
         ├─ Ingestion already in progress
         │  → 409 Conflict
         │     {"error": "Ingestion in progress"}
         │
         └─ All valid
            ▼
         ┌──────────────────┐
         │ Process Data     │
         └─────────┬────────┘
                   │
                   ▼
         ┌──────────────────┐
         │ 202 Accepted     │
         │                  │
         │ {                │
         │   "status":      │
         │   "accepted"     │
         │ }                │
         └──────────────────┘
```

---

## SUMMARY

### Current Flow
CSV (synthetic) → Repository → Service → ARIMA → Cache → API

### Production Flow
Laravel DB → SQL Aggregate → HTTP POST → Validate → Store → Check Criteria → Retrain (if needed) → Cache → API

### Key Points
1. ✅ Laravel sends **pre-aggregated daily counts**
2. ✅ Python validates and stores data
3. ✅ Retraining is **criteria-based** (not every sync)
4. ✅ Background task for retraining (~30 seconds)
5. ✅ GET /forecast/charts **unchanged** (100% backward compatible)
6. ✅ CSV storage (simplest for capstone)
7. ✅ Daily incremental + weekly full sync

---

**Next:** Review design → Implement → Test → Deploy
