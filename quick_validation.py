"""Quick model validation - samples 5 courses for faster execution"""
import sys
import json
from pathlib import Path
import warnings
sys.path.insert(0, 'services')

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.iolib.smpickle import load_pickle

from forecasting_repository import get_forecasting_repository
from forecasting_evaluation import walk_forward_backtest, classify_mape

warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_REGISTRY_FILE = PROJECT_ROOT / "trained_models" / "forecasting" / "metadata" / "model_registry.json"

print("QUICK FORECAST MODEL VALIDATION")
print("="*80)

# Load registry
with open(MODEL_REGISTRY_FILE) as f:
    registry = json.load(f)

print(f"\nTotal models: {len(registry['models'])}")
print(f"ARIMA order (all): {registry['arima_order']}")
print(f"Training range: {list(registry['models'].values())[0]['data_start_date']} to "
      f"{list(registry['models'].values())[0]['data_end_date']}")

# Sample 5 diverse courses
sample_courses = [
    "Cookery NC II",  # High volume
    "Driving NC II",  # High volume
    "HEO (Bulldozer) NC II",  # Low volume
    "Trainers Methodology Level I",  # Low volume
    "Computer Systems Servicing NC II"  # Medium volume
]

repository = get_forecasting_repository()

print("\n\nBACKTESTING SAMPLE COURSES:")
print("-"*80)

results = []
for course in sample_courses:
    print(f"\n{course}:")
    try:
        series = repository.get_course_series(course)
        print(f"  Total weeks: {len(series)}")
        print(f"  Avg applicants/week: {series.mean():.2f}")
        
        # Backtest
        result = walk_forward_backtest(series, train_ratio=0.8)
        print(f"  MAE: {result.mae:.2f}")
        print(f"  RMSE: {result.rmse:.2f}")
        print(f"  MAPE: {result.mape:.2f}%" if result.mape else "  MAPE: N/A")
        print(f"  Assessment: {classify_mape(result.mape)}")
        
        results.append({
            'course': course,
            'mae': result.mae,
            'rmse': result.rmse,
            'mape': result.mape,
            'avg_weekly': series.mean()
        })
    except Exception as e:
        print(f"  ERROR: {e}")

#Check forecast behavior
print("\n\nFORCAST BEHAVIOR CHECK (Jan-Mar 2026):")
print("-"*80)

from forecasting_service import get_forecasting_service
service = get_forecasting_service()

for course in sample_courses[:3]:
    try:
        detail = service.get_course_detail(course)
        forecast_vol = detail['forecast_volume']
        print(f"\n{course}:")
        for point in forecast_vol:
            print(f"  {point['period']}: {point['applicants']} applicants")
    except Exception as e:
        print(f"\n{course}: ERROR - {e}")

# Simple baseline comparison
print("\n\nBASELINE COMPARISON (Naive Forecast):")
print("-"*80)

for item in results:
    if item.get('mae'):
        series = repository.get_course_series(item['course'])
        
        # Split same way
        split = int(len(series) * 0.8)
        test_actuals = series.iloc[split:].values
        # Naive: next = previous
        naive_preds = series.iloc[split-1:-1].values
        
        # Calculate naive MAE
        naive_mae = np.mean(np.abs(test_actuals - naive_preds))
        
        arima_mae = item['mae']
        improvement = ((naive_mae - arima_mae) / naive_mae * 100) if naive_mae > 0 else 0
        
        comparison = "ARIMA better" if arima_mae < naive_mae else "Baseline better"
        
        print(f"\n{item['course']}:")
        print(f"  ARIMA MAE: {arima_mae:.2f}")
        print(f"  Naive MAE: {naive_mae:.2f}")
        print(f"  Improvement: {improvement:.1f}%")
        print(f"  Result: {comparison}")

print("\n\nDone!")
