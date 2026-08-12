# LGU-TLDC Predictive Analytics API

Predictive analytics backend for the LGU-TLDC scholarship and training
management system.

## Features

- Applicant volume forecasting
- Weekly ARIMA forecasting
- Course-level forecasting
- Forecast growth analysis
- Application trend data
- Laravel-compatible JSON API
- Forecast evaluation and validation

## Technology

- Python
- FastAPI
- ARIMA
- Pandas
- NumPy
- Statsmodels
- Pytest

## Project Structure

```text
datasets/       Dataset files
routes/         API routes
services/       Business and forecasting logic
tests/          Automated tests
trained_models/ Trained ML models
training/       Dataset/model training utilities
docs/           Project documentation
main.py         FastAPI application entry point
vercel.json     Vercel deployment configuration