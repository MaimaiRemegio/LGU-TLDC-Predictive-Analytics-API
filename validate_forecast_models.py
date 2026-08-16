"""
Comprehensive Forecast Model Quality Validation and Evaluation

This script performs a complete validation of the 21 course-specific ARIMA models
without modifying production code or models.
"""

import sys
import json
from pathlib import Path
import warnings

sys.path.insert(0, 'services')

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.iolib.smpickle import load_pickle

from forecasting_repository import ForecastingRepository, get_forecasting_repository
from forecasting_service import ForecastingService, get_forecasting_service, ARIMA_ORDER
from forecasting_evaluation import (
    walk_forward_backtest,
    compute_forecast_metrics,
    classify_mape,
    chronological_split_index,
)

# Suppress ARIMA warnings for cleaner output
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parent
MODELS_DIR = PROJECT_ROOT / "trained_models" / "forecasting" / "models"
METADATA_DIR = PROJECT_ROOT / "trained_models" / "forecasting" / "metadata"
MODEL_REGISTRY_FILE = METADATA_DIR / "model_registry.json"

print("="*80)
print("FORECAST MODEL QUALITY VALIDATION AND EVALUATION")
print("="*80)
print()

# =============================================================================
# SECTION 1: INSPECT CURRENT FORECASTING IMPLEMENTATION
# =============================================================================

print("SECTION 1: CURRENT FORECASTING IMPLEMENTATION")
print("-"*80)

print("\n1.1 Training Process:")
print("  - Models trained: 21 (one per course)")
print("  - Data source: datasets/applicant_volume.csv")
print("  - Training frequency: WEEKLY (W-SUN)")
print("  - Daily data aggregated to weekly totals before ARIMA")
print("  - ARIMA order: (1, 1, 1) for all courses")
print("  - Model persistence: .pkl files using statsmodels save/load")

print("\n1.2 Forecast Generation:")
print("  - Horizon: 52 weeks (pre-computed at startup)")
print("  - next_week: step 1")
print("  - next_month: sum of steps 1-4")
print("  - next_quarter: sum of steps 1-13")

print("\n1.3 Missing Values:")
print("  - Repository filters data to HISTORICAL_CUTOFF_DATE")
print("  - .resample() fills gaps with zeros (addressed in previous fix)")
print("  - No NaN values in training data")

print("\n1.4 Forecast Transformations:")
print("  - Negative forecasts: Clipped to 0.0 (max(0.0, pred))")
print("  - Rounding: Yes, to 2 decimal places")
print("  - No other transformations applied")

print("\n1.5 Course to Model Mapping:")
print("  - Course name -> sanitized filename")
print("  - Example: 'Cookery NC II' -> 'Cookery_NC_II_v1.pkl'")

print("\n1.6 Existing Evaluation:")
print("  - Module: services/forecasting_evaluation.py")
print("  - Method: Walk-forward chronological backtesting")
print("  - Metrics: MAE, RMSE, MAPE")
print("  - Endpoint: GET /forecast/evaluation")

# =============================================================================
# SECTION 2: INSPECT ALL 21 TRAINED MODELS
# =============================================================================

print("\n\n" + "="*80)
print("SECTION 2: INSPECT ALL 21 TRAINED MODELS")
print("-"*80)

# Load registry
with open(MODEL_REGISTRY_FILE) as f:
    registry = json.load(f)

print(f"\nRegistry loaded: {len(registry['models'])} courses")
print(f"Active version: {registry['active_version']}")
print(f"Last training: {registry['last_training_time']}")
print(f"ARIMA order (global): {registry['arima_order']}")

print("\n\nMODEL INVENTORY:")
print(f"{'Course':<50} {'File':<40} {'ARIMA':<12} {'Obs':<6} {'Start':<12} {'End':<12} {'Loaded'}")
print("-"*160)

model_details = []
for course, meta in sorted(registry['models'].items()):
    model_path = PROJECT_ROOT / "trained_models" / "forecasting" / meta['file']
    
    # Try to load model
    try:
        model = load_pickle(str(model_path))
        loaded = "✓"
    except Exception as e:
        loaded = f"✗ {str(e)[:20]}"
    
    arima_str = f"({','.join(map(str, meta['arima_order']))})"
    
    print(f"{course:<50} {meta['file'][-40:]:<40} {arima_str:<12} {meta['observations']:<6} "
          f"{meta['data_start_date']:<12} {meta['data_end_date']:<12} {loaded}")
    
    model_details.append({
        'course': course,
        'file': meta['file'],
        'arima_order': tuple(meta['arima_order']),
        'observations': meta['observations'],
        'start_date': meta['data_start_date'],
        'end_date': meta['data_end_date'],
        'loaded': loaded == "✓"
    })

print(f"\nSummary: {sum(1 for m in model_details if m['loaded'])}/{len(model_details)} models loaded successfully")

# =============================================================================
# SECTION 3: HISTORICAL HOLDOUT BACKTESTING
# =============================================================================

print("\n\n" + "="*80)
print("SECTION 3: HISTORICAL HOLDOUT BACKTESTING")
print("-"*80)

print("\nBacktesting Methodology:")
print("  - Approach: Walk-forward expanding window")
print("  - Train/test split: 80/20 chronological")
print("  - Training period: ~first 210 weeks (~4 years)")
print("  - Test period: ~last 52 weeks (~1 year)")
print("  - Evaluation: One-step-ahead weekly forecasts")
print("  - Rationale: Simulates realistic forecasting scenario")

print("\nPerforming backtesting for all 21 courses...")
print("(This may take 2-3 minutes)")

repository = get_forecasting_repository()
courses = repository.get_available_courses()

backtest_results = []

for i, course in enumerate(courses, 1):
    print(f"\n[{i}/21] {course}")
    
    try:
        # Get weekly series for this course
        series = repository.get_course_series(course)
        
        if series.empty or len(series) < 50:
            print(f"  ERROR: Insufficient data ({len(series)} periods)")
            backtest_results.append({
                'course': course,
                'error': 'Insufficient data',
                'mae': None,
                'rmse': None,
                'mape': None,
                'test_periods': 0
            })
            continue
        
        # Perform walk-forward backtest
        result = walk_forward_backtest(series, train_ratio=0.8)
        
        print(f"  MAE: {result.mae if result.mae is not None else 'N/A'}")
        print(f"  RMSE: {result.rmse if result.rmse is not None else 'N/A'}")
        print(f"  MAPE: {result.mape if result.mape is not None else 'N/A'}%")
        print(f"  Test periods: {result.test_periods}")
        print(f"  Assessment: {classify_mape(result.mape)}")
        
        backtest_results.append({
            'course': course,
            'mae': result.mae,
            'rmse': result.rmse,
            'mape': result.mape,
            'test_periods': result.test_periods,
            'mape_periods': result.mape_periods,
            'assessment': classify_mape(result.mape),
            'actuals_mean': np.mean(result.actuals) if result.actuals else 0,
            'actuals_std': np.std(result.actuals) if result.actuals else 0,
        })
        
    except Exception as e:
        print(f"  ERROR: {str(e)}")
        backtest_results.append({
            'course': course,
            'error': str(e),
            'mae': None,
            'rmse': None,
            'mape': None,
            'test_periods': 0
        })

# =============================================================================
# SECTION 4: EVALUATION METRICS SUMMARY
# =============================================================================

print("\n\n" + "="*80)
print("SECTION 4: EVALUATION METRICS SUMMARY")
print("-"*80)

print("\n\nPERFORMANCE TABLE:")
print(f"{'Course':<50} {'MAE':<10} {'RMSE':<10} {'MAPE%':<10} {'Assessment':<20}")
print("-"*100)

for result in backtest_results:
    mae_str = f"{result['mae']:.2f}" if result['mae'] is not None else "N/A"
    rmse_str = f"{result['rmse']:.2f}" if result['rmse'] is not None else "N/A"
    mape_str = f"{result['mape']:.2f}" if result['mape'] is not None else "N/A"
    assessment = result.get('assessment', 'Error')
    
    print(f"{result['course']:<50} {mae_str:<10} {rmse_str:<10} {mape_str:<10} {assessment:<20}")

# Calculate aggregate statistics
valid_results = [r for r in backtest_results if r.get('mae') is not None]

if valid_results:
    print("\n\nAGGREGATE STATISTICS:")
    print(f"  Models evaluated: {len(valid_results)}")
    print(f"  Average MAE: {np.mean([r['mae'] for r in valid_results]):.2f}")
    print(f"  Average RMSE: {np.mean([r['rmse'] for r in valid_results]):.2f}")
    
    valid_mape = [r['mape'] for r in valid_results if r['mape'] is not None]
    if valid_mape:
        print(f"  Average MAPE: {np.mean(valid_mape):.2f}%")
        print(f"  Median MAPE: {np.median(valid_mape):.2f}%")
    
    excellent = sum(1 for r in valid_results if r.get('assessment') == 'Excellent')
    good = sum(1 for r in valid_results if r.get('assessment') == 'Good')
    acceptable = sum(1 for r in valid_results if r.get('assessment') == 'Acceptable')
    needs_improvement = sum(1 for r in valid_results if r.get('assessment') == 'Needs Improvement')
    
    print(f"\n  Excellent (MAPE < 5%): {excellent}")
    print(f"  Good (MAPE < 10%): {good}")
    print(f"  Acceptable (MAPE < 20%): {acceptable}")
    print(f"  Needs Improvement (MAPE >= 20%): {needs_improvement}")

# =============================================================================
# SECTION 5: MODEL PERFORMANCE COMPARISON
# =============================================================================

print("\n\n" + "="*80)
print("SECTION 5: MODEL PERFORMANCE COMPARISON")
print("-"*80)

if valid_results:
    # Best performing
    best_by_mape = sorted([r for r in valid_results if r.get('mape') is not None], 
                          key=lambda x: x['mape'])[:5]
    
    print("\nBEST PERFORMING COURSES (by MAPE):")
    for i, result in enumerate(best_by_mape, 1):
        print(f"  {i}. {result['course']:<50} MAPE: {result['mape']:.2f}%")
    
    # Worst performing
    worst_by_mape = sorted([r for r in valid_results if r.get('mape') is not None], 
                           key=lambda x: x['mape'], reverse=True)[:5]
    
    print("\nWORST PERFORMING COURSES (by MAPE):")
    for i, result in enumerate(worst_by_mape, 1):
        print(f"  {i}. {result['course']:<50} MAPE: {result['mape']:.2f}%")
    
    # High error courses
    high_error = [r for r in valid_results if r.get('mape') is not None and r['mape'] > 30]
    if high_error:
        print(f"\nCOURSES WITH HIGH FORECAST ERROR (MAPE > 30%):")
        for result in high_error:
            print(f"  - {result['course']:<50} MAPE: {result['mape']:.2f}%")
            print(f"    Average actual: {result.get('actuals_mean', 0):.2f} applicants/week")
    
    # Low volume courses
    low_volume = [r for r in valid_results if r.get('actuals_mean', 0) < 5]
    if low_volume:
        print(f"\nLOW VOLUME COURSES (< 5 applicants/week avg):")
        for result in low_volume:
            print(f"  - {result['course']:<50} Avg: {result.get('actuals_mean', 0):.2f}/week")

print("\nCompleted. Results saved in memory.")
print("\nNote: Lower MAE/RMSE/MAPE indicates better forecast accuracy.")
print("MAPE < 10% is generally considered good for demand forecasting.")
