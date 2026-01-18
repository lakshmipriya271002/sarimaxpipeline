# Time Series Forecasting Pipeline - AI Core Deployment

## Overview
This is a production-ready time series forecasting pipeline using SARIMAX with a three-pipeline architecture:
1. **Initial Training**: Train on 18 months of historical data
2. **Daily Inference**: Predict one day at a time with expanding window
3. **Monthly Retraining**: Retrain model after each month with updated data

## Files
- `main.py`: Main application with forecasting pipeline and Flask API
- `requirements.txt`: Python dependencies
- `README.md`: This file

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### 1. Training Mode (Batch Processing)
Run the complete training pipeline:

```bash
python main.py train City_Gas_CNG_Combined.csv
```

This will:
- Load and prepare the data
- Train the initial SARIMAX model
- Perform daily forecasting with expanding window
- Retrain monthly
- Save all predictions to CSV files
- Save trained models

### 2. API Mode (REST API Service)
Start the Flask API server:

```bash
python main.py
```

The API will be available at `http://localhost:5000`

#### API Endpoints

**Health Check**
```bash
GET /health
```

**Train Model**
```bash
POST /train
Content-Type: application/json

{
  "data_file": "City_Gas_CNG_Combined.csv",
  "start_date": "2023-04-01",
  "end_date": "2025-03-31"
}
```

**Get Predictions**
```bash
POST /predict
Content-Type: application/json

{
  "model_file": "sarimax_initial_18months.pkl",
  "steps": 1,
  "exog_data": [[value1, value2, ...]]  // optional
}
```

**List Models**
```bash
GET /models
```

## Configuration

Edit the `CONFIG` dictionary in `main.py`:

```python
CONFIG = {
    'TRAIN_WINDOW_MONTHS': 18,      # Initial training window
    'FORECAST_HORIZON_DAYS': 1,     # Forecast horizon
    'SARIMAX_ORDER': (1, 1, 1),     # ARIMA order
    'SEASONAL_ORDER': (1, 1, 1, 7), # Seasonal order
    'OUTPUT_DIR': './outputs/',     # Output directory
    'MODEL_DIR': './models/',       # Model directory
    'RANDOM_STATE': 42
}
```

## Output Files

The pipeline generates:
- `predictions_daily.csv`: Daily predictions
- `predictions_weekly.csv`: Weekly aggregated predictions
- `predictions_biweekly.csv`: Bi-weekly aggregated predictions
- `predictions_monthly.csv`: Monthly aggregated predictions
- Trained models in `./models/` directory

## AI Core Deployment

### 1. Create Docker Image

Create a `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 5000

CMD ["python", "main.py"]
```

### 2. Build and Push

```bash
docker build -t time-series-forecasting:latest .
docker tag time-series-forecasting:latest <your-registry>/time-series-forecasting:latest
docker push <your-registry>/time-series-forecasting:latest
```

### 3. Deploy to AI Core

Create a deployment descriptor and deploy using AI Core SDK or UI.

## Environment Variables

- `PORT`: API server port (default: 5000)

## Data Requirements

Input CSV should contain:
- `BILL DATE`: Date column
- `QTY(1000 SM3)`: Quantity column
- Optional exogenous variables: gcv_cal_value, gst_rcovery_rate, etc.

## Model Artifacts

All trained models are saved in `./models/`:
- `sarimax_initial_18months.pkl`: Initial model
- `sarimax_month_N_Mmonths.pkl`: Retrained models

## Metrics

The pipeline calculates:
- **MAE**: Mean Absolute Error
- **RMSE**: Root Mean Squared Error
- **MAPE**: Mean Absolute Percentage Error

## Support

For issues or questions, contact the development team.
