# Production Data Ingestion - Implementation Checklist

**Date:** 2026-08-13  
**Purpose:** Step-by-step implementation guide  
**Estimated Time:** 2-3 days

---

## OVERVIEW

This checklist guides the implementation of production data ingestion from Laravel to the Python forecasting API.

**Key Documents:**
- `PRODUCTION_DATA_INGESTION_DESIGN.md` - Full design specification
- `PRODUCTION_FLOW_DIAGRAM.md` - Visual architecture diagrams
- This document - Implementation steps

---

## PHASE 1: PYTHON API - DATA INGESTION ENDPOINT

### 1.1 Create Request/Response Models

**File:** `routes/data_ingestion.py` (new file)

```python
from pydantic import BaseModel, Field, validator
from typing import Literal

class DailyVolumeRecord(BaseModel):
    date: str = Field(..., description="Application date in YYYY-MM-DD format")
    course: str = Field(..., description="Course name")
    applicant_count: int = Field(..., ge=0, description="Number of applicants")
    
    @validator('date')
    def validate_date(cls, v):
        from datetime import datetime
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format')
        return v

class DateRange(BaseModel):
    start_date: str
    end_date: str

class DataIngestionRequest(BaseModel):
    source: str = Field(..., description="Data source identifier")
    data_version: str = Field(default="1.0", description="API version")
    sync_type: Literal["full", "incremental"] = Field(..., description="Sync mode")
    date_range: DateRange
    daily_volumes: list[DailyVolumeRecord]
    manual_retrain: bool = Field(default=False, description="Force retraining")

class DataIngestionResponse(BaseModel):
    status: str
    message: str
    ingestion_id: str
    records_received: int
    records_valid: int
    date_range: DateRange
    sync_type: str
    estimated_processing_time_seconds: int
    retraining_scheduled: bool
    retraining_reason: str | None
    next_steps: list[str]
```

**Checklist:**
- [ ] Create `routes/data_ingestion.py`
- [ ] Define all Pydantic models
- [ ] Add validation for dates, courses, counts
- [ ] Test model validation with invalid data

### 1.2 Implement Validation Logic

**File:** `services/data_validation_service.py` (new file)

```python
from services.forecasting_repository import get_forecasting_repository

class DataValidationService:
    def __init__(self):
        self._repository = get_forecasting_repository()
        self._valid_courses = set(self._repository.get_available_courses())
    
    def validate_records(self, records: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        Validate daily volume records.
        
        Returns:
            (valid_records, errors)
        """
        valid = []
        errors = []
        seen = set()
        
        for idx, record in enumerate(records):
            record_errors = []
            
            # Validate course
            if record['course'] not in self._valid_courses:
                record_errors.append({
                    "field": f"daily_volumes[{idx}].course",
                    "error": f"Unknown course '{record['course']}'"
                })
            
            # Validate applicant_count
            if record['applicant_count'] < 0:
                record_errors.append({
                    "field": f"daily_volumes[{idx}].applicant_count",
                    "error": "Applicant count must be non-negative"
                })
            
            # Check for duplicates
            key = (record['date'], record['course'])
            if key in seen:
                record_errors.append({
                    "field": f"daily_volumes[{idx}]",
                    "error": f"Duplicate record for {key}"
                })
            seen.add(key)
            
            if record_errors:
                errors.extend(record_errors)
            else:
                valid.append(record)
        
        return valid, errors
```

**Checklist:**
- [ ] Create `services/data_validation_service.py`
- [ ] Implement course validation
- [ ] Implement count validation
- [ ] Implement duplicate detection
- [ ] Add unit tests for validation

### 1.3 Extend ForecastingRepository

**File:** `services/forecasting_repository.py` (modify existing)

**Add these methods:**

```python
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
    import pandas as pd
    
    new_df = pd.DataFrame(daily_volumes)
    new_df['date'] = pd.to_datetime(new_df['date'])
    
    if sync_type == "full":
        # Replace entire dataset
        self._daily = new_df.sort_values(['course', 'date']).reset_index(drop=True)
    else:
        # Incremental: remove duplicates, append new
        self._daily = pd.concat([self._daily, new_df], ignore_index=True)
        self._daily = self._daily.drop_duplicates(
            subset=['date', 'course'],
            keep='last'
        )
        self._daily = self._daily.sort_values(['course', 'date']).reset_index(drop=True)
    
    # Persist to storage
    self._persist_data()
    
    return {
        "total_records": len(self._daily),
        "new_records_added": len(new_df),
        "date_range": {
            "start": str(self._daily['date'].min().date()),
            "end": str(self._daily['date'].max().date())
        }
    }

def _persist_data(self) -> None:
    """Save data to CSV."""
    self._daily.to_csv(self._volume_path, index=False)

def reload_data(self) -> None:
    """Reload the daily volume dataset from storage."""
    self._daily = self._load_daily(self._volume_path)

def get_new_data_days_count(self, since_date: str) -> int:
    """Count unique dates added since a given date."""
    import pandas as pd
    since = pd.to_datetime(since_date)
    return len(self._daily[self._daily['date'] > since]['date'].unique())
```

**Checklist:**
- [ ] Add `upsert_daily_volumes()` method
- [ ] Add `_persist_data()` method
- [ ] Add `reload_data()` method
- [ ] Add `get_new_data_days_count()` method
- [ ] Test full sync mode
- [ ] Test incremental sync mode
- [ ] Test duplicate handling

### 1.4 Extend ForecastingService

**File:** `services/forecasting_service.py` (modify existing)

**Add these methods:**

```python
from datetime import datetime
import time

def __init__(self, repository=None, statistics=None):
    # ... existing code ...
    self._last_training_time: datetime | None = None
    self._fit_course_models()
    self._last_training_time = datetime.now()

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

def get_last_training_time(self) -> datetime | None:
    """Return when models were last trained."""
    return self._last_training_time

def should_retrain(
    self,
    new_data_days: int,
    manual_trigger: bool = False
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
    
    if self._last_training_time:
        days_since = (datetime.now() - self._last_training_time).days
        if days_since >= 7:
            return True, f"Scheduled retraining ({days_since} days since last)"
    
    return False, "No retraining criteria met"
```

**Checklist:**
- [ ] Add `_last_training_time` attribute
- [ ] Add `retrain_models()` method
- [ ] Add `get_last_training_time()` method
- [ ] Add `should_retrain()` method
- [ ] Test retraining with new data
- [ ] Verify caches are cleared
- [ ] Verify forecasts update after retrain

### 1.5 Create Data Ingestion Route

**File:** `routes/data_ingestion.py`

```python
from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from services.forecasting_repository import get_forecasting_repository
from services.forecasting_service import get_forecasting_service
from services.data_validation_service import DataValidationService
import uuid
from datetime import datetime

router = APIRouter(prefix="/forecast", tags=["Data Ingestion"])

def retrain_models_task():
    """Background task to retrain models."""
    service = get_forecasting_service()
    service.retrain_models()

@router.post("/ingest-data")
def ingest_data(
    request: DataIngestionRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(None)
):
    """
    Ingest daily applicant volume data from Laravel.
    
    Validates, stores, and optionally retrains ARIMA models.
    """
    # Optional: Verify API key
    # if x_api_key != os.getenv("FORECAST_INGEST_API_KEY"):
    #     raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Validate
    validator = DataValidationService()
    valid_records, errors = validator.validate_records(
        [r.dict() for r in request.daily_volumes]
    )
    
    if errors:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "error_code": "INVALID_DATA_FORMAT",
                "message": "Validation failed",
                "errors": errors,
                "records_received": len(request.daily_volumes),
                "records_valid": len(valid_records),
                "records_invalid": len(errors)
            }
        )
    
    # Store
    repository = get_forecasting_repository()
    metrics = repository.upsert_daily_volumes(
        valid_records,
        sync_type=request.sync_type
    )
    
    # Check retraining criteria
    service = get_forecasting_service()
    
    # Calculate new data days
    if request.sync_type == "incremental":
        last_train = service.get_last_training_time()
        if last_train:
            new_days = repository.get_new_data_days_count(
                last_train.strftime('%Y-%m-%d')
            )
        else:
            new_days = 0
    else:
        new_days = 999  # Full sync always retrains
    
    should_retrain, reason = service.should_retrain(
        new_data_days=new_days,
        manual_trigger=request.manual_retrain
    )
    
    # Schedule retraining if needed
    if should_retrain:
        background_tasks.add_task(retrain_models_task)
    
    # Generate ingestion ID
    ingestion_id = f"ing_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    return {
        "status": "accepted",
        "message": "Data ingestion completed successfully",
        "ingestion_id": ingestion_id,
        "records_received": len(request.daily_volumes),
        "records_valid": len(valid_records),
        "date_range": request.date_range.dict(),
        "sync_type": request.sync_type,
        "estimated_processing_time_seconds": 30 if should_retrain else 0,
        "retraining_scheduled": should_retrain,
        "retraining_reason": reason if should_retrain else None,
        "next_steps": [
            "Data has been validated and stored",
            "Models will be retrained in background" if should_retrain else "Existing models retained",
            "Forecasts will be available after processing" if should_retrain else "Forecasts are immediately available"
        ]
    }
```

**Checklist:**
- [ ] Create route file
- [ ] Implement POST /forecast/ingest-data
- [ ] Add validation logic
- [ ] Add storage logic
- [ ] Add retraining decision logic
- [ ] Add background task scheduling
- [ ] Test with valid data
- [ ] Test with invalid data
- [ ] Test error responses

### 1.6 Register Route in main.py

**File:** `main.py` (modify existing)

```python
from routes import data_ingestion  # Add this import

# ... existing code ...

app.include_router(data_ingestion.router)  # Add this line
```

**Checklist:**
- [ ] Import data_ingestion router
- [ ] Register router with app
- [ ] Verify /docs shows new endpoint

---

## PHASE 2: PYTHON API - TESTING

### 2.1 Unit Tests

**File:** `tests/test_data_ingestion.py` (new file)

```python
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_ingest_data_valid():
    """Test successful data ingestion."""
    payload = {
        "source": "laravel_tldc",
        "data_version": "1.0",
        "sync_type": "incremental",
        "date_range": {
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        },
        "daily_volumes": [
            {"date": "2026-01-01", "course": "Cookery NC II", "applicant_count": 5},
            {"date": "2026-01-01", "course": "Driving NC II", "applicant_count": 3}
        ]
    }
    response = client.post("/forecast/ingest-data", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["records_valid"] == 2

def test_ingest_data_invalid_date():
    """Test validation catches invalid date format."""
    payload = {
        "source": "laravel_tldc",
        "data_version": "1.0",
        "sync_type": "incremental",
        "date_range": {"start_date": "2026-01-01", "end_date": "2026-01-31"},
        "daily_volumes": [
            {"date": "2026-99-99", "course": "Cookery NC II", "applicant_count": 5}
        ]
    }
    response = client.post("/forecast/ingest-data", json=payload)
    assert response.status_code == 400

def test_ingest_data_invalid_course():
    """Test validation catches unknown course."""
    payload = {
        "source": "laravel_tldc",
        "data_version": "1.0",
        "sync_type": "incremental",
        "date_range": {"start_date": "2026-01-01", "end_date": "2026-01-31"},
        "daily_volumes": [
            {"date": "2026-01-01", "course": "Invalid Course", "applicant_count": 5}
        ]
    }
    response = client.post("/forecast/ingest-data", json=payload)
    assert response.status_code == 400

def test_ingest_data_negative_count():
    """Test validation catches negative count."""
    payload = {
        "source": "laravel_tldc",
        "data_version": "1.0",
        "sync_type": "incremental",
        "date_range": {"start_date": "2026-01-01", "end_date": "2026-01-31"},
        "daily_volumes": [
            {"date": "2026-01-01", "course": "Cookery NC II", "applicant_count": -5}
        ]
    }
    response = client.post("/forecast/ingest-data", json=payload)
    assert response.status_code == 422  # Pydantic validation

def test_retrain_logic():
    """Test retraining decision logic."""
    from services.forecasting_service import get_forecasting_service
    service = get_forecasting_service()
    
    # Manual trigger
    should, reason = service.should_retrain(new_data_days=5, manual_trigger=True)
    assert should is True
    
    # Sufficient new data
    should, reason = service.should_retrain(new_data_days=35, manual_trigger=False)
    assert should is True
    
    # No criteria met
    should, reason = service.should_retrain(new_data_days=5, manual_trigger=False)
    assert should is False
```

**Checklist:**
- [ ] Create test file
- [ ] Test successful ingestion
- [ ] Test invalid date format
- [ ] Test invalid course
- [ ] Test negative count
- [ ] Test retraining logic
- [ ] All tests pass

### 2.2 Integration Tests

```python
def test_end_to_end_sync_and_forecast():
    """Test full flow: ingest → retrain → forecast."""
    # Step 1: Ingest data
    payload = generate_test_payload()
    response = client.post("/forecast/ingest-data", json=payload)
    assert response.status_code == 200
    
    # Step 2: Wait for background task (if needed)
    import time
    time.sleep(15)
    
    # Step 3: Verify forecast works
    response = client.get("/forecast/charts")
    assert response.status_code == 200
    data = response.json()
    assert len(data["forecast_curve"]) > 0
```

**Checklist:**
- [ ] Test end-to-end flow
- [ ] Verify forecasts update
- [ ] Test both sync modes (full/incremental)

---

## PHASE 3: LARAVEL - SYNC CONTROLLER

### 3.1 Create Controller

**File:** `app/Http/Controllers/ForecastDataSyncController.php` (new file)

```php
<?php

namespace App\Http\Controllers;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class ForecastDataSyncController extends Controller
{
    public function syncForecastingData()
    {
        // Step 1: Aggregate
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

        // Step 3: Build payload
        $payload = [
            'source' => 'laravel_tldc',
            'data_version' => '1.0',
            'sync_type' => 'full',
            'date_range' => [
                'start_date' => $startDate,
                'end_date' => $endDate
            ],
            'daily_volumes' => $dailyVolumes
        ];

        // Step 4: Send to API
        try {
            $response = Http::timeout(120)
                ->post(config('services.forecast_api.url') . '/forecast/ingest-data', $payload);

            if ($response->successful()) {
                $data = $response->json();
                
                Log::info('Forecast data sync successful', [
                    'ingestion_id' => $data['ingestion_id'],
                    'records_sent' => count($dailyVolumes)
                ]);

                return response()->json([
                    'success' => true,
                    'message' => 'Forecast data synchronized successfully',
                    'data' => $data
                ]);
            } else {
                Log::error('Forecast data sync failed', [
                    'status' => $response->status(),
                    'error' => $response->json()
                ]);

                return response()->json([
                    'success' => false,
                    'message' => 'Failed to sync forecast data',
                    'error' => $response->json()
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
}
```

**Checklist:**
- [ ] Create controller file
- [ ] Implement syncForecastingData() method
- [ ] Test SQL aggregation query
- [ ] Test HTTP request to Python API
- [ ] Add error handling
- [ ] Add logging

### 3.2 Add Routes

**File:** `routes/api.php` (modify existing)

```php
use App\Http\Controllers\ForecastDataSyncController;

Route::post('/admin/sync-forecast-data', [ForecastDataSyncController::class, 'syncForecastingData']);
```

**Checklist:**
- [ ] Add route
- [ ] Test route manually (Postman/curl)

### 3.3 Add Configuration

**File:** `config/services.php` (modify existing)

```php
return [
    'forecast_api' => [
        'url' => env('FORECAST_API_URL', 'http://localhost:8000'),
    ],
];
```

**File:** `.env`

```
FORECAST_API_URL=http://localhost:8000
```

**Checklist:**
- [ ] Add config
- [ ] Add .env variable
- [ ] Test config reads correctly

---

## PHASE 4: LARAVEL - SCHEDULED SYNC

### 4.1 Add Scheduled Task

**File:** `app/Console/Kernel.php` (modify existing)

```php
protected function schedule(Schedule $schedule)
{
    // Daily incremental sync at midnight
    $schedule->call(function () {
        Http::post(route('admin.sync-forecast-data'));
    })->daily()->at('00:00');
}
```

**Checklist:**
- [ ] Add scheduled task
- [ ] Test with `php artisan schedule:run`
- [ ] Verify cron is configured on server

---

## PHASE 5: SYNTHETIC CSV DISPOSITION

### 5.1 Rename Synthetic Data

**Steps:**
1. Rename `datasets/applicant_volume.csv` to `datasets/applicant_volume_SYNTHETIC_DEV_ONLY.csv`
2. Create `datasets/README.md` with explanation
3. Update `.gitignore` to ignore production `applicant_volume.csv`
4. Update `ForecastingRepository` to fall back to synthetic if production doesn't exist

**Checklist:**
- [ ] Rename synthetic CSV
- [ ] Create datasets/README.md
- [ ] Update .gitignore
- [ ] Update ForecastingRepository fallback logic
- [ ] Test API starts with synthetic data
- [ ] Test API works with production data

---

## PHASE 6: DOCUMENTATION UPDATES

### 6.1 Update Existing Docs

**Files to update:**
- [ ] `LARAVEL_TEST_REQUESTS.md` - Add data sync section
- [ ] `FORECASTING_DATA_SOURCE.md` - Update with production flow
- [ ] `API_DOCUMENTATION.md` - Document new endpoint
- [ ] `README.md` - Add production setup instructions

---

## PHASE 7: DEPLOYMENT

### 7.1 Python API Deployment

**Checklist:**
- [ ] Deploy to Vercel/hosting
- [ ] Verify all endpoints work
- [ ] Test POST /forecast/ingest-data
- [ ] Test GET /forecast/charts still works

### 7.2 Laravel Deployment

**Checklist:**
- [ ] Deploy controller changes
- [ ] Set FORECAST_API_URL in production
- [ ] Run initial full sync
- [ ] Verify scheduled tasks are running
- [ ] Monitor logs for errors

### 7.3 Monitoring

**Checklist:**
- [ ] Monitor sync success rate
- [ ] Monitor model retraining frequency
- [ ] Monitor API response times
- [ ] Set up alerts for failures

---

## TESTING MATRIX

| Test Case | Expected Result | Status |
|-----------|----------------|--------|
| POST /forecast/ingest-data with valid data | 200/202 Accepted | ⬜ |
| POST /forecast/ingest-data with invalid date | 400 Bad Request | ⬜ |
| POST /forecast/ingest-data with unknown course | 400 Bad Request | ⬜ |
| POST /forecast/ingest-data with negative count | 422 Unprocessable | ⬜ |
| Full sync replaces all data | Data replaced | ⬜ |
| Incremental sync appends data | Data appended | ⬜ |
| Retraining triggers with 30+ new days | Models retrained | ⬜ |
| Retraining skipped with <30 new days | Models not retrained | ⬜ |
| GET /forecast/charts after ingestion | Updated forecasts | ⬜ |
| Laravel sync sends correct format | API accepts | ⬜ |
| Laravel scheduled sync runs | Sync completes | ⬜ |

---

## ROLLBACK PLAN

If issues occur during production deployment:

1. **Revert Python API changes**
   - Deploy previous version
   - CSV fallback to synthetic data still works

2. **Disable Laravel sync**
   - Comment out scheduled task
   - Remove route if needed

3. **Restore synthetic CSV**
   - Copy `applicant_volume_SYNTHETIC_DEV_ONLY.csv` back to `applicant_volume.csv`
   - Restart API

**Dashboard will continue working** - GET /forecast/charts is unchanged!

---

## SUCCESS CRITERIA

- [ ] Python API accepts data from Laravel
- [ ] Data validation works correctly
- [ ] Models retrain automatically when criteria met
- [ ] GET /forecast/charts returns updated forecasts
- [ ] Laravel scheduled sync runs successfully
- [ ] No breaking changes to dashboard
- [ ] All tests pass
- [ ] Documentation complete

---

**Estimated Timeline:**
- Phase 1-2 (Python): 1 day
- Phase 3-4 (Laravel): 0.5 day
- Phase 5-6 (Cleanup/Docs): 0.5 day
- Phase 7 (Deployment/Testing): 0.5-1 day
- **Total: 2.5-3 days**

---

**Ready to Start:** Review this checklist → Begin Phase 1
