# 🚀 SAP AI Core Deployment - Quick Reference

## 📁 Updated Folder Structure

```
deployment/
├── workflow/                          # SAP AI Core workflow templates
│   ├── training-workflow.yaml        # Training pipeline (Argo workflow)
│   ├── serving-workflow.yaml         # Serving API (KServe)
│   └── README.md                      # Workflow documentation
│
├── main.py                            # Main application
├── requirements.txt                   # Python dependencies
├── Dockerfile                         # Docker container
├── deploy.sh                          # Deployment script
├── .gitignore                         # Git ignore
│
└── Documentation/
    ├── INDEX.md                       # Navigation guide (START HERE!)
    ├── SUMMARY.md                     # Package overview
    ├── QUICKSTART.md                  # Quick start guide
    ├── README.md                      # Full documentation
    └── ARCHITECTURE.txt               # Visual diagrams
```

## ⚡ Quick Deploy (5 Steps)

### Step 1: Build Docker Image
```bash
cd /Users/i769086/Data\ Science/Pipeline/deployment

# Update this with your Docker username
DOCKER_USER="<YOUR_DOCKER_USERNAME>"

docker build -t ${DOCKER_USER}/time-series-forecasting:latest .
docker push ${DOCKER_USER}/time-series-forecasting:latest
```

### Step 2: Update Workflow Files
Edit these files in `workflow/` folder:

**training-workflow.yaml** (Line 37):
```yaml
image: docker.io/YOUR_DOCKER_USERNAME/time-series-forecasting:latest
```

**serving-workflow.yaml** (Line 67):
```yaml
image: docker.io/YOUR_DOCKER_USERNAME/time-series-forecasting:latest
```

Also update the secret names (Lines 20 in both files):
```yaml
imagePullSecrets:
  - name: your-docker-secret-name
```

### Step 3: Upload Data to S3
Upload your CSV file to SAP AI Core S3:
```
s3://your-bucket/data/City_Gas_CNG_Combined.csv
```

### Step 4: Deploy Training Workflow
1. Go to SAP AI Core UI
2. Navigate to **ML Operations** → **Scenarios**
3. Create/Select scenario: `time-series-forecasting`
4. Go to **Executables** → **Create**
5. Upload `workflow/training-workflow.yaml`
6. Create **Configuration** with parameters:
   - data-file: `City_Gas_CNG_Combined.csv`
   - start-date: `2023-04-01`
   - end-date: `2025-03-31`
   - train-window-months: `18`
7. Create **Execution** and monitor progress
8. Wait for completion (~30-60 minutes)

### Step 5: Deploy Serving API
1. Go to **Deployments** → **Create**
2. Upload `workflow/serving-workflow.yaml`
3. Create **Configuration**
4. Link model artifact from training execution
5. Create **Deployment**
6. Wait for status: **RUNNING**
7. Test the API!

## 🧪 Test Your Deployment

```bash
# Get your deployment URL from SAP AI Core
DEPLOYMENT_URL="https://api.ai.sap.com/v2/inference/deployments/<deployment-id>"
TOKEN="<your-auth-token>"

# Health check
curl -H "Authorization: Bearer ${TOKEN}" ${DEPLOYMENT_URL}/health

# List models
curl -H "Authorization: Bearer ${TOKEN}" ${DEPLOYMENT_URL}/models

# Get predictions
curl -X POST ${DEPLOYMENT_URL}/predict \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "model_file": "sarimax_initial_18months.pkl",
    "steps": 7
  }'
```

## 📋 What Each Workflow Does

### Training Workflow (training-workflow.yaml)
```
Pipeline 1: Initial Training (18 months)
    ↓
Pipeline 2: Daily Inference (expanding window)
    → Day 1: Predict using 18 months
    → Day 2: Predict using 18 months + 1 day
    → Day 3: Predict using 18 months + 2 days
    → ...
    → Day 30: Predict using 18 months + 29 days
    ↓
Pipeline 3: Monthly Retraining
    → After 30 days, retrain with 19 months
    → Repeat Pipeline 2 for next month
    ↓
Output:
    → Trained models (saved to S3)
    → Predictions (daily/weekly/monthly) (saved to S3)
```

### Serving Workflow (serving-workflow.yaml)
```
Load trained models from S3
    ↓
Start Flask REST API server
    ↓
Endpoints available:
    ✓ GET  /health    → Health check
    ✓ GET  /models    → List available models
    ✓ POST /predict   → Get predictions
    ✓ POST /train     → Run training (optional)
```

## 🔧 Configuration Options

### Training Parameters
Edit in `training-workflow.yaml` (lines 17-28):
```yaml
arguments:
  parameters:
  - name: data-file
    value: "City_Gas_CNG_Combined.csv"  # Your CSV file
  - name: start-date
    value: "2023-04-01"                  # Start date
  - name: end-date
    value: "2025-03-31"                  # End date
  - name: train-window-months
    value: "18"                          # Initial training window
```

### Resource Allocation
Edit in both workflow files:

**Training** (lines 89-95 in training-workflow.yaml):
```yaml
resources:
  requests:
    memory: "4Gi"    # Increase if needed
    cpu: "2"         # Increase if needed
  limits:
    memory: "8Gi"
    cpu: "4"
```

**Serving** (lines 101-107 in serving-workflow.yaml):
```yaml
resources:
  requests:
    memory: "2Gi"    # Adjust based on model size
    cpu: "1"
  limits:
    memory: "4Gi"
    cpu: "2"
```

## 📊 Expected Outputs

After training completes, you'll get these artifacts in S3:

### Models Directory
```
models/<execution-id>/models/
├── sarimax_initial_18months.pkl     # Initial model
├── sarimax_month_1_19months.pkl     # After month 1
├── sarimax_month_2_20months.pkl     # After month 2
└── ... (one per month forecasted)
```

### Predictions Directory
```
models/<execution-id>/outputs/
├── predictions_daily.csv            # Daily predictions
├── predictions_weekly.csv           # Weekly aggregations
├── predictions_biweekly.csv         # Bi-weekly aggregations
└── predictions_monthly.csv          # Monthly aggregations
```

## ⏱️ Estimated Time

| Step | Duration |
|------|----------|
| Docker build & push | 5-10 minutes |
| Update YAML files | 5 minutes |
| Upload data to S3 | 2 minutes |
| Training execution | 30-60 minutes |
| Serving deployment | 2-5 minutes |
| **Total** | **~45-80 minutes** |

## ❗ Common Issues

### 1. ImagePullBackOff
- **Cause**: Docker image not found or secret incorrect
- **Fix**: Verify image exists and secret name is correct

### 2. Training OOM (Out of Memory)
- **Cause**: Insufficient memory for training
- **Fix**: Increase `resources.requests.memory` in training-workflow.yaml

### 3. Model Not Found in Serving
- **Cause**: Model artifact not properly linked
- **Fix**: Ensure you selected the correct artifact from training execution

### 4. S3 Access Error
- **Cause**: Incorrect S3 path or permissions
- **Fix**: Verify S3 path and check AI Core has access

## 📞 Need Help?

| For | Check |
|-----|-------|
| Workflow setup | `workflow/README.md` |
| Application code | `main.py` (commented) |
| Docker issues | `Dockerfile` |
| General info | `INDEX.md` |
| Full docs | `README.md` |

## ✅ Pre-Deployment Checklist

- [ ] Docker image built and pushed
- [ ] Updated image name in both YAML files
- [ ] Updated docker registry secret name
- [ ] Data uploaded to S3
- [ ] S3 path updated in training-workflow.yaml
- [ ] Resource limits configured appropriately
- [ ] Docker registry secret exists in SAP AI Core
- [ ] S3 object store configured in SAP AI Core

## 🎯 Success Criteria

Training is successful when:
- ✅ Execution status: COMPLETED
- ✅ Model artifacts saved to S3
- ✅ Prediction files saved to S3
- ✅ No error messages in logs

Serving is successful when:
- ✅ Deployment status: RUNNING
- ✅ Health check returns 200 OK
- ✅ Models listed via /models endpoint
- ✅ Predictions work via /predict endpoint

---

**You're ready to deploy to SAP AI Core!** 🚀

Start with `workflow/README.md` for detailed deployment instructions.
