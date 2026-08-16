# Production Architecture - Before vs After Comparison

**Date:** 2026-08-13  
**Purpose:** Clear visual comparison of current vs proposed architecture

---

## OVERVIEW COMPARISON

| Aspect | BEFORE (Current) | AFTER (Production) |
|--------|------------------|-------------------|
| **Data Source** | Static CSV (synthetic) | Laravel database (real TLDC data) |
| **Data Update** | Manual CSV edit + API restart | Automatic scheduled sync |
| **Data Freshness** | Stale (2021-2025 frozen) | Current (updates daily) |
| **Model Retraining** | Manual (at startup only) | Automatic (criteria-based) |
| **Production Ready** | ❌ No | ✅ Yes |
| **Laravel Dashboard** | Works | Works (unchanged!) |

---

## DATA FLOW COMPARISON

### BEFORE (Current Architecture)

```
┌─────────────────────────────────┐
│ datasets/applicant_volume.csv   │  ← Static, synthetic data
│ (38,346 rows, 2021-2025)       │  ← Requires manual edit
└──────────────┬──────────────────┘
               │
               │ Read at API startup
               │ (Cannot update without restart)
               ▼
┌─────────────────────────────────┐
│ ForecastingService              │
│ - Loads CSV                     │
│ - Fits ARIMA models (21)        │
│ - Caches forecasts              │
└──────────────┬──────────────────┘
               │
               │ GET /forecast/charts
               ▼
┌─────────────────────────────────┐
│ Laravel Dashboard               │
│ - Displays forecasts            │
│ - Based on synthetic data       │
└─────────────────────────────────┘

❌ Problems:
- Data is synthetic (not real TLDC)
- Cannot update without API restart
- No connection to Laravel database
- Forecasts based on fake data
```

### AFTER (Production Architecture)

```
┌─────────────────────────────────┐
│ Laravel Database                │  ← Real TLDC applications
│ (applications table)            │
└──────────────┬──────────────────┘
               │
               │ Daily scheduled sync (cron)
               │ SELECT date, course, COUNT(*)
               │ GROUP BY date, course
               ▼
┌─────────────────────────────────┐
│ POST /forecast/ingest-data      │  ← New endpoint
│ - Validates data                │
│ - Stores to CSV/DB              │
│ - Checks retraining criteria    │
└──────────────┬──────────────────┘
               │
               │ If criteria met:
               │ - Reload data
               │ - Refit ARIMA models
               │ - Update cached forecasts
               ▼
┌─────────────────────────────────┐
│ ForecastingService              │
│ - Uses real data                │
│ - Models auto-update            │
│ - Fresh forecasts               │
└──────────────┬──────────────────┘
               │
               │ GET /forecast/charts
               ▼
┌─────────────────────────────────┐
│ Laravel Dashboard               │  ← No code changes!
│ - Displays forecasts            │
│ - Based on REAL data            │
└─────────────────────────────────┘

✅ Solutions:
- Data is real (from Laravel DB)
- Updates automatically (scheduled)
- Connected to source of truth
- Forecasts based on real TLDC data
```

---

## DATA SOURCE COMPARISON

### BEFORE: Static CSV

**File:** `datasets/applicant_volume.csv`

```csv
date,course,applicant_count
2021-01-01,Bookkeeping NC II,8
2021-01-01,Cookery NC II,10
...
2025-12-31,Cookery NC II,5
```

| Characteristic | Value |
|----------------|-------|
| **Origin** | Synthetic generator script |
| **Records** | 38,346 rows |
| **Date Range** | 2021-01-01 to 2025-12-31 (frozen) |
| **Update Method** | Manual edit + git commit |
| **Realism** | Fake data (random generation) |
| **Production Use** | ❌ Not suitable |

**To update:**
1. Edit CSV file manually
2. Git commit
3. Restart Python API
4. Hope it works

### AFTER: Real Laravel Data

**Source:** Laravel database `applications` table

| Characteristic | Value |
|----------------|-------|
| **Origin** | Real TLDC application forms |
| **Records** | Variable (grows over time) |
| **Date Range** | Current (today's date) |
| **Update Method** | Automatic sync (scheduled) |
| **Realism** | Real TLDC data |
| **Production Use** | ✅ Production-ready |

**To update:**
1. Applications submitted in Laravel
2. Daily cron runs at midnight
3. Python API receives data
4. Models retrain if needed
5. Forecasts automatically fresh

---

## MODEL RETRAINING COMPARISON

### BEFORE: Manual Retraining

**When models retrain:**
- ✅ At API startup
- ❌ That's it

**To retrain with new data:**
1. Edit CSV file
2. Restart entire Python API
3. Wait for startup (~30 seconds)
4. All users affected by restart

**Problems:**
- No way to update models without restart
- Downtime during restart
- No automated updates
- No criteria-based decisions

### AFTER: Automatic Criteria-Based Retraining

**When models retrain (ANY of):**
- ✅ New data days >= 30
- ✅ Days since last training >= 7
- ✅ Manual trigger flag
- ✅ Volume drift > 20%

**To retrain with new data:**
1. Laravel sends new data
2. Python API checks criteria
3. If met: background task retrains
4. No API downtime
5. Forecasts update automatically

**Benefits:**
- Automatic updates (no manual intervention)
- No API downtime
- Smart retraining (not every sync)
- Background processing

---

## API ENDPOINTS COMPARISON

### BEFORE

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `GET /forecast/charts` | GET | Get forecast charts | ✅ Works |
| `GET /forecast/dashboard` | GET | Get dashboard data | ✅ Works |
| `POST /predict/applicant-volume` | POST | Get forecast | ✅ Works |
| Data ingestion | - | - | ❌ Not available |

### AFTER

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `GET /forecast/charts` | GET | Get forecast charts | ✅ Works (unchanged) |
| `GET /forecast/dashboard` | GET | Get dashboard data | ✅ Works (unchanged) |
| `POST /predict/applicant-volume` | POST | Get forecast | ✅ Works (unchanged) |
| `POST /forecast/ingest-data` | POST | **Ingest real data** | ✅ **NEW** |

**Key Point:** All existing endpoints remain 100% unchanged!

---

## LARAVEL INTEGRATION COMPARISON

### BEFORE: Dashboard Only

**Laravel Code:**
```php
// Dashboard fetches forecasts
$response = Http::get('http://python-api/forecast/charts');
$data = $response->json();
return view('dashboard', compact('data'));
```

**Laravel's Role:**
- ✅ Fetch forecasts
- ❌ No data synchronization
- ❌ No connection to Python's data source

### AFTER: Dashboard + Data Sync

**Laravel Code (Dashboard - unchanged):**
```php
// Dashboard fetches forecasts (NO CHANGES)
$response = Http::get('http://python-api/forecast/charts');
$data = $response->json();
return view('dashboard', compact('data'));
```

**Laravel Code (New Sync Controller):**
```php
// NEW: Sync data to Python API
$dailyVolumes = DB::table('applications')
    ->select(
        DB::raw('DATE(application_date) as date'),
        'course',
        DB::raw('COUNT(*) as applicant_count')
    )
    ->groupBy('date', 'course')
    ->get();

$response = Http::post('http://python-api/forecast/ingest-data', [
    'daily_volumes' => $dailyVolumes,
    'sync_type' => 'full'
]);
```

**Laravel's Role:**
- ✅ Fetch forecasts (unchanged)
- ✅ Sync application data to Python API (new)
- ✅ Two-way integration

---

## STORAGE COMPARISON

### BEFORE

| Storage | Type | Location | Access |
|---------|------|----------|--------|
| Daily volumes | CSV | `datasets/applicant_volume.csv` | Read-only at startup |
| ARIMA models | Memory | Python process | Runtime only |
| Forecasts | Memory | Cached in service | Runtime only |

**Update Process:** Manual file edit + restart

### AFTER

| Storage | Type | Location | Access |
|---------|------|----------|--------|
| Daily volumes | CSV | `datasets/applicant_volume.csv` | Read/write via API |
| ARIMA models | Memory | Python process | Runtime + auto-refresh |
| Forecasts | Memory | Cached in service | Runtime + auto-refresh |

**Update Process:** Automatic via API endpoint

---

## DEPLOYMENT COMPARISON

### BEFORE: Simple but Limited

**Deployment Steps:**
1. Git push changes
2. Vercel/hosting deploys
3. API restarts
4. Done

**Pros:**
- ✅ Simple deployment

**Cons:**
- ❌ Cannot update data without redeployment
- ❌ No production data integration
- ❌ Not suitable for real use

### AFTER: Production-Ready

**Deployment Steps:**
1. Git push changes
2. Vercel/hosting deploys
3. API restarts
4. **NEW:** Laravel sync sends real data
5. Models retrain with real data
6. Done

**Pros:**
- ✅ Production-ready
- ✅ Real data integration
- ✅ Automatic updates
- ✅ No redeployment needed for data updates

**Cons:**
- ⚠️ Slightly more complex initial setup
- ⚠️ Requires Laravel scheduled tasks

---

## MAINTENANCE COMPARISON

### BEFORE: High Maintenance

**To update forecasts with new data:**
1. Manually edit CSV file
2. Commit to git
3. Redeploy entire API
4. Wait for deployment
5. Test manually

**Frequency:** Rare (too much work)

**Risk:** High (manual edits, full redeploy)

### AFTER: Low Maintenance

**To update forecasts with new data:**
1. Wait for scheduled sync (automatic)
2. That's it

**Frequency:** Daily (automatic)

**Risk:** Low (automated, no manual intervention)

---

## DATA PRIVACY COMPARISON

### BEFORE

**Data in CSV:**
- Date, course, aggregated count
- No PII (already aggregated)

**Risk:** Low

### AFTER

**Data transferred in API:**
- Date, course, aggregated count
- No PII (already aggregated)

**Risk:** Low (same as before)

**Additional Protection:**
- ✅ Optional API key authentication
- ✅ HTTPS encryption
- ✅ No individual applicant data
- ✅ No names, IDs, or sensitive fields

---

## TESTING COMPARISON

### BEFORE

**Test Data Source:**
- Synthetic CSV only
- No real data testing

**Test Coverage:**
- ✅ ARIMA calculations
- ✅ API responses
- ❌ Real data integration
- ❌ Data ingestion
- ❌ Model retraining

### AFTER

**Test Data Source:**
- Synthetic CSV (development)
- Real data (integration testing)

**Test Coverage:**
- ✅ ARIMA calculations
- ✅ API responses
- ✅ Real data integration
- ✅ Data ingestion validation
- ✅ Model retraining logic

---

## SCALABILITY COMPARISON

### BEFORE

**Limitations:**
- CSV editing doesn't scale
- Manual process
- Git repo size grows

**Max Capacity:**
- ~100k rows (CSV still works)
- Beyond that: slow, cumbersome

### AFTER

**Scalability:**
- API endpoint scales
- Automated process
- Can migrate to database if needed

**Max Capacity:**
- ~100k rows (CSV still fine)
- Beyond that: migrate to SQLite/PostgreSQL
- Architecture supports it

---

## COST COMPARISON

### BEFORE

**Infrastructure:**
- Python API hosting (Vercel free tier)
- Git repository storage
- **Total: Free**

**Developer Time:**
- Manual CSV updates: 30 min per update
- Git commits/redeploys: 15 min per update
- **Total: 45 min per update**

### AFTER

**Infrastructure:**
- Python API hosting (Vercel free tier)
- Git repository storage
- Laravel scheduled tasks (existing server)
- **Total: Free (no additional cost)**

**Developer Time:**
- Initial setup: 2-3 days (one-time)
- Ongoing maintenance: 0 min (automated)
- **Total: Saves 45 min per update**

**ROI:** Pays for itself after ~4-6 updates

---

## RISK COMPARISON

### BEFORE

**Risks:**
- ❌ Using fake data in production
- ❌ Forecasts not based on reality
- ❌ Manual errors in CSV editing
- ❌ Deployment issues during updates
- ❌ Not production-ready

**Risk Level:** HIGH for production use

### AFTER

**Risks:**
- ✅ Real data (mitigates fake data risk)
- ✅ Automated sync (mitigates manual errors)
- ✅ Validation layer (mitigates bad data)
- ✅ Background retraining (mitigates downtime)
- ⚠️ New endpoint security (mitigated by API key)

**Risk Level:** LOW for production use

---

## FEATURE COMPARISON MATRIX

| Feature | BEFORE | AFTER |
|---------|--------|-------|
| **Data Source** | Synthetic CSV | Real Laravel DB |
| **Data Update** | Manual | Automatic |
| **Update Frequency** | Rare (manual) | Daily (scheduled) |
| **Model Retraining** | Manual (restart) | Auto (criteria-based) |
| **Dashboard Code** | Works | Works (unchanged) |
| **API Downtime** | Required for updates | Not required |
| **Production Ready** | ❌ No | ✅ Yes |
| **Real TLDC Data** | ❌ No | ✅ Yes |
| **Laravel Integration** | One-way (fetch) | Two-way (sync + fetch) |
| **Background Processing** | ❌ No | ✅ Yes |
| **Data Validation** | Manual | Automatic |
| **Error Handling** | Basic | Comprehensive |
| **Monitoring** | Basic | Detailed |
| **Scalability** | Limited | Good |
| **Maintenance** | High | Low |
| **Developer Time** | 45 min/update | 0 min (automated) |
| **Security** | Basic | Enhanced (API key) |
| **Privacy** | Good | Good |
| **Testing** | Partial | Complete |
| **Documentation** | Basic | Comprehensive |

---

## MIGRATION PATH

### Step 1: Current State (BEFORE)
```
[Static CSV] → [Python API] → [Laravel Dashboard]
```

### Step 2: Add Ingestion Endpoint
```
[Static CSV] → [Python API] ← [New Endpoint]
                    ↓
           [Laravel Dashboard]
```

### Step 3: Connect Laravel
```
[Static CSV] → [Python API] ← [POST /ingest-data] ← [Laravel DB]
                    ↓
           [Laravel Dashboard]
```

### Step 4: Full Production (AFTER)
```
[Laravel DB] → [POST /ingest-data] → [Python API] → [Laravel Dashboard]
                                           ↓
                                    [Real Forecasts]
```

**During Migration:**
- ✅ Dashboard continues working (GET /forecast/charts unchanged)
- ✅ Can test new endpoint without affecting dashboard
- ✅ Can rollback at any step
- ✅ Zero downtime

---

## SUMMARY TABLE

| Metric | BEFORE | AFTER | Improvement |
|--------|--------|-------|-------------|
| Data Source | Synthetic CSV | Real Laravel DB | ✅ Production-ready |
| Update Method | Manual edit | Automatic sync | ✅ Saves 45 min/update |
| Update Frequency | Rare | Daily | ✅ Always fresh |
| API Downtime | Required | Not required | ✅ Zero downtime |
| Developer Time | High | Low | ✅ Low maintenance |
| Risk Level | High | Low | ✅ Safer |
| Production Ready | ❌ No | ✅ Yes | ✅ Ready for real use |
| Dashboard Changes | - | None | ✅ Backward compatible |
| Implementation Time | - | 2-3 days | ✅ Reasonable effort |

---

## CONCLUSION

### BEFORE (Current)
- ❌ Synthetic data only
- ❌ Manual updates
- ❌ Not production-ready
- ✅ Simple (but limited)

### AFTER (Production)
- ✅ Real TLDC data
- ✅ Automatic updates
- ✅ Production-ready
- ✅ Still simple (just more capable)

### Key Takeaway

**Zero breaking changes to dashboard, but transforms forecasting from "demo with fake data" to "production system with real TLDC data."**

---

**Recommendation:** PROCEED with production implementation

**Risk:** LOW (backward compatible)  
**Effort:** REASONABLE (2-3 days)  
**Value:** HIGH (production-ready system)
