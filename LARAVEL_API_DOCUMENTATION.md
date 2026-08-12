# Laravel Frontend API Documentation

## Backend Data Sources for Laravel Dashboard

Your Laravel frontend developer needs **TWO data sources**:

1. ✅ **Application Trend** - Provided by Forecasting API
2. ✅ **Barangay Recommendation** - Already completed (separate system)

---

## 📊 APPLICATION TREND ENDPOINT

### Recommended Endpoint: `GET /forecast/charts`

This endpoint provides all the data needed for the Application Trend dashboard chart, including:
- ✅ Historical application trend (monthly aggregated view)
- ✅ Weekly application trend (weekly granularity)
- ✅ Forecast curve (future predictions)
- ✅ Summary statistics
- ✅ Top courses
- ✅ Demographic distributions

**Architecture:**
- Source data: Daily observations (5 years, 2021-2025)
- Aggregation: Daily → Weekly → ARIMA(1,1,1)
- Forecast horizons: next_week, next_month (4 weeks), next_quarter (13 weeks)
- Single source of truth: `ForecastingService`

---

## API Specification

### Endpoint Details

**URL:** `GET /forecast/charts`

**HTTP Method:** `GET`

**Query Parameters:**
- `course` (optional): Filter by specific course name
  - Omit for TLDC-wide (all courses aggregated)
  - Example: `?course=Cookery%20NC%20II`

**Authentication:** None (currently open)

**Response Format:** JSON

**Status Codes:**
- `200 OK` - Success
- `400 Bad Request` - Invalid course name
- `500 Internal Server Error` - Server error

---

## Response Structure

### Full Response Schema

```json
{
  "applicant_trend_over_time": [
    {
      "period": "Jul 2024",
      "applicants": 2128.0
    }
  ],
  "weekly_applicant_trend": [
    {
      "period": "2025-07-13",
      "applicants": 483.0
    }
  ],
  "forecast_curve": [
    {
      "period": "Jan 2026",
      "applicants": 1761.5
    }
  ],
  "top_courses": [
    {
      "course": "Cookery NC II",
      "forecasted_applicant_count": 176.2,
      "trend": "Stable"
    }
  ],
  "summary_points": [
    {
      "label": "Next Week",
      "applicants": 431.7
    }
  ],
  "employment_distribution": [...],
  "education_distribution": [...],
  "course_distribution": [...],
  "sex_distribution": [...],
  "age_distribution": [...],
  "learner_classification_distribution": [...],
  "barangay_distribution": [...]
}
```

---

## Field Descriptions

### 1. `applicant_trend_over_time` ⭐ PRIMARY FOR CHART

**Purpose:** Historical application trend with monthly labels

**Type:** Array of objects

**Structure:**
```json
[
  {
    "period": "Jul 2024",      // Month label (human-readable)
    "applicants": 2128.0       // Total applicants for that month
  }
]
```

**Details:**
- Contains the last 18 months of historical data
- Aggregated from weekly data to monthly view for easier visualization
- Labels are formatted as "Mon YYYY" (e.g., "Jul 2024", "Dec 2025")
- Applicant counts are floats (aggregated from weekly totals)

**Chart Usage:**
- **X-axis:** `period` (month labels)
- **Y-axis:** `applicants` (count)
- **Line type:** Historical (solid line, blue)

---

### 2. `weekly_applicant_trend`

**Purpose:** Weekly granularity historical data

**Type:** Array of objects

**Structure:**
```json
[
  {
    "period": "2025-07-13",    // ISO date (Sunday of that week)
    "applicants": 483.0        // Total applicants for that week
  }
]
```

**Details:**
- Contains the last ~26 weeks (approximately 6 months)
- Each entry represents one week's total
- Dates are ISO format (YYYY-MM-DD)
- More granular than `applicant_trend_over_time`

**Chart Usage:**
- Optional: Use for detailed weekly drill-down
- X-axis: `period` (weekly dates)
- Y-axis: `applicants` (count)

---

### 3. `forecast_curve` ⭐ PRIMARY FOR FORECAST

**Purpose:** Future predictions from ARIMA model

**Type:** Array of objects

**Structure:**
```json
[
  {
    "period": "Jan 2026",      // Future month label
    "applicants": 1761.5       // Predicted applicants
  }
]
```

**Details:**
- Contains 3 months of future predictions
- Labels match `applicant_trend_over_time` format ("Mon YYYY")
- Values are ARIMA(1,1,1) weekly forecasts aggregated to monthly view
- Predictions are based on weekly aggregated data

**Chart Usage:**
- **X-axis:** `period` (future month labels)
- **Y-axis:** `applicants` (predicted count)
- **Line type:** Forecast (dashed line, orange/red)
- **Combine with:** `applicant_trend_over_time` for continuous chart

---

### 4. `top_courses`

**Purpose:** Top 10 courses by forecasted volume

**Type:** Array of objects (max 10 items)

**Structure:**
```json
[
  {
    "course": "Cookery NC II",
    "forecasted_applicant_count": 176.2,
    "trend": "Stable"           // "Increasing" | "Stable" | "Decreasing"
  }
]
```

**Details:**
- Sorted by `forecasted_applicant_count` (descending)
- Trend is calculated from growth percentage vs recent average
- Useful for ranking and highlighting high-demand courses

---

### 5. `summary_points`

**Purpose:** Key forecast metrics for dashboard cards

**Type:** Array of objects (3 items)

**Structure:**
```json
[
  {
    "label": "Next Week",
    "applicants": 431.7
  },
  {
    "label": "Next Month (~4 weeks)",
    "applicants": 1761.5
  },
  {
    "label": "Next Quarter (~13 weeks)",
    "applicants": 5761.1
  }
]
```

**Details:**
- Next Week: ARIMA step 1 (genuine 1-week forecast)
- Next Month: Sum of ARIMA steps 1-4 (≈ 4 weeks)
- Next Quarter: Sum of ARIMA steps 1-13 (≈ 13 weeks)

**Dashboard Usage:**
- Display as metric cards at the top of the dashboard
- Show predicted applicant volumes for planning

---

### 6. Distribution Fields (Optional)

These provide demographic breakdowns for additional insights:

- **`employment_distribution`** - Employment status breakdown
- **`education_distribution`** - Educational attainment levels
- **`course_distribution`** - All 21 courses with historical counts
- **`sex_distribution`** - Male/Female breakdown
- **`age_distribution`** - Age group breakdown
- **`learner_classification_distribution`** - New Entrant, Career Shifter, etc.
- **`barangay_distribution`** - Top 10 barangays by participation

**Common Structure:**
```json
[
  {
    "label": "Category Name",
    "count": 2447,
    "percentage": 30.6
  }
]
```

---

## Example Usage

### Example 1: TLDC-Wide Application Trend (All Courses)

**Request:**
```bash
GET http://your-api-domain.com/forecast/charts
```

**cURL:**
```bash
curl -X GET "http://your-api-domain.com/forecast/charts"
```

**JavaScript (Fetch API):**
```javascript
fetch('http://your-api-domain.com/forecast/charts')
  .then(response => response.json())
  .then(data => {
    // Historical data
    const historical = data.applicant_trend_over_time;
    
    // Forecast data
    const forecast = data.forecast_curve;
    
    // Combine for continuous chart
    const chartData = [...historical, ...forecast];
    
    // Summary metrics
    const nextWeek = data.summary_points[0].applicants;
    const nextMonth = data.summary_points[1].applicants;
    const nextQuarter = data.summary_points[2].applicants;
    
    console.log(`Expected applicants next month: ${nextMonth}`);
  });
```

**Laravel (Guzzle):**
```php
use GuzzleHttp\Client;

$client = new Client();
$response = $client->get('http://your-api-domain.com/forecast/charts');
$data = json_decode($response->getBody(), true);

// Historical trend
$historical = $data['applicant_trend_over_time'];

// Forecast
$forecast = $data['forecast_curve'];

// Summary
$nextMonth = $data['summary_points'][1]['applicants'];
```

---

### Example 2: Course-Specific Application Trend

**Request:**
```bash
GET http://your-api-domain.com/forecast/charts?course=Cookery%20NC%20II
```

**cURL:**
```bash
curl -X GET "http://your-api-domain.com/forecast/charts?course=Cookery%20NC%20II"
```

**JavaScript:**
```javascript
const course = encodeURIComponent('Cookery NC II');
fetch(`http://your-api-domain.com/forecast/charts?course=${course}`)
  .then(response => response.json())
  .then(data => {
    // Course-specific historical and forecast data
    console.log('Historical:', data.applicant_trend_over_time);
    console.log('Forecast:', data.forecast_curve);
  });
```

---

## Sample Response (Actual Data)

### Actual Response from `GET /forecast/charts`

```json
{
  "applicant_trend_over_time": [
    { "period": "Jul 2024", "applicants": 2128.0 },
    { "period": "Aug 2024", "applicants": 2177.0 },
    { "period": "Sep 2024", "applicants": 1888.0 },
    { "period": "Oct 2024", "applicants": 1872.0 },
    { "period": "Nov 2024", "applicants": 1744.0 },
    { "period": "Dec 2024", "applicants": 2128.0 },
    { "period": "Jan 2025", "applicants": 2325.0 },
    { "period": "Feb 2025", "applicants": 1958.0 },
    { "period": "Mar 2025", "applicants": 1969.0 },
    { "period": "Apr 2025", "applicants": 1817.0 },
    { "period": "May 2025", "applicants": 1862.0 },
    { "period": "Jun 2025", "applicants": 1898.0 },
    { "period": "Jul 2025", "applicants": 2190.0 },
    { "period": "Aug 2025", "applicants": 2274.0 },
    { "period": "Sep 2025", "applicants": 1979.0 },
    { "period": "Oct 2025", "applicants": 1968.0 },
    { "period": "Nov 2025", "applicants": 1849.0 },
    { "period": "Dec 2025", "applicants": 2113.0 }
  ],
  
  "forecast_curve": [
    { "period": "Jan 2026", "applicants": 1761.5 },
    { "period": "Feb 2026", "applicants": 1777.6 },
    { "period": "Mar 2026", "applicants": 1777.6 }
  ],
  
  "summary_points": [
    { "label": "Next Week", "applicants": 431.7 },
    { "label": "Next Month (~4 weeks)", "applicants": 1761.5 },
    { "label": "Next Quarter (~13 weeks)", "applicants": 5761.1 }
  ],
  
  "top_courses": [
    {
      "course": "Cookery NC II",
      "forecasted_applicant_count": 176.2,
      "trend": "Stable"
    },
    {
      "course": "Driving NC II",
      "forecasted_applicant_count": 169.6,
      "trend": "Stable"
    },
    {
      "course": "Computer Systems Servicing NC II",
      "forecasted_applicant_count": 169.2,
      "trend": "Increasing"
    }
  ]
}
```

---

## Chart Implementation Guide

### Recommended Chart Type: Line Chart with Forecast

**Chart Libraries:**
- Chart.js (recommended for simplicity)
- ApexCharts (more features)
- Highcharts (enterprise)

### Basic Chart Configuration

**Data Structure:**
```javascript
// Combine historical and forecast
const labels = [
  ...data.applicant_trend_over_time.map(d => d.period),
  ...data.forecast_curve.map(d => d.period)
];

const historicalValues = data.applicant_trend_over_time.map(d => d.applicants);
const forecastValues = new Array(historicalValues.length).fill(null)
  .concat(data.forecast_curve.map(d => d.applicants));

// Chart.js configuration
const chartConfig = {
  type: 'line',
  data: {
    labels: labels,
    datasets: [
      {
        label: 'Historical Applications',
        data: historicalValues,
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        borderWidth: 2,
        tension: 0.4
      },
      {
        label: 'Forecast',
        data: forecastValues,
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)',
        borderWidth: 2,
        borderDash: [5, 5],  // Dashed line for forecast
        tension: 0.4
      }
    ]
  },
  options: {
    responsive: true,
    plugins: {
      title: {
        display: true,
        text: 'TLDC Application Trend & Forecast'
      },
      legend: {
        display: true,
        position: 'top'
      }
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Number of Applicants'
        }
      },
      x: {
        title: {
          display: true,
          text: 'Period'
        }
      }
    }
  }
};
```

---

## Alternative Endpoint: `/forecast/dashboard`

If you need **more comprehensive data** including insights and full course details:

**URL:** `GET /forecast/dashboard?period=next_month`

**Query Parameters:**
- `period` (required): `next_week`, `next_month`, or `next_quarter`
- `course` (optional): Filter by specific course

**Response Includes:**
- All the data from `/forecast/charts`
- Plus: Summary metrics, course forecasts, insights

**Example:**
```bash
GET http://your-api-domain.com/forecast/dashboard?period=next_month
```

**Note:** This endpoint returns the same chart data in the `charts` object:
```json
{
  "period": "next_month",
  "course_filter": null,
  "summary": {...},
  "courses": [...],
  "charts": {
    "applicant_trend_over_time": [...],
    "forecast_curve": [...],
    ...
  },
  "insights": [...]
}
```

---

## Data Architecture

### Data Flow (Read-Only for Laravel)

```
datasets/applicant_volume.csv (38,346 daily records)
           ↓
ForecastingRepository (aggregates daily → weekly)
           ↓
ForecastingService (fits ARIMA(1,1,1) on weekly data)
           ↓
Pre-computed forecasts (52 weekly steps cached at startup)
           ↓
API endpoint /forecast/charts (serves aggregated monthly view)
           ↓
Laravel Frontend (renders chart)
```

### Dataset Details

- **Source:** `datasets/applicant_volume.csv`
- **Records:** 38,346 daily observations
- **Date Range:** 2021-01-01 to 2025-12-31 (5 years)
- **Courses:** 21 courses
- **Max Daily Applicants:** 10 per course per day
- **Data Type:** Synthetic (for capstone development)

### Model Details

- **Model:** ARIMA(1,1,1)
- **Frequency:** Weekly (aggregated from daily)
- **Training:** One model per course (21 total)
- **Forecast Horizon:** 52 weeks (pre-computed at startup)
- **Validation:** Chronological walk-forward (no data leakage)

---

## Testing & Verification

### API Status

✅ **Endpoint Tested:** `GET /forecast/charts`  
✅ **HTTP Status:** 200 OK  
✅ **Response Format:** Valid JSON  
✅ **Data Validation:** All 15 forecasting tests passing

### Test Results

```bash
============================= 15 passed in 35.21s ==============================
```

**Tests Validated:**
- ✅ Weekly ARIMA forecasts
- ✅ Growth calculations (time-scale correct)
- ✅ Trend classifications
- ✅ Chronological validation (no data leakage)
- ✅ MAPE, MAE, RMSE metrics
- ✅ JSON serialization (no pandas/numpy objects)

---

## Important Notes

### ✅ Production Ready

1. **Single Source of Truth:** `ForecastingService` is the only forecasting pipeline
2. **No Duplicate Systems:** Legacy forecasting code is not loaded at runtime
3. **Clean JSON:** No pandas objects, numpy scalars, or datetime objects in response
4. **Stable API:** Response structure is finalized and tested
5. **Complete Coverage:** All 21 courses included in aggregated view

### ⚠️ Important Constraints

1. **Synthetic Data:** Dataset is synthetically generated for capstone development
2. **Not Real TLDC Records:** Clearly documented throughout the system
3. **Weekly Aggregation:** Source is daily, but ARIMA operates on weekly aggregates
4. **Caching:** Forecasts are pre-computed at server startup (fast response times)

### 🔒 Recommendation System

**Status:** ✅ Complete and untouched

**Endpoint:** (Provided separately by completion/recommendation module)

**Important:** The forecasting API and recommendation API are **independent systems**. Do not mix their data or endpoints.

---

## Summary for Laravel Developer

### What You Need

**For Application Trend Dashboard:**
- ✅ **Endpoint:** `GET /forecast/charts`
- ✅ **Historical Data:** `applicant_trend_over_time` (18 months)
- ✅ **Forecast Data:** `forecast_curve` (3 months ahead)
- ✅ **Summary Metrics:** `summary_points` (next week/month/quarter)
- ✅ **Optional Filter:** `?course=Course%20Name`

### Quick Start

1. **Fetch data:**
   ```
   GET http://your-api-domain.com/forecast/charts
   ```

2. **Parse JSON:**
   ```javascript
   const historical = data.applicant_trend_over_time;
   const forecast = data.forecast_curve;
   ```

3. **Render chart:**
   - X-axis: `period` (month labels)
   - Y-axis: `applicants` (counts)
   - Historical: solid line
   - Forecast: dashed line

4. **Display metrics:**
   ```javascript
   const nextWeek = data.summary_points[0].applicants;
   const nextMonth = data.summary_points[1].applicants;
   const nextQuarter = data.summary_points[2].applicants;
   ```

### Support

**Backend Status:** ✅ Production-ready  
**Tests:** ✅ 15/15 passing  
**Documentation:** ✅ Complete  
**API:** ✅ Stable and tested

---

**Document Version:** 1.0  
**Last Updated:** 2026-08-12  
**Status:** Production Ready ✅
