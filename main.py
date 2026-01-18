"""
Time Series Forecasting Pipeline for AI Core Deployment
Three-Pipeline Architecture: Training → Inference → Retraining
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')
import pickle
import os
import json

# SARIMAX and time series libraries
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error

# Flask for API endpoint
from flask import Flask, request, jsonify


# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    'TRAIN_WINDOW_MONTHS': 18,
    'FORECAST_HORIZON_DAYS': 1,
    'SARIMAX_ORDER': (1, 1, 1),
    'SEASONAL_ORDER': (1, 1, 1, 7),
    'OUTPUT_DIR': './outputs/',
    'MODEL_DIR': './models/',
    'RANDOM_STATE': 42
}

# Create directories
os.makedirs(CONFIG['OUTPUT_DIR'], exist_ok=True)
os.makedirs(CONFIG['MODEL_DIR'], exist_ok=True)


# ============================================================================
# DATA PREPARATION FUNCTIONS
# ============================================================================

def load_and_prepare_data(file_path):
    """
    Load and prepare data with proper data cleaning
    """
    # Load the CSV data file
    df = pd.read_csv(file_path, low_memory=False)
    
    # Standardize column names
    df.columns = df.columns.str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '').str.replace('-', '_')
    
    # Drop columns with >= 60% null values
    null_threshold = 0.6
    null_ratio = df.isnull().mean()
    high_null_columns = null_ratio[null_ratio > null_threshold].index.tolist()
    high_null_columns = [col for col in high_null_columns if col != 'index_2_percentage']
    if high_null_columns:
        df = df.drop(columns=high_null_columns)
    
    # Drop columns with >= 70% zeros
    zero_threshold = 0.7
    zero_ratio = ((df == '0') | (df == '0.0') | (df == '0.00') | (df == 0)).mean()
    high_zero_columns = zero_ratio[zero_ratio >= zero_threshold].index.tolist()
    if high_zero_columns:
        df = df.drop(columns=high_zero_columns)
    
    # Combine tax related columns
    if 'gst_rcovery_amount' in df.columns and 'vat_tax' in df.columns:
        tax_cols = ["gst_rcovery_amount", "vat_tax"]
        df[tax_cols] = df[tax_cols].replace(",", "", regex=True)
        df[tax_cols] = df[tax_cols].apply(pd.to_numeric, errors='coerce')
        df["total_tax_combined"] = df[tax_cols].sum(axis=1)
        df = df.drop(columns=tax_cols)
    
    # Remove ID-based and duplicate columns
    cols_to_remove = []
    for col_list in [["contract_no", "invoice_no"], 
                     ["material_number", "customer", "year_month", "month"],
                     ["quantitymbg", "quantitymbn", "quantitymcg", "quantitymcn"]]:
        cols_to_remove.extend([c for c in col_list if c in df.columns])
    if cols_to_remove:
        df = df.drop(columns=cols_to_remove)
    
    # Remove rows with null industries and customers
    if 'customer_name' in df.columns and 'industory_sector' in df.columns:
        df = df.dropna(subset=['customer_name', 'industory_sector'])
    
    # Handle missing values
    if 'order_reason' in df.columns:
        df["order_reason"] = df["order_reason"].fillna("Unknown Reason")
    if 'drc' in df.columns:
        df["drc"] = df["drc"].fillna("No DRC")
    if 'mvgr1' in df.columns:
        df["mvgr1"] = df["mvgr1"].fillna("Uncategorized")
    if 'index_2' in df.columns:
        df["index_2"] = df["index_2"].replace(["None", "-", "", " "], pd.NA)
        df["index_2"] = df["index_2"].fillna("Not Indexed")
    if 'index_2_percentage' in df.columns:
        df["index_2_percentage"] = df["index_2_percentage"].fillna("0%")
    
    # Convert numeric columns
    numeric_cols = ["taxable_sales", "basic_price", "zutf_amount", "ztu1_amount", "gcv_cal_value", 
                    "zutf_rate", "ztf_total", "total_basic", "ztf1_amount", "ztu1_rate", "ztf1_rate", 
                    "qty1000_sm3", "ncv_cal_value", "marketing_margn_rate", "marketing_margn"]
    numeric_cols = [col for col in numeric_cols if col in df.columns]
    if numeric_cols:
        df[numeric_cols] = df[numeric_cols].replace(",", "", regex=True)
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
    
    # Convert dates
    if 'bill_date' in df.columns:
        df["bill_date"] = pd.to_datetime(df["bill_date"], errors='coerce')
    if 'invoice_generation_d' in df.columns:
        df["invoice_generation_d"] = pd.to_datetime(df["invoice_generation_d"], errors='coerce')
    
    # Convert index percentages
    if 'index_1_percentage' in df.columns:
        df["index_1_percentage"] = df["index_1_percentage"].str.rstrip('%').astype(float) / 100
    if 'index_2_percentage' in df.columns:
        df["index_2_percentage"] = df["index_2_percentage"].str.rstrip('%').astype(float) / 100
    
    # Temporal features
    if 'bill_date' in df.columns:
        df["bill_quarter"] = df["bill_date"].dt.quarter
        df["bill_year"] = df["bill_date"].dt.year
        df["bill_day"] = df["bill_date"].dt.day
        df["bill_dayofweek"] = df["bill_date"].dt.dayofweek
        df["is_weekend"] = df["bill_dayofweek"].isin([5, 6]).astype(int)
        df["month_num"] = df["bill_date"].dt.month
    
    # Energy quality ratio
    if 'gcv_cal_value' in df.columns and 'ncv_cal_value' in df.columns:
        df["gcv_to_ncv_ratio"] = df["gcv_cal_value"] / (df["ncv_cal_value"] + 1e-5)
    
    # Remove data leakage columns
    leakage_cols = ['inv_tot', 'zutf_amount', 'ztf_total', 'total_basic', 'basic_price',
                    'ztf1_amount', 'ztu1_amount', 'marketing_margn', 'taxable_sales',
                    "foreign_compzpr1", "foreign_compzpr3", 'total_tax_combined', 'invoice_generation_d']
    leakage_cols = [col for col in leakage_cols if col in df.columns]
    if leakage_cols:
        df = df.drop(columns=leakage_cols)
    
    # Filter for City Gas-CNG
    if 'industory_sector' in df.columns:
        df_cng = df[df['industory_sector'] == 'City Gas-CNG'].copy()
    else:
        df_cng = df.copy()
    
    # Select exogenous variables
    exog_var_names = ['gcv_cal_value', 'gst_rcovery_rate', 'zutf_rate', 'ztu1_rate', 
                       'ztf1_rate', 'exch_rate', 'ncv_cal_value', 'marketing_margn_rate', 
                       'vat_rate', 'gcv_to_ncv_ratio']
    
    available_exog = [col for col in exog_var_names if col in df_cng.columns]
    
    if len(available_exog) > 0:
        required_cols = ['bill_date', 'qty1000_sm3'] + available_exog
        df_cng = df_cng[required_cols].copy()
        
        # Aggregate to DAILY level
        agg_dict = {'qty1000_sm3': 'sum'}
        for var in available_exog:
            agg_dict[var] = 'mean'
        
        df_daily = df_cng.groupby('bill_date').agg(agg_dict).reset_index()
        
        # Create lagged features
        lag_days = [1, 7, 14, 30]
        for var in available_exog:
            for lag in lag_days:
                df_daily[f"{var}_lag_{lag}"] = df_daily[var].shift(lag)
        
        df_daily = df_daily.drop(columns=available_exog)
    else:
        df_daily = df_cng.groupby('bill_date').agg({'qty1000_sm3': 'sum'}).reset_index()
    
    # Rename columns
    df_daily = df_daily.rename(columns={'qty1000_sm3': 'quantity'}, errors='ignore')
    if 'bill_date' in df_daily.columns:
        df_daily = df_daily.rename(columns={'bill_date': 'date'})
    
    # Drop rows with NaN from lagging
    df_daily = df_daily.dropna()
    df_daily = df_daily.sort_values('date').reset_index(drop=True)
    
    return df_daily


# ============================================================================
# MODELING FUNCTIONS
# ============================================================================

def train_sarimax_model(train_data, exog_data=None, order=(1,1,1), seasonal_order=(1,1,1,7)):
    """
    Train SARIMAX model on given data with optional exogenous variables
    """
    try:
        model = SARIMAX(train_data, exog=exog_data, order=order, seasonal_order=seasonal_order, 
                        enforce_stationarity=False, enforce_invertibility=False)
        fitted_model = model.fit(disp=False, maxiter=200)
        return fitted_model
    except Exception as e:
        print(f"Error training SARIMAX: {e}")
        return None


def forecast_with_sarimax(model, steps=1, exog_forecast=None):
    """
    Forecast next day(s) using fitted SARIMAX model
    """
    try:
        forecast = model.forecast(steps=steps, exog=exog_forecast)
        if isinstance(forecast, np.ndarray):
            return forecast[0] if steps == 1 else forecast
        else:
            return forecast.values[0] if steps == 1 else forecast.values
    except Exception as e:
        print(f"Error forecasting: {e}")
        return None


# ============================================================================
# FORECASTING PIPELINE
# ============================================================================

def run_forecasting_pipeline(df_daily, start_date='2023-04-01', end_date='2025-03-31'):
    """
    Run the three-pipeline architecture: Training → Inference → Retraining
    """
    # Filter date range
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    df_daily = df_daily[(df_daily['date'] >= start_date) & (df_daily['date'] <= end_date)].copy()
    
    # Check if we have exogenous features
    exog_features = [col for col in df_daily.columns if col not in ['date', 'quantity']]
    has_exog = len(exog_features) > 0
    
    print(f"Exogenous features: {len(exog_features)}")
    
    # Storage for all predictions
    all_predictions = []
    
    # ========================================================================
    # PIPELINE 1: INITIAL TRAINING
    # ========================================================================
    
    print("\n" + "="*80)
    print("PIPELINE 1: INITIAL TRAINING")
    print("="*80)
    
    initial_train_start = start_date
    initial_train_end = start_date + pd.DateOffset(months=CONFIG['TRAIN_WINDOW_MONTHS']) - pd.Timedelta(days=1)
    
    train_mask = (df_daily['date'] >= initial_train_start) & (df_daily['date'] <= initial_train_end)
    train_df = df_daily[train_mask].copy()
    train_y = train_df['quantity'].values
    train_exog = train_df[exog_features].values if has_exog else None
    
    print(f"Training initial model on {len(train_y)} days...")
    current_model = train_sarimax_model(train_y, exog_data=train_exog, 
                                        order=CONFIG['SARIMAX_ORDER'], 
                                        seasonal_order=CONFIG['SEASONAL_ORDER'])
    
    if current_model is None:
        raise Exception("Initial training failed")
    
    # Save initial model
    initial_model_path = os.path.join(CONFIG['MODEL_DIR'], f'sarimax_initial_{CONFIG["TRAIN_WINDOW_MONTHS"]}months.pkl')
    with open(initial_model_path, 'wb') as f:
        pickle.dump(current_model, f)
    print(f"Initial model saved: {initial_model_path}")
    
    current_train_start = initial_train_start
    current_train_end = initial_train_end
    current_train_months = CONFIG['TRAIN_WINDOW_MONTHS']
    
    # ========================================================================
    # PIPELINE 2 & 3: DAILY INFERENCE + MONTHLY RETRAINING
    # ========================================================================
    
    print("\n" + "="*80)
    print("PIPELINE 2 & 3: DAILY INFERENCE + MONTHLY RETRAINING LOOP")
    print("="*80)
    
    forecast_start_date = initial_train_end + pd.Timedelta(days=1)
    total_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1
    forecast_month_count = total_months - CONFIG['TRAIN_WINDOW_MONTHS']
    
    for month_idx in range(forecast_month_count):
        
        # PIPELINE 2: DAILY INFERENCE
        print(f"\n{'='*80}")
        print(f"MONTH {month_idx + 1}/{forecast_month_count}: DAILY INFERENCE")
        print(f"{'='*80}")
        
        forecast_month_start = forecast_start_date + pd.DateOffset(months=month_idx)
        forecast_month_end = forecast_month_start + pd.DateOffset(months=1) - pd.Timedelta(days=1)
        
        if forecast_month_end > end_date:
            forecast_month_end = end_date
        
        print(f"Training: {current_train_start.strftime('%Y-%m-%d')} to {current_train_end.strftime('%Y-%m-%d')}")
        print(f"Forecast: {forecast_month_start.strftime('%Y-%m-%d')} to {forecast_month_end.strftime('%Y-%m-%d')}")
        
        forecast_mask = (df_daily['date'] >= forecast_month_start) & (df_daily['date'] <= forecast_month_end)
        forecast_df_month = df_daily[forecast_mask].copy()
        
        if len(forecast_df_month) == 0:
            print("No data available for this forecast period")
            continue
        
        forecast_dates = forecast_df_month['date'].values
        print(f"Forecasting {len(forecast_dates)} days...")
        
        # Daily inference with expanding window
        for day_idx, forecast_date in enumerate(forecast_dates):
            
            expand_train_end = forecast_date - pd.Timedelta(days=1)
            expand_train_mask = (df_daily['date'] >= current_train_start) & (df_daily['date'] <= expand_train_end)
            expand_train_df = df_daily[expand_train_mask].copy()
            
            expand_train_y = expand_train_df['quantity'].values
            expand_train_exog = expand_train_df[exog_features].values if has_exog else None
            
            daily_model = train_sarimax_model(expand_train_y, exog_data=expand_train_exog,
                                             order=CONFIG['SARIMAX_ORDER'],
                                             seasonal_order=CONFIG['SEASONAL_ORDER'])
            
            if daily_model is None:
                print(f"Failed to train model for {forecast_date}")
                continue
            
            date_mask = df_daily['date'] == forecast_date
            date_exog = df_daily[date_mask][exog_features].values if has_exog else None
            
            prediction = forecast_with_sarimax(daily_model, steps=1, exog_forecast=date_exog)
            
            if prediction is None:
                print(f"Failed to forecast for {forecast_date}")
                continue
            
            actual_value = df_daily[date_mask]['quantity'].values[0] if date_mask.any() else None
            
            all_predictions.append({
                'date': forecast_date,
                'predicted': float(prediction),
                'actual': actual_value,
                'train_start': current_train_start,
                'train_end': expand_train_end,
                'train_months': current_train_months,
                'train_days': len(expand_train_df),
                'month_iteration': month_idx + 1,
                'day_in_month': day_idx + 1
            })
            
            if (day_idx + 1) % 5 == 0 or (day_idx + 1) == len(forecast_dates):
                print(f"  Day {day_idx + 1}/{len(forecast_dates)}: {forecast_date} | Predicted: {prediction:.2f}")
        
        print(f"Completed {len(forecast_dates)} predictions")
        
        # PIPELINE 3: MONTHLY RETRAINING
        if month_idx < forecast_month_count - 1:
            print(f"\n{'='*80}")
            print(f"PIPELINE 3: MONTHLY RETRAINING (After Month {month_idx + 1})")
            print(f"{'='*80}")
            
            current_train_end = forecast_month_end
            current_train_months += 1
            
            retrain_mask = (df_daily['date'] >= current_train_start) & (df_daily['date'] <= current_train_end)
            retrain_df = df_daily[retrain_mask].copy()
            retrain_y = retrain_df['quantity'].values
            retrain_exog = retrain_df[exog_features].values if has_exog else None
            
            print(f"Retraining with {len(retrain_y)} days ({current_train_months} months)...")
            current_model = train_sarimax_model(retrain_y, exog_data=retrain_exog,
                                               order=CONFIG['SARIMAX_ORDER'],
                                               seasonal_order=CONFIG['SEASONAL_ORDER'])
            
            if current_model is None:
                print("Retraining failed, keeping previous model")
            else:
                retrained_model_path = os.path.join(CONFIG['MODEL_DIR'], 
                                                    f'sarimax_month_{month_idx + 1}_{current_train_months}months.pkl')
                with open(retrained_model_path, 'wb') as f:
                    pickle.dump(current_model, f)
                print(f"Retrained model saved: {retrained_model_path}")
    
    return pd.DataFrame(all_predictions)


# ============================================================================
# AGGREGATION FUNCTIONS
# ============================================================================

def aggregate_predictions(df_predictions_daily):
    """
    Aggregate daily predictions to weekly, bi-weekly, and monthly
    """
    results = {}
    
    # Daily
    df_predictions_daily['error'] = df_predictions_daily['actual'] - df_predictions_daily['predicted']
    df_predictions_daily['abs_error'] = abs(df_predictions_daily['error'])
    df_predictions_daily['pct_error'] = (df_predictions_daily['abs_error'] / df_predictions_daily['actual'] * 100).fillna(0)
    results['daily'] = df_predictions_daily
    
    # Weekly
    df_predictions_daily['week'] = df_predictions_daily['date'].dt.to_period('W')
    df_weekly = df_predictions_daily.groupby(['week', 'month_iteration']).agg({
        'predicted': 'sum',
        'actual': 'sum',
        'date': ['min', 'max']
    }).reset_index()
    df_weekly.columns = ['week', 'month_iteration', 'predicted', 'actual', 'week_start', 'week_end']
    df_weekly['error'] = df_weekly['actual'] - df_weekly['predicted']
    df_weekly['abs_error'] = abs(df_weekly['error'])
    df_weekly['pct_error'] = (df_weekly['abs_error'] / df_weekly['actual'] * 100).fillna(0)
    results['weekly'] = df_weekly
    
    # Bi-weekly
    df_predictions_daily['biweek'] = (df_predictions_daily['date'] - df_predictions_daily['date'].min()).dt.days // 14
    df_biweekly = df_predictions_daily.groupby(['biweek', 'month_iteration']).agg({
        'predicted': 'sum',
        'actual': 'sum',
        'date': ['min', 'max']
    }).reset_index()
    df_biweekly.columns = ['biweek', 'month_iteration', 'predicted', 'actual', 'period_start', 'period_end']
    df_biweekly['error'] = df_biweekly['actual'] - df_biweekly['predicted']
    df_biweekly['abs_error'] = abs(df_biweekly['error'])
    df_biweekly['pct_error'] = (df_biweekly['abs_error'] / df_biweekly['actual'] * 100).fillna(0)
    results['biweekly'] = df_biweekly
    
    # Monthly
    df_predictions_daily['month'] = df_predictions_daily['date'].dt.to_period('M')
    df_monthly = df_predictions_daily.groupby(['month', 'month_iteration']).agg({
        'predicted': 'sum',
        'actual': 'sum',
        'date': ['min', 'max']
    }).reset_index()
    df_monthly.columns = ['month', 'month_iteration', 'predicted', 'actual', 'month_start', 'month_end']
    df_monthly['error'] = df_monthly['actual'] - df_monthly['predicted']
    df_monthly['abs_error'] = abs(df_monthly['error'])
    df_monthly['pct_error'] = (df_monthly['abs_error'] / df_monthly['actual'] * 100).fillna(0)
    results['monthly'] = df_monthly
    
    return results


def save_predictions(results):
    """
    Save predictions to CSV files
    """
    for freq, df in results.items():
        output_file = os.path.join(CONFIG['OUTPUT_DIR'], f'predictions_{freq}.csv')
        df.to_csv(output_file, index=False)
        print(f"Saved {freq} predictions: {output_file}")


# ============================================================================
# FLASK API
# ============================================================================

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'time-series-forecasting'}), 200


@app.route('/train', methods=['POST'])
def train():
    """Training endpoint"""
    try:
        data = request.json
        data_file = data.get('data_file', 'City_Gas_CNG_Combined.csv')
        start_date = data.get('start_date', '2023-04-01')
        end_date = data.get('end_date', '2025-03-31')
        
        print(f"Loading data from: {data_file}")
        df_daily = load_and_prepare_data(data_file)
        
        print("Running forecasting pipeline...")
        df_predictions_daily = run_forecasting_pipeline(df_daily, start_date, end_date)
        
        print("Aggregating predictions...")
        results = aggregate_predictions(df_predictions_daily)
        
        print("Saving predictions...")
        save_predictions(results)
        
        # Calculate metrics
        valid_predictions = df_predictions_daily[df_predictions_daily['actual'].notna()]
        metrics = {}
        if len(valid_predictions) > 0:
            metrics = {
                'mae': float(mean_absolute_error(valid_predictions['actual'], valid_predictions['predicted'])),
                'rmse': float(np.sqrt(mean_squared_error(valid_predictions['actual'], valid_predictions['predicted']))),
                'mape': float(mean_absolute_percentage_error(valid_predictions['actual'], valid_predictions['predicted']) * 100)
            }
        
        return jsonify({
            'status': 'success',
            'total_predictions': len(df_predictions_daily),
            'metrics': metrics,
            'output_dir': CONFIG['OUTPUT_DIR']
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/predict', methods=['POST'])
def predict():
    """Prediction endpoint using saved model"""
    try:
        data = request.json
        model_file = data.get('model_file', f'sarimax_initial_{CONFIG["TRAIN_WINDOW_MONTHS"]}months.pkl')
        
        model_path = os.path.join(CONFIG['MODEL_DIR'], model_file)
        
        if not os.path.exists(model_path):
            return jsonify({'status': 'error', 'message': f'Model not found: {model_path}'}), 404
        
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        
        steps = data.get('steps', 1)
        exog_data = data.get('exog_data', None)
        
        if exog_data is not None:
            exog_data = np.array(exog_data)
        
        prediction = forecast_with_sarimax(model, steps=steps, exog_forecast=exog_data)
        
        if prediction is None:
            return jsonify({'status': 'error', 'message': 'Prediction failed'}), 500
        
        return jsonify({
            'status': 'success',
            'predictions': prediction.tolist() if isinstance(prediction, np.ndarray) else [float(prediction)]
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/models', methods=['GET'])
def list_models():
    """List available models"""
    try:
        model_files = [f for f in os.listdir(CONFIG['MODEL_DIR']) if f.endswith('.pkl')]
        return jsonify({
            'status': 'success',
            'models': model_files,
            'count': len(model_files)
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'train':
        # Run training pipeline
        print("Starting training pipeline...")
        data_file = sys.argv[2] if len(sys.argv) > 2 else 'City_Gas_CNG_Combined.csv'
        
        df_daily = load_and_prepare_data(data_file)
        df_predictions_daily = run_forecasting_pipeline(df_daily)
        results = aggregate_predictions(df_predictions_daily)
        save_predictions(results)
        
        print("\nTraining completed successfully!")
        print(f"Output directory: {CONFIG['OUTPUT_DIR']}")
        print(f"Model directory: {CONFIG['MODEL_DIR']}")
    else:
        # Start Flask API server
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
