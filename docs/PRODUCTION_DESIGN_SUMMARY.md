# Production Data Ingestion - Executive Summary

**Date:** 2026-08-13  
**Status:** Design Complete - Ready for Implementation  
**Estimated Implementation Time:** 2-3 days

---

## THE PROBLEM

Current forecasting API uses **synthetic CSV data** hard-coded in the repository. This requires API restart to update and does not use real TLDC application data from Laravel.

---

## THE SOLUTION

Create a **data ingestion endpoint** where Laravel sends real applicant data to Python API:

```
Laravel DB → SQL Aggregate → POST /forecast/ingest-data → Validate → Store → Retrain → Updated Forecasts
```

---

## KEY DECISIONS

### ✅ RECOMMENDED: Pre-Aggregated Daily Counts

**Laravel sends:**
```json
{
  "daily_volumes": [
    {"date": "2026-01-15", "course": "Cookery NC II", "applicant_count": 8},
    {"date": "2026-01-15", "course": "Driving NC II", "applicant_count": 5}
  ]
}
```

**Why:**
- ✅ Minimal payload (only what's needed for ARIMA)
- ✅ No PII transferred (privacy-safe)
- ✅ Fast processing (no aggregation in Python)
- ✅ Matches existing CSV structure exactly
- ✅ Simple Laravel implementation (one GROUP BY query)

### ✅ Storage: CSV File Replacement

**Why:**
- ✅ Simplest implementation (no database setup)
- ✅ Works with existing ForecastingRepository code
- ✅ Suitable for capstone project scale

### ✅ Retraining: Criteria-Based with Background Task

**Retraining triggers when ANY of:**
- New data days >= 30
- Days since last training >= 7
- Manual trigger flag
- Volume drift > 20%

**Implementation:** FastAPI BackgroundTasks (non-blocking)

---

## API CONTRACT

### New Endpoint: `POST /forecast/ingest-data`

**Request:**
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
    {"date": "2026-01-15", "course": "Cookery NC II", "applicant_count": 8}
  ]
}
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "ingestion_id": "ing_20260813_123456",
  "records_received": 1500,
  "retraining_scheduled": true,
  "retraining_reason": "Sufficient new data (30+ new days)"
}
```

---

## LARAVEL IMPLEMENTATION

### One SQL Query + One HTTP POST

```php
// 1. Aggregate daily counts
$dailyVolumes = DB::table('applications')
    ->select(
        DB::raw('DATE(application_date) as date'),
        'course',
        DB::raw('COUNT(*) as applicant_count')
    )
    ->groupBy('date', 'course')
    ->get();

// 2. Send to Python API
$response = Http::post(
    config('services.forecast_api.url') . '/forecast/ingest-data',
    ['daily_volumes' => $dailyVolumes, 'sync_type' => 'full']
);
```

### Scheduled Sync

```php
// Daily incremental at midnight
$schedule->call(function () {
    Http::post(route('admin.sync-forecast-data'));
})->daily()->at('00:00');
```

---

## ZERO BREAKING CHANGES

### Laravel Dashboard Integration (UNCHANGED)

```php
// THIS WILL CONTINUE TO WORK EXACTLY AS BEFORE
$response = Http::get('http://localhost:8000/forecast/charts');
$data = $response->json();
// Same JSON structure, same fields, same everything
// Only difference: data is now REAL instead of synthetic
```

**Guarantee:**
- ✅ GET /forecast/charts endpoint unchanged
- ✅ Response structure unchanged
- ✅ No Laravel dashboard code changes needed

---

## IMPLEMENTATION PHASES

### Phase 1: Python API (1 day)
1. Create `routes/data_ingestion.py`
2. Add `ForecastingRepository.upsert_daily_volumes()`
3. Add `ForecastingService.retrain_models()`
4. Implement validation and retraining logic
5. Write tests

### Phase 2: Laravel (0.5 day)
1. Create `ForecastDataSyncController`
2. Add sync route
3. Add scheduled task
4. Test with real database

### Phase 3: Testing & Deployment (1 day)
1. Integration testing
2. Deploy Python API
3. Deploy Laravel changes
4. Run initial sync
5. Monitor

---

## FILE STRUCTURE CHANGES

### New Files
```
routes/data_ingestion.py          # New endpoint
services/data_validation_service.py  # Validation logic
tests/test_data_ingestion.py      # Tests
docs/PRODUCTION_DATA_INGESTION_DESIGN.md  # This design
docs/PRODUCTION_FLOW_DIAGRAM.md   # Visual diagrams
docs/IMPLEMENTATION_CHECKLIST.md  # Step-by-step guide
```

### Modified Files
```
services/forecasting_repository.py  # Add upsert_daily_volumes()
services/forecasting_service.py     # Add retrain_models()
main.py                             # Register new route
.gitignore                          # Ignore production CSV
```

### Renamed Files
```
datasets/applicant_volume.csv 
→ datasets/applicant_volume_SYNTHETIC_DEV_ONLY.csv
```

---

## SYNTHETIC CSV DISPOSITION

**Keep synthetic CSV for:**
- ✅ Development without Laravel database
- ✅ Testing
- ✅ CI/CD pipelines
- ✅ New developer onboarding

**Rename to:** `applicant_volume_SYNTHETIC_DEV_ONLY.csv`

**Gitignore production CSV:** `applicant_volume.csv` (generated from Laravel)

**Fallback logic:** Use synthetic if production CSV doesn't exist yet

---

## PERFORMANCE EXPECTATIONS

**Data Ingestion:**
- 1,000 records: <1 second
- 10,000 records: <5 seconds
- 38,346 records (full): <10 seconds

**Model Retraining:**
- 21 ARIMA models: ~10-30 seconds
- Background task (non-blocking)

**Total Sync Time:**
- Full sync + retrain: <60 seconds
- Incremental sync (no retrain): <10 seconds

---

## SECURITY

**API Key Authentication (Optional):**
```python
@router.post("/forecast/ingest-data", dependencies=[Depends(verify_api_key)])
```

**Data Validation:**
- ✅ Whitelist course names
- ✅ Date range validation
- ✅ Count validation (non-negative, realistic)
- ✅ Rate limiting

**Privacy:**
- ✅ No PII transferred (only aggregated counts)
- ✅ Safe for logs

---

## TESTING STRATEGY

### Unit Tests
- ✅ Valid data ingestion
- ✅ Invalid date format
- ✅ Unknown course
- ✅ Negative count
- ✅ Duplicate detection
- ✅ Retraining logic

### Integration Tests
- ✅ End-to-end: ingest → retrain → forecast
- ✅ Full sync mode
- ✅ Incremental sync mode
- ✅ Laravel sync from real database

---

## ROLLBACK PLAN

If production deployment has issues:

1. **Revert Python API** to previous version
2. **Disable Laravel sync** (comment out scheduled task)
3. **Restore synthetic CSV** as `applicant_volume.csv`
4. **Dashboard continues working** (GET /forecast/charts unchanged)

**Risk Level:** LOW (changes are isolated, backward compatible)

---

## DOCUMENTATION

### For Laravel Developer
- ✅ `LARAVEL_TEST_REQUESTS.md` - Test examples (updated)
- ✅ `FORECASTING_DATA_SOURCE.md` - Data source explanation (updated)
- ✅ `QUICK_REFERENCE_LARAVEL.md` - Quick reference card

### For Python Developer
- ✅ `PRODUCTION_DATA_INGESTION_DESIGN.md` - Full design spec
- ✅ `PRODUCTION_FLOW_DIAGRAM.md` - Visual diagrams
- ✅ `IMPLEMENTATION_CHECKLIST.md` - Step-by-step implementation
- ✅ `API_DOCUMENTATION.md` - API reference (to be updated)

---

## SUCCESS METRICS

- [ ] Python API accepts real data from Laravel
- [ ] Models retrain automatically (criteria-based)
- [ ] Forecasts update with real TLDC data
- [ ] Laravel scheduled sync runs daily
- [ ] Zero breaking changes to dashboard
- [ ] All tests passing
- [ ] Performance meets expectations
- [ ] Documentation complete

---

## NEXT STEPS

1. **Review Design** - Team review this document
2. **Approve Design** - Get stakeholder sign-off
3. **Begin Implementation** - Follow `IMPLEMENTATION_CHECKLIST.md`
4. **Test Thoroughly** - Unit + integration tests
5. **Deploy to Production** - Phased rollout
6. **Monitor** - Watch for issues, iterate

---

## KEY CONTACTS

**Laravel Developer:** Needs to implement sync controller  
**Python Developer:** Needs to implement ingestion endpoint  
**Database Admin:** May need to verify application table schema  
**DevOps:** Needs to configure scheduled tasks

---

## FREQUENTLY ASKED QUESTIONS

### Q: Will the dashboard stop working during this change?
**A:** No. GET /forecast/charts endpoint is 100% unchanged. Dashboard works throughout migration.

### Q: Do we need to modify the dashboard code?
**A:** No. Laravel dashboard code remains unchanged. Only backend data source changes.

### Q: What if the sync fails?
**A:** Forecasts continue using existing data. Sync can be retried. No data loss.

### Q: How often should we sync?
**A:** Recommended: Daily incremental + weekly full sync. Adjustable based on needs.

### Q: Can we use real data immediately?
**A:** Yes, once implemented. Run one full sync and forecasts will use real data.

### Q: What about the synthetic CSV?
**A:** Keep it renamed as `*_SYNTHETIC_DEV_ONLY.csv` for development/testing.

### Q: Will this scale to more data?
**A:** Yes. CSV handles 100k+ rows. Can migrate to database later if needed.

### Q: How do we trigger manual retraining?
**A:** Set `"manual_retrain": true` in the ingestion request.

---

## CONCLUSION

This design provides a **production-ready data ingestion solution** that:

✅ Uses real TLDC data from Laravel  
✅ Requires minimal Laravel changes (one query + one POST)  
✅ No breaking changes to dashboard  
✅ Privacy-safe (no PII transfer)  
✅ Simple implementation (CSV replacement)  
✅ Automatic model updates (criteria-based)  
✅ Suitable for capstone project scope  

**Estimated effort:** 2-3 days implementation + testing  
**Risk level:** LOW  
**Recommendation:** PROCEED with implementation

---

**Document Version:** 1.0  
**Last Updated:** 2026-08-13  
**Status:** ✅ DESIGN COMPLETE - READY FOR IMPLEMENTATION
