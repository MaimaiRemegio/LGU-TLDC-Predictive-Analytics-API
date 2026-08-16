# Production Data Ingestion Design for Forecasting API

**Date:** 2026-08-13  
**Purpose:** Design production-ready data ingestion from Laravel to Python forecasting API  
**Status:** Design Phase - No Implementation Yet

---

## EXECUTIVE SUMMARY

### Current Problem
The forecasting API uses **synthetic CSV data** (`applicant_volume.csv`) that is hard-coded and requires API restart to update. This is acceptable for development but NOT production-ready.

### Solution
Design a **data ingestion endpoint** where Laravel can send real TLDC applicant/application data to the Python API, which will:
1. Validate and store the data
2. Aggregate daily applicant volumes
3. Retrain ARIMA models when sufficient new data is available
4. Serve updated forecasts via existing `/forecast/charts` endpoint

### Key Constraint
**ZERO CHANGES to Laravel dashboard integration.** The existing `GET /forecast/charts` response structure remains 100% compatible.

---

## PART 1: CURRENT ARCHITECTURE ANALYSIS

### 1.1 Current Data Structure

**File:** `datasets/applicant_volume.csv`

**Schema:**
```csv
date,course,applicant_count
2021-01-01,Bookkeeping NC II,8
2021-01-01,Carpentry NC II,6
2021-01-01,Cookery NC II,10
```

**Key Fields:**
| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `date` | DATE | Application date (YYYY-MM-DD) | ✅ YES |
| `course` | TEXT | Course name | ✅ YES |
| `applicant_count` | INTEGER | Daily applicant count per course | ✅ YES |

**Characteristics:**
- ✅ Already aggregated to **DAILY** level
- ✅ One row per (date, course) combination
- ✅ Pre-aggregated counts (not individual records)
- ✅ Total records: 38,346 rows (2021-2025, 21 courses)

### 1.2 Current Processing Flow

```
CSV File (daily data)
    ↓
ForecastingRepository._load_daily()
    ↓
Daily DataFrame (date, course, applicant_count)
    ↓
ForecastingRepository.get_course_series()
    ↓
Weekly Aggregation (resample "W-SUN")
    ↓
Weekly Series per course
    ↓
ForecastingService._fit_course_models()
    ↓
ARIMA(1,1,1) per course (21 models)
    ↓
Pre-compute 52 weeks ahead
    ↓
Cache forecasts in memory
    ↓
Serve via /forecast/charts
```

### 1.3 Current Dependencies

**Minimal Required Fields for ARIMA:**
1. ✅ `date` - For time series indexing
2. ✅ `course` - For per-course modeling
3. ✅ `applicant_count` - For volume forecasting

**NOT Required for ARIMA:**
- ❌ Individual applicant IDs
- ❌ Applicant names
- ❌ Barangay (used only for demographic profiles)
- ❌ Age, sex, employment status (descriptive only)
- ❌ Application form fields

**Key Insight:** The forecasting system only needs **aggregated daily counts per course**, not individual application records.

### 1.4 Current Startup Behavior

**File:** `main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    get_forecasting_service()  # Loads CSV, fits 21 ARIMA models
    yield
```

**Timing:**
- Model training happens at API startup (blocking)
- Takes ~10-30 seconds depending on data size
- Models remain in memory until API restart

---

## PART 2: PRODUCTION ARCHITECTURE DESIGN

### 2.1 Two Approaches Compared

#### Option A: Individual Application Records

**Laravel sends:**
```json
{
  "applications": [
    {
      "application_id": 12345,
      "application_date": "2026-01-15",
      "course": "Cookery NC II",
      "applicant_id": 67890,
      "applicant_name": "Juan Dela Cruz"
    },
    ...
  ]
}
```

**Pros:**
- Laravel sends all available data
- Python can perform additional analytics

**Cons:**
- ❌ Large payload size (thousands of records)
- ❌ Requires aggregation in Python
- ❌ Unnecessary data transfer (names, IDs not needed for forecasting)
- ❌ Privacy concerns (PII in API requests)
- ❌ Slower processing

#### Option B: Pre-Aggregated Daily Counts ✅ **RECOMMENDED**

**Laravel sends:**
```json
{
  "daily_volumes": [
    {
      "date": "2026-01-15",
      "course": "Cookery NC II",
      "applicant_count": 8
    },
    {
      "date": "2026-01-15",
      "course": "Driving NC II",
      "applicant_count": 5
    }
  ]
}
```

**Pros:**
- ✅ **Minimal payload** - only what's needed
- ✅ **Matches existing CSV structure exactly**
- ✅ **No PII transfer** (privacy-safe)
- ✅ **Fast processing** - no aggregation needed
- ✅ **Easy Laravel implementation** - simple SQL GROUP BY
- ✅ **Backward compatible** with existing repository

**Cons:**
- None for this use case

**Decision:** **Option B is strongly recommended** for this capstone project.

### 2.2 Recommended Data Format

**Endpoint:** `POST /forecast/ingest-data`

**Request Body:**
```json
{
  "source": "laravel_tldc",
  "data_version": "1.0",
  "sync_type": "full|incremental",
  "date_range": {
    "start_date": "2021-01-01",
    "end_date": "2026-08-13"
  },
  "daily_volumes": [
    {
      "date": "2026-01-15",
      "course": "Cookery NC II",
      "applicant_count": 8
    },
    {
      "date": "2026-01-15",
      "course": "Driving NC II",
      "applicant_count": 5
    },
    {
      "date": "2026-01-16",
      "course": "Cookery NC II",
      "applicant_count": 3
    }
  ]
}
```

**Field Definitions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | YES | Data source identifier (e.g., "laravel_tldc") |
| `data_version` | string | YES | API version for future compatibility |
| `sync_type` | enum | YES | "full" (replace all) or "incremental" (append new) |
| `date_range.start_date` | date | YES | Earliest date in the dataset |
| `date_range.end_date` | date | YES | Latest date in the dataset |
| `daily_volumes` | array | YES | Array of daily applicant counts |
| `daily_volumes[].date` | date | YES | Application date (YYYY-MM-DD format) |
| `daily_volumes[].course` | string | YES | Exact course name |
| `daily_volumes[].applicant_count` | integer | YES | Number of applicants (≥ 0) |

**Validation Rules:**
1. `date` must be valid YYYY-MM-DD format
2. `applicant_count` must be non-negative integer
3. `course` must match one of the 21 recognized courses
4. No duplicate (date, course) pairs in one request
5. `sync_type` must be either "full" or "incremental"

### 2.3 Response Format

**Success Response (202 Accepted):**
```json
{
  "status": "accepted",
  "message": "Data ingestion queued successfully",
  "ingestion_id": "ing_20260813_123456",
  "records_received": 1500,
  "date_range": {
    "start_date": "2021-01-01",
    "end_date": "2026-08-13"
  },
  "sync_type": "incremental",
  "estimated_processing_time_seconds": 15,
  "retraining_scheduled": true,
  "retraining_reason": "Sufficient new data (30+ new days)",
  "next_steps": [
    "Data will be validated and stored",
    "Models will be retrained if criteria met",
    "Forecasts will be available after processing"
  ]
}
```

**Error Response (400 Bad Request):**
```json
{
  "status": "error",
  "error_code": "INVALID_DATA_FORMAT",
  "message": "Validation failed",
  "errors": [
    {
      "field": "daily_volumes[5].date",
      "error": "Invalid date format. Expected YYYY-MM-DD"
    },
    {
      "field": "daily_volumes[12].applicant_count",
      "error": "Applicant count must be non-negative"
    },
    {
      "field": "daily_volumes[20].course",
      "error": "Unknown course 'Invalid Course Name'"
    }
  ],
  "records_received": 1500,
  "records_valid": 1497,
  "records_invalid": 3
}
```

**Error Response (409 Conflict):**
```json
{
  "status": "error",
  "error_code": "INGESTION_IN_PROGRESS",
  "message": "Another data ingestion is currently in progress",
  "current_ingestion_id": "ing_20260813_120000",
  "estimated_completion_seconds": 45
}
```

---

## PART 3: PROPOSED PRODUCTION FLOW

### 3.1 Data Ingestion Flow

```
Laravel TLDC Database
    ↓
    | SELECT date, course, COUNT(*) as applicant_count
    | FROM applications
    | GROUP BY date, course
    | ORDER BY date, course
    ↓
Laravel HTTP Request
    ↓ POST /forecast/ingest-data
Python Forecasting API
    ↓
Data Validation
    ├─ Date format check
    ├─ Course name validation
    ├─ Applicant count >= 0
    └─ No duplicate (date, course)
    ↓
Data Storage
    ├─ Option 1: SQLite database (lightweight)
    ├─ Option 2: PostgreSQL (production-grade)
    └─ Option 3: CSV file replacement (simplest)
    ↓
Check Retraining Criteria
    ├─ New data days >= threshold (e.g., 30 days)
    ├─ Time since last training >= threshold (e.g., 7 days)
    └─ Manual trigger flag
    ↓
    ├─ YES → Schedule Retraining
    │   ↓
    │   Background Task
    │   ↓
    │   Load Daily Data
    │   ↓
    │   Aggregate to Weekly
    │   ↓
    │   Fit ARIMA(1,1,1) × 21 courses
    │   ↓
    │   Cache forecasts (52 weeks)
    │   ↓
    │   Update singleton service
    │
    └─ NO → Keep existing models
    ↓
Return Success Response
    ↓
Laravel Dashboard
    ↓ GET /forecast/charts (unchanged!)
Python Forecasting API
    ↓
Serve forecasts from cache
```

### 3.2 Laravel Implementation Example

**Laravel Controller Method:**

```php
<?php

namespace App\Http\Controllers;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class ForecastDataSyncController extends Controller
{
    /**
     * Sync application data to Python forecasting API.
     * 
     * This method aggregates daily applicant volumes and sends
     * them to the Python API for ARIMA forecasting.
     */
    public function syncForecastingData()
    {
        // Step 1: Aggregate daily applicant volumes from Laravel database
        $dailyVolumes = DB::table('applications')
            ->select(
                DB::raw('DATE(application_date) as date'),
                'course',
                DB::raw('COUNT(*) as applicant_count')
            )
            ->whereNotNull('application_date')
            ->whereNotNull('course')
            ->groupBy('date', 'course')
            ->orderBy('date', 'asc')
            ->orderBy('course', 'asc')
            ->get()
            ->map(function ($row) {
                return [
                    'date' => $row->date,
                    'course' => $row->course,
                    'applicant_count' => (int) $row->applicant_count
                ];
            })
            ->toArray();

        // Step 2: Get date range
        $dates = collect($dailyVolumes)->pluck('date');
        $startDate = $dates->min();
        $endDate = $dates->max();

        // Step 3: Build request payload
        $payload = [
            'source' => 'laravel_tldc',
            'data_version' => '1.0',
            'sync_type' => 'full',  // or 'incremental' for updates only
            'date_range' => [
                'start_date' => $startDate,
                'end_date' => $endDate
            ],
            'daily_volumes' => $dailyVolumes
        ];

        // Step 4: Send to Python API
        try {
            $response = Http::timeout(120)  // 2 minutes timeout
                ->post(config('services.forecast_api.url') . '/forecast/ingest-data', $payload);

            if ($response->successful()) {
                $data = $response->json();
                
                Log::info('Forecast data sync successful', [
                    'ingestion_id' => $data['ingestion_id'],
                    'records_sent' => count($dailyVolumes),
                    'retraining_scheduled' => $data['retraining_scheduled']
                ]);

                return response()->json([
                    'success' => true,
                    'message' => 'Forecast data synchronized successfully',
                    'data' => $data
                ]);
            } else {
                $error = $response->json();
                
                Log::error('Forecast data sync failed', [
                    'status' => $response->status(),
                    'error' => $error
                ]);

                return response()->json([
                    'success' => false,
                    'message' => 'Failed to sync forecast data',
                    'error' => $error
                ], $response->status());
            }
        } catch (\Exception $e) {
            Log::error('Forecast data sync exception', [
                'exception' => $e->getMessage()
            ]);

            return response()->json([
                'success' => false,
                'message' => 'Exception during forecast data sync',
                'error' => $e->getMessage()
            ], 500);
        }
    }

    /**
     * Sync only incremental data (new applications since last sync).
     */
    public function syncIncrementalData()
    {
        // Get last sync timestamp from settings or database
        $lastSyncDate = DB::table('settings')
            ->where('key', 'last_forecast_sync_date')
            ->value('value') ?? '2021-01-01';

        // Query only new data
        $dailyVolumes = DB::table('applications')
            ->select(
                DB::raw('DATE(application_date) as date'),
                'course',
                DB::raw('COUNT(*) as applicant_count')
            )
            ->where('application_date', '>', $lastSyncDate)
            ->whereNotNull('application_date')
            ->whereNotNull('course')
            ->groupBy('date', 'course')
            ->orderBy('date', 'asc')
            ->get()
            ->map(function ($row) {
                return [
                    'date' => $row->date,
                    'course' => $row->course,
                    'applicant_count' => (int) $row->applicant_count
                ];
            })
            ->toArray();

        if (empty($dailyVolumes)) {
            return response()->json([
                'success' => true,
                'message' => 'No new data to sync'
            ]);
        }

        $dates = collect($dailyVolumes)->pluck('date');
        
        $payload = [
            'source' => 'laravel_tldc',
            'data_version' => '1.0',
            'sync_type' => 'incremental',
            'date_range' => [
                'start_date' => $dates->min(),
                'end_date' => $dates->max()
            ],
            'daily_volumes' => $dailyVolumes
        ];

        // Send to API and update last sync date on success
        // ... (similar to syncForecastingData)
    }
}
```

**Laravel Route:**
```php
// routes/api.php
Route::post('/admin/sync-forecast-data', [ForecastDataSyncController::class, 'syncForecastingData']);
Route::post('/admin/sync-forecast-incremental', [ForecastDataSyncController::class, 'syncIncrementalData']);
```

**Laravel Config:**
```php
// config/services.php
return [
    'forecast_api' => [
        'url' => env('FORECAST_API_URL', 'http://localhost:8000'),
    ],
];
```

**.env:**
```
FORECAST_API_URL=http://localhost:8000
# or for production:
# FORECAST_API_URL=https://your-python-api.vercel.app
```

### 3.3 Scheduled Sync (Laravel Task Scheduler)

**Laravel Kernel:**
```php
// app/Console/Kernel.php
protected function schedule(Schedule $schedule)
{
    // Option 1: Daily sync at midnight
    $schedule->call(function () {
        Http::post(route('admin.sync-forecast-incremental'));
    })->daily()->at('00:00');

    // Option 2: Weekly full sync every Sunday
    $schedule->call(function () {
        Http::post(route('admin.sync-forecast-data'));
    })->weekly()->sundays()->at('02:00');
}
```

---

## PART 4: RETRAINING STRATEGY

### 4.1 When to Retrain?

**Problem:** ARIMA retraining on 21 courses takes ~10-30 seconds. We don't want to retrain after every single new application.

**Recommended Criteria (ANY one triggers retraining):**

1. **Sufficient New Data**
   - Threshold: ≥ 30 new daily records (≈ 1+ weeks of data)
   - Reason: Weekly ARIMA needs at least 1 new week for meaningful update

2. **Scheduled Interval**
   - Threshold: 7 days since last training
   - Reason: Weekly refresh aligns with weekly ARIMA granularity

3. **Manual Trigger**
   - Admin manually requests model refresh
   - Use case: Data correction, model tuning

4. **Significant Volume Change**
   - Threshold: Recent weekly volume differs by >20% from forecast
   - Reason: Model drift detected

**Implementation:**

```python
def should_retrain(
    new_data_days: int,
    days_since_last_training: int,
    manual_trigger: bool,
    volume_drift_percent: float
) -> tuple[bool, str]:
    """
    Determine if models should be retrained.
    
    Returns:
        (should_retrain: bool, reason: str)
    """
    if manual_trigger:
        return True, "Manual trigger by administrator"
    
    if new_data_days >= 30:
        return True, f"Sufficient new data ({new_data_days} new days)"
    
    if days_since_last_training >= 7:
        return True, f"Scheduled retraining ({days_since_last_training} days since last)"
    
    if abs(volume_drift_percent) > 20.0:
        return True, f"Significant volume drift ({volume_drift_percent:+.1f}%)"
    
    return False, "No retraining criteria met"
```

### 4.2 Retraining Modes

**Mode 1: Blocking (Synchronous) - Simplest**
```python
@router.post("/forecast/ingest-data")
def ingest_data(request: DataIngestionRequest):
    # Validate
    # Store
    # Check criteria
    if should_retrain(...):
        # BLOCKS until done (~10-30 seconds)
        forecasting_service.retrain_models()
    return {"status": "completed"}
```

**Pros:**
- ✅ Simplest implementation
- ✅ Immediate consistency
- ✅ No background worker needed

**Cons:**
- ❌ Client waits ~30 seconds
- ❌ Blocks API thread

**Mode 2: Background Task (Asynchronous) - Recommended**
```python
from fastapi import BackgroundTasks

@router.post("/forecast/ingest-data")
def ingest_data(request: DataIngestionRequest, background_tasks: BackgroundTasks):
    # Validate
    # Store
    # Check criteria
    if should_retrain(...):
        # Returns immediately (202 Accepted)
        background_tasks.add_task(retrain_models_task)
    return {"status": "accepted", "retraining_scheduled": True}

def retrain_models_task():
    forecasting_service.retrain_models()
```

**Pros:**
- ✅ Client gets immediate response (202)
- ✅ Non-blocking
- ✅ Better user experience

**Cons:**
- ⚠️ Forecasts may be stale for ~30 seconds during retraining
- ⚠️ Requires FastAPI BackgroundTasks

**Mode 3: Separate Worker Process - Production**
```python
# Use Celery or similar
@celery.task
def retrain_models_task():
    forecasting_service.retrain_models()

@router.post("/forecast/ingest-data")
def ingest_data(request: DataIngestionRequest):
    # Validate, store
    if should_retrain(...):
        retrain_models_task.delay()  # Queue to Celery
    return {"status": "accepted"}
```

**Pros:**
- ✅ True background processing
- ✅ Scalable
- ✅ Can monitor task status

**Cons:**
- ❌ Requires Celery + Redis/RabbitMQ
- ❌ More complex deployment

**Recommendation for Capstone:** **Mode 2 (FastAPI BackgroundTasks)** - Good balance of simplicity and user experience.

### 4.3 Retraining Implementation

**Key Changes to ForecastingService:**

```python
class ForecastingService:
    def __init__(self, repository=None, statistics=None):
        self._repository = repository or get_forecasting_repository()
        # ... existing code ...
        self._last_training_time: datetime | None = None
        self._fit_course_models()
    
    def retrain_models(self) -> dict:
        """
        Retrain all ARIMA models with latest data.
        
        Returns training metrics.
        """
        start_time = time.time()
        
        # Clear caches
        self._weekly_series.clear()
        self._weekly_models.clear()
        self._weekly_forecast.clear()
        self._cached_distributions = None
        self._cached_course_forecasts.clear()
        
        # Reload data from repository
        self._repository.reload_data()
        
        # Refit models
        self._fit_course_models()
        
        # Update timestamp
        self._last_training_time = datetime.now()
        
        elapsed = time.time() - start_time
        
        return {
            "status": "completed",
            "training_time_seconds": round(elapsed, 2),
            "courses_trained": len(self._weekly_models),
            "training_timestamp": self._last_training_time.isoformat()
        }
```

**Key Changes to ForecastingRepository:**

```python
class ForecastingRepository:
    def reload_data(self) -> None:
        """Reload the daily volume dataset from storage."""
        self._daily = self._load_daily(self._volume_path)
    
    def upsert_daily_volumes(
        self, 
        daily_volumes: list[dict],
        sync_type: str = "full"
    ) -> dict:
        """
        Insert or update daily volume data.
        
        Args:
            daily_volumes: List of {"date": str, "course": str, "applicant_count": int}
            sync_type: "full" (replace all) or "incremental" (append new)
        
        Returns:
            Metrics about the operation
        """
        new_df = pd.DataFrame(daily_volumes)
        new_df['date'] = pd.to_datetime(new_df['date'])
        
        if sync_type == "full":
            # Replace entire dataset
            self._daily = new_df.sort_values(['course', 'date']).reset_index(drop=True)
        else:
            # Incremental: remove duplicates, append new
            self._daily = pd.concat([self._daily, new_df], ignore_index=True)
            self._daily = self._daily.drop_duplicates(subset=['date', 'course'], keep='last')
            self._daily = self._daily.sort_values(['course', 'date']).reset_index(drop=True)
        
        # Persist to storage (CSV or database)
        self._persist_data()
        
        return {
            "total_records": len(self._daily),
            "new_records_added": len(new_df),
            "date_range": {
                "start": str(self._daily['date'].min()),
                "end": str(self._daily['date'].max())
            }
        }
    
    def _persist_data(self) -> None:
        """Save data to CSV or database."""
        self._daily.to_csv(self._volume_path, index=False)
```

---

## PART 5: DATA STORAGE OPTIONS

### Option 1: CSV File Replacement (Simplest) ✅ **RECOMMENDED FOR CAPSTONE**

**Approach:** Replace `applicant_volume.csv` with new data

**Pros:**
- ✅ **Simplest implementation** - no database setup
- ✅ **Zero changes to existing code** - ForecastingRepository already reads CSV
- ✅ **Transparent** - can inspect data with any text editor
- ✅ **Version control friendly** - can git track changes
- ✅ **Fast for small datasets** (<100k rows)

**Cons:**
- ⚠️ Not suitable for very large datasets (>1M rows)
- ⚠️ File locking issues if multiple processes write
- ⚠️ No query optimization

**Implementation:**
```python
def _persist_data(self) -> None:
    """Save to CSV."""
    self._daily.to_csv(self._volume_path, index=False)
```

### Option 2: SQLite Database (Lightweight)

**Approach:** Store in embedded SQLite database

**Pros:**
- ✅ Lightweight (single file)
- ✅ SQL queries available
- ✅ ACID transactions
- ✅ Better for >100k rows

**Cons:**
- ⚠️ Requires schema migration
- ⚠️ Limited concurrency

**Schema:**
```sql
CREATE TABLE daily_volumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    course VARCHAR(255) NOT NULL,
    applicant_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, course)
);

CREATE INDEX idx_date ON daily_volumes(date);
CREATE INDEX idx_course ON daily_volumes(course);
```

### Option 3: PostgreSQL (Production-Grade)

**Approach:** Full relational database

**Pros:**
- ✅ Production-grade
- ✅ High concurrency
- ✅ Advanced features (views, stored procedures)

**Cons:**
- ❌ Requires separate database server
- ❌ More complex deployment
- ❌ Overkill for capstone

**Recommendation:** **Option 1 (CSV replacement)** for capstone simplicity.

---

## PART 6: MIGRATION PLAN

### Phase 1: Design & Documentation ✅ **CURRENT PHASE**
- [x] Analyze current architecture
- [x] Design production data ingestion endpoint
- [x] Document API contract
- [x] Define retraining strategy
- [ ] Review with team

### Phase 2: Python API Implementation
1. Create new route: `POST /forecast/ingest-data`
2. Add data validation logic
3. Implement `ForecastingRepository.upsert_daily_volumes()`
4. Implement `ForecastingService.retrain_models()`
5. Add retraining criteria logic
6. Add background task support (FastAPI BackgroundTasks)
7. Write unit tests for data ingestion
8. Test with sample Laravel data

### Phase 3: Laravel Implementation
1. Create `ForecastDataSyncController`
2. Add sync methods (full & incremental)
3. Add scheduled task (daily/weekly)
4. Add admin UI trigger button
5. Test with development database
6. Verify forecasts update correctly

### Phase 4: Integration Testing
1. Test full sync with real TLDC data
2. Test incremental sync
3. Verify model retraining works
4. Verify `GET /forecast/charts` still works (no changes!)
5. Performance testing (sync time, model training time)
6. Error handling testing

### Phase 5: Production Deployment
1. Deploy Python API with new endpoint
2. Deploy Laravel with sync controller
3. Run initial full sync
4. Enable scheduled syncs
5. Monitor for issues
6. Document for future maintainers

---

## PART 7: SYNTHETIC CSV DISPOSITION

### Question: Should `applicant_volume.csv` remain in the repository?

**Answer:** **YES, but mark it clearly as development data.**

### Recommended Approach

1. **Rename the file:**
   ```
   datasets/applicant_volume.csv
   →
   datasets/applicant_volume_SYNTHETIC_DEV_ONLY.csv
   ```

2. **Add README:**
   ```
   datasets/README.md:
   
   # Datasets Directory
   
   ## Development Data
   - `applicant_volume_SYNTHETIC_DEV_ONLY.csv` - Synthetic data for development/testing
     - 38,346 records (2021-2025)
     - 21 courses
     - DO NOT USE IN PRODUCTION
   
   ## Production Data
   - `applicant_volume.csv` - Real TLDC data (generated from Laravel sync)
     - Created by POST /forecast/ingest-data endpoint
     - Updated via scheduled Laravel sync
   ```

3. **Update .gitignore:**
   ```
   # Ignore production data
   datasets/applicant_volume.csv
   
   # Keep synthetic dev data in git
   !datasets/applicant_volume_SYNTHETIC_DEV_ONLY.csv
   ```

4. **Update ForecastingRepository default path:**
   ```python
   # Default to production data
   DEFAULT_VOLUME_PATH = PROJECT_ROOT / "datasets" / "applicant_volume.csv"
   
   # Fallback to synthetic if production doesn't exist yet
   if not DEFAULT_VOLUME_PATH.exists():
       DEFAULT_VOLUME_PATH = PROJECT_ROOT / "datasets" / "applicant_volume_SYNTHETIC_DEV_ONLY.csv"
   ```

### Rationale

**Keep synthetic CSV because:**
- ✅ Developers can run the API without Laravel database
- ✅ Testing doesn't require real data
- ✅ CI/CD pipelines can use it
- ✅ New developers can get started quickly

**Don't commit production CSV because:**
- ✅ Production data changes frequently
- ✅ Contains real TLDC information (even if aggregated)
- ✅ Avoids git repo bloat
- ✅ Synced from Laravel as source of truth

---

## PART 8: BACKWARD COMPATIBILITY

### Guarantee: ZERO Laravel Dashboard Changes Required

**Existing Laravel Integration:**
```php
// THIS WILL CONTINUE TO WORK UNCHANGED
$response = Http::get('http://localhost:8000/forecast/charts');
$data = $response->json();
```

**Why it works:**
1. ✅ `GET /forecast/charts` endpoint unchanged
2. ✅ Response structure unchanged
3. ✅ Only the data source changes (CSV → real data)
4. ✅ ForecastingRepository interface unchanged
5. ✅ ForecastingService interface unchanged

**What changes for Laravel:**
1. ✅ **Add** sync endpoint calls (new feature)
2. ✅ **Add** scheduled sync task (new feature)
3. ❌ **NO CHANGES** to dashboard GET requests

---

## PART 9: TESTING STRATEGY

### Unit Tests

```python
# tests/test_data_ingestion.py

def test_ingest_data_full_sync():
    """Test full data sync replaces all data."""
    payload = {
        "source": "laravel_tldc",
        "data_version": "1.0",
        "sync_type": "full",
        "date_range": {"start_date": "2026-01-01", "end_date": "2026-01-31"},
        "daily_volumes": [
            {"date": "2026-01-01", "course": "Cookery NC II", "applicant_count": 5},
            # ... more records
        ]
    }
    response = client.post("/forecast/ingest-data", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["records_received"] == len(payload["daily_volumes"])

def test_ingest_data_validation_errors():
    """Test validation catches invalid data."""
    payload = {
        "daily_volumes": [
            {"date": "invalid-date", "course": "Cookery NC II", "applicant_count": 5},
            {"date": "2026-01-01", "course": "Unknown Course", "applicant_count": 5},
            {"date": "2026-01-01", "course": "Cookery NC II", "applicant_count": -1},
        ]
    }
    response = client.post("/forecast/ingest-data", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert len(data["errors"]) == 3

def test_retraining_criteria():
    """Test retraining decision logic."""
    # Test sufficient new data
    should, reason = should_retrain(new_data_days=35, days_since_last_training=2, ...)
    assert should is True
    
    # Test scheduled interval
    should, reason = should_retrain(new_data_days=5, days_since_last_training=8, ...)
    assert should is True
    
    # Test no criteria met
    should, reason = should_retrain(new_data_days=5, days_since_last_training=2, ...)
    assert should is False
```

### Integration Tests

```python
def test_end_to_end_data_sync_and_forecast():
    """Test full flow: ingest data → retrain → get forecast."""
    # Step 1: Ingest real-like data
    payload = generate_realistic_daily_volumes()
    response = client.post("/forecast/ingest-data", json=payload)
    assert response.status_code == 202
    
    # Step 2: Wait for retraining (if background task)
    time.sleep(10)
    
    # Step 3: Verify forecasts updated
    response = client.get("/forecast/charts")
    assert response.status_code == 200
    data = response.json()
    assert len(data["forecast_curve"]) > 0
```

---

## PART 10: PERFORMANCE CONSIDERATIONS

### Expected Performance

**Data Ingestion:**
- 1,000 records: <1 second (validation + storage)
- 10,000 records: <5 seconds
- 38,346 records (5 years): <10 seconds

**Model Retraining:**
- 21 ARIMA(1,1,1) models: ~10-30 seconds
- Depends on dataset size (more weeks = longer training)

**Total Sync + Retrain:**
- Estimated: <60 seconds for full sync with retraining
- Estimated: <10 seconds for incremental sync without retraining

### Optimization Strategies

1. **Batch Validation**
   - Validate all records in parallel (vectorized operations)
   
2. **Incremental Sync**
   - Only send new data (last sync date tracking)
   
3. **Lazy Retraining**
   - Don't retrain for every sync
   - Use criteria-based triggers

4. **Cache Warming**
   - Pre-compute forecast responses after retraining

5. **Async Retraining**
   - Use FastAPI BackgroundTasks
   - Return 202 Accepted immediately

---

## PART 11: SECURITY CONSIDERATIONS

### Authentication

**Recommendation:** Require API key for data ingestion endpoint.

```python
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.getenv("FORECAST_INGEST_API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")

@router.post("/forecast/ingest-data", dependencies=[Depends(verify_api_key)])
def ingest_data(request: DataIngestionRequest):
    ...
```

**Laravel .env:**
```
FORECAST_INGEST_API_KEY=your-secure-key-here
```

### Data Validation

1. ✅ **Whitelist course names** - reject unknown courses
2. ✅ **Date range validation** - reject future dates, very old dates
3. ✅ **Count validation** - reject negative counts, unrealistic counts (e.g., >1000/day)
4. ✅ **Rate limiting** - limit sync requests to prevent abuse
5. ✅ **Request size limits** - max 10k records per request

### Privacy

- ✅ **No PII transfer** - only aggregated counts
- ✅ **No individual applicant data**
- ✅ **Safe for logs** - can log requests without privacy concerns

---

## PART 12: DOCUMENTATION UPDATES NEEDED

Once implemented, update:

1. **LARAVEL_TEST_REQUESTS.md**
   - Add section on data sync endpoint
   - Add sync examples

2. **FORECASTING_DATA_SOURCE.md**
   - Update to explain production flow
   - Remove "synthetic only" warnings
   - Add sync schedule info

3. **API_DOCUMENTATION.md**
   - Document `POST /forecast/ingest-data`
   - Document request/response schemas
   - Document retraining behavior

4. **README.md**
   - Add production setup instructions
   - Document Laravel sync setup

5. **DEPLOYMENT.md** (new)
   - Document production deployment
   - Document environment variables
   - Document monitoring

---

## SUMMARY & RECOMMENDATIONS

### ✅ Recommended Approach

1. **Data Format:** Pre-aggregated daily counts (Option B)
2. **Endpoint:** `POST /forecast/ingest-data`
3. **Storage:** CSV file replacement (simplest for capstone)
4. **Retraining:** Background task with criteria-based triggers
5. **Sync Schedule:** Daily incremental + weekly full
6. **Synthetic CSV:** Keep as `*_SYNTHETIC_DEV_ONLY.csv`

### 🎯 Key Benefits

- ✅ **Minimal Laravel changes** - simple GROUP BY query
- ✅ **Fast data transfer** - only aggregated counts
- ✅ **Privacy-safe** - no PII in API requests
- ✅ **Backward compatible** - GET /forecast/charts unchanged
- ✅ **Production-ready** - real data from Laravel database
- ✅ **Simple implementation** - CSV replacement, no database
- ✅ **Capstone-appropriate** - balances sophistication and feasibility

### 🚀 Next Steps

1. **Review this design** with team
2. **Implement Python endpoint** (`POST /forecast/ingest-data`)
3. **Implement Laravel sync** (controller + scheduled task)
4. **Test with real data**
5. **Deploy to production**
6. **Monitor and iterate**

---

**Document Status:** DESIGN COMPLETE - READY FOR REVIEW  
**Implementation Status:** NOT STARTED  
**Estimated Implementation Time:** 2-3 days (Python + Laravel)  
**Risk Level:** LOW (changes are isolated, backward compatible)

