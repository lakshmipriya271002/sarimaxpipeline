# SAP AI Core Workflow Templates

This folder contains the workflow templates for deploying the time series forecasting pipeline to SAP AI Core.

## Files

- **training-workflow.yaml**: Workflow template for training the SARIMAX model
- **serving-workflow.yaml**: Serving template for the prediction API

## Architecture Overview

### Training Pipeline (training-workflow.yaml)
```
Input: CSV data from S3
  ↓
[Pipeline 1: Initial Training]
  → Train SARIMAX on 18 months of data
  ↓
[Pipeline 2: Daily Inference]
  → Predict each day using expanding window
  → Retrain daily with updated data
  ↓
[Pipeline 3: Monthly Retraining]
  → After 1 month, retrain with expanded dataset
  → Repeat for all forecast months
  ↓
Output: Trained models + Predictions to S3
```

### Serving Pipeline (serving-workflow.yaml)
```
Input: Trained models from S3
  ↓
[Flask REST API Server]
  → Load saved models
  → Serve predictions via API
  ↓
Endpoints:
  - GET  /health
  - GET  /models
  - POST /predict
  - POST /train
```

## Prerequisites

1. **Docker Image**: Build and push your Docker image
   ```bash
   cd ..
   docker build -t <YOUR_DOCKER_USERNAME>/time-series-forecasting:latest .
   docker push <YOUR_DOCKER_USERNAME>/time-series-forecasting:latest
   ```

2. **Docker Registry Secret**: Create a secret in SAP AI Core for your Docker registry
   ```bash
   # This is usually done through SAP AI Core UI or CLI
   ```

3. **S3 Object Store**: Set up S3 bucket for storing:
   - Input data: `data/City_Gas_CNG_Combined.csv`
   - Trained models: `models/<workflow-name>/models/`
   - Predictions: `models/<workflow-name>/outputs/`

## Customization Required

Before deploying, update the following in **both YAML files**:

### 1. Docker Image Name
Replace `<YOUR_DOCKER_USERNAME>` with your actual Docker username:
```yaml
image: docker.io/<YOUR_DOCKER_USERNAME>/time-series-forecasting:latest
```

### 2. Docker Registry Secret
Replace with your actual secret name:
```yaml
imagePullSecrets:
  - name: docker-registry-secret  # Change this to your secret name
```

### 3. S3 Paths (training-workflow.yaml)
Update S3 paths to match your bucket structure:
```yaml
s3:
  key: "data/City_Gas_CNG_Combined.csv"  # Update to your S3 path
```

### 4. Resource Plans
Choose appropriate resource plans based on your needs:
- Training: `train.l` (large), `train.m` (medium), `train.s` (small)
- Serving: `infer.s` (small), `infer.m` (medium), `infer.l` (large)

## Deployment Steps

### Step 1: Prepare Data
Upload your CSV file to S3:
```bash
# Upload via SAP AI Core UI or AWS CLI
aws s3 cp City_Gas_CNG_Combined.csv s3://<your-bucket>/data/
```

### Step 2: Deploy Training Workflow

#### Option A: Using SAP AI Core UI
1. Log in to SAP AI Core Launchpad
2. Navigate to **ML Operations** → **Scenarios**
3. Create or select scenario: `time-series-forecasting`
4. Go to **Executables** → **Create**
5. Upload `training-workflow.yaml`
6. Configure parameters:
   - `data-file`: City_Gas_CNG_Combined.csv
   - `start-date`: 2023-04-01
   - `end-date`: 2025-03-31
   - `train-window-months`: 18
7. Click **Create Execution**
8. Monitor training progress in Executions tab

#### Option B: Using SAP AI Core SDK
```python
from ai_core_sdk.ai_core_v2_client import AICoreV2Client

# Initialize client
ai_core_client = AICoreV2Client(
    base_url="<your-ai-core-url>",
    auth_url="<your-auth-url>",
    client_id="<your-client-id>",
    client_secret="<your-client-secret>",
    resource_group="<your-resource-group>"
)

# Create execution (training)
execution_resp = ai_core_client.execution.create(
    configuration_id="<your-configuration-id>",
    input_artifact_bindings=[
        {
            "key": "data",
            "artifact_id": "<your-data-artifact-id>"
        }
    ],
    parameter_bindings={
        "data-file": "City_Gas_CNG_Combined.csv",
        "start-date": "2023-04-01",
        "end-date": "2025-03-31",
        "train-window-months": "18"
    }
)

print(f"Execution ID: {execution_resp.id}")
print(f"Status: {execution_resp.status}")

# Check execution status
status = ai_core_client.execution.get(execution_resp.id)
print(f"Current Status: {status.status}")
```

### Step 3: Deploy Serving API

#### Option A: Using SAP AI Core UI
1. Go to **Deployments** → **Create**
2. Upload `serving-workflow.yaml`
3. Select the trained model artifact from training execution
4. Configure parameters:
   - `model-name`: sarimax_initial_18months.pkl
   - `port`: 5000
5. Click **Create Deployment**
6. Wait for deployment to be RUNNING
7. Get the deployment URL

#### Option B: Using SAP AI Core SDK
```python
# Create deployment (serving)
deployment_resp = ai_core_client.deployment.create(
    configuration_id="<your-serving-config-id>",
    resource_plan="infer.s",
    input_artifact_bindings=[
        {
            "key": "models",
            "artifact_id": "<model-artifact-id-from-training>"
        }
    ]
)

print(f"Deployment ID: {deployment_resp.id}")
print(f"Status: {deployment_resp.status}")
print(f"Deployment URL: {deployment_resp.deployment_url}")
```

### Step 4: Test the API

```bash
# Get deployment URL from SAP AI Core
DEPLOYMENT_URL="<your-deployment-url>"

# Health check
curl ${DEPLOYMENT_URL}/health

# List available models
curl ${DEPLOYMENT_URL}/models

# Get predictions
curl -X POST ${DEPLOYMENT_URL}/predict \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "model_file": "sarimax_initial_18months.pkl",
    "steps": 7
  }'
```

## Parameters

### Training Workflow Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| data-file | City_Gas_CNG_Combined.csv | Input CSV file name in S3 |
| start-date | 2023-04-01 | Training start date |
| end-date | 2025-03-31 | Training end date |
| train-window-months | 18 | Initial training window in months |

### Serving Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| model-name | sarimax_initial_18months.pkl | Model file to load |
| port | 5000 | API server port |

## Monitoring

### Training Progress
Monitor training execution in SAP AI Core UI:
1. Go to **ML Operations** → **Executions**
2. Find your execution by name
3. Check logs for progress:
   - Pipeline 1: Initial training
   - Pipeline 2: Daily inference
   - Pipeline 3: Monthly retraining
4. Download output artifacts (models and predictions)

### Serving Health
Monitor serving deployment:
1. Go to **ML Operations** → **Deployments**
2. Check deployment status (should be RUNNING)
3. View logs for API requests
4. Use `/health` endpoint for health checks

## Output Artifacts

### From Training Workflow

**Models** (saved to S3):
```
models/<workflow-name>/models/
├── sarimax_initial_18months.pkl
├── sarimax_month_1_19months.pkl
├── sarimax_month_2_20months.pkl
└── ... (one per month)
```

**Predictions** (saved to S3):
```
models/<workflow-name>/outputs/
├── predictions_daily.csv
├── predictions_weekly.csv
├── predictions_biweekly.csv
└── predictions_monthly.csv
```

## Resource Requirements

### Training
- **Memory**: 4-8 GB
- **CPU**: 2-4 cores
- **Duration**: 30-60 minutes (depends on data size)
- **Storage**: 1 GB for models

### Serving
- **Memory**: 2-4 GB
- **CPU**: 1-2 cores
- **Replicas**: 1-3 (auto-scaling)
- **Storage**: 1 GB for models

## Troubleshooting

### Training Fails

**Issue**: Out of memory
- **Solution**: Increase memory in `resources.requests.memory` and `resources.limits.memory`

**Issue**: Data not found
- **Solution**: Verify S3 path in `inputs.artifacts.s3.key`

**Issue**: Model training error
- **Solution**: Check logs for specific error, verify data format

### Serving Fails

**Issue**: Pod not starting
- **Solution**: Check image pull secret, verify Docker image exists

**Issue**: Health check failing
- **Solution**: Check Flask server logs, verify port 5000 is accessible

**Issue**: Model not found
- **Solution**: Ensure model artifact is properly bound from training execution

## Best Practices

1. **Version Control**: Tag your Docker images with versions (e.g., `:v1.0`, `:v1.1`)
2. **Model Versioning**: Include timestamps or version numbers in model names
3. **Resource Planning**: Start with smaller resource plans and scale up as needed
4. **Monitoring**: Set up alerts for deployment health and performance
5. **Data Backup**: Keep backups of training data and trained models
6. **Testing**: Test in development environment before production deployment
7. **Documentation**: Document parameter changes and model versions

## Next Steps

1. ✅ Customize YAML files with your values
2. ✅ Build and push Docker image
3. ✅ Upload data to S3
4. ✅ Deploy training workflow
5. ✅ Monitor training execution
6. ✅ Deploy serving API
7. ✅ Test API endpoints
8. ✅ Set up monitoring and alerts

## Support

For SAP AI Core specific issues:
- Check SAP AI Core documentation
- Review workflow logs in UI
- Contact SAP AI Core support

For application issues:
- Review `main.py` code
- Check Docker container logs
- Test locally first

## Example: Complete Deployment Flow

```bash
# 1. Build and push Docker image
cd /Users/i769086/Data\ Science/Pipeline/deployment
docker build -t mydockerusername/time-series-forecasting:v1.0 .
docker push mydockerusername/time-series-forecasting:v1.0

# 2. Upload data to S3 (via UI or CLI)
# Upload City_Gas_CNG_Combined.csv to s3://mybucket/data/

# 3. Update YAML files
# Replace <YOUR_DOCKER_USERNAME> with mydockerusername
# Replace docker-registry-secret with your actual secret name

# 4. Deploy via SAP AI Core UI
# - Upload training-workflow.yaml
# - Create execution with parameters
# - Wait for completion (~30-60 min)

# 5. Deploy serving API
# - Upload serving-workflow.yaml
# - Link to trained model artifact
# - Create deployment
# - Wait for RUNNING status

# 6. Test the API
curl https://api.ai.sap.com/v2/inference/deployments/<deployment-id>/health
```

---

**Ready to deploy!** 🚀

Update the YAML files with your specific values and follow the deployment steps above.
