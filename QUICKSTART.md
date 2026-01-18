# Quick Start Guide for AI Core Deployment

## Prerequisites
- Docker installed
- Access to a container registry (e.g., Docker Hub, SAP AI Core registry)
- SAP AI Core access (for production deployment)

## Local Testing

### 1. Build and Run Locally
```bash
# Build the Docker image
docker build -t time-series-forecasting:latest .

# Run the container
docker run -p 5000:5000 time-series-forecasting:latest

# Test the health endpoint
curl http://localhost:5000/health
```

### 2. Test Training (Command Line)
```bash
# Copy your data file to the deployment folder
cp ../City_Gas_CNG_Combined.csv .

# Run training in the container
docker run -v $(pwd):/data time-series-forecasting:latest python main.py train /data/City_Gas_CNG_Combined.csv
```

### 3. Test API Endpoints
```bash
# Health check
curl http://localhost:5000/health

# List models
curl http://localhost:5000/models

# Get predictions
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "model_file": "sarimax_initial_18months.pkl",
    "steps": 1
  }'
```

## AI Core Deployment

### Option 1: Using SAP AI Core UI
1. Log in to SAP AI Core Launchpad
2. Navigate to ML Operations → Deployments
3. Click "Create Deployment"
4. Upload `ai-core-config.yaml`
5. Configure parameters
6. Deploy

### Option 2: Using AI Core SDK

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

# Create deployment
deployment_resp = ai_core_client.deployment.create(
    configuration_id="<your-configuration-id>",
    resource_plan="infer.s"
)

print(f"Deployment ID: {deployment_resp.id}")
print(f"Deployment Status: {deployment_resp.status}")
```

### Option 3: Using CLI Script
```bash
# Update deploy.sh with your registry URL
# Then run:
./deploy.sh
```

## Environment Variables

Set these in your AI Core deployment:

- `PORT`: API port (default: 5000)
- `TRAIN_WINDOW_MONTHS`: Training window in months (default: 18)
- `FORECAST_HORIZON_DAYS`: Forecast horizon (default: 1)

## Persistent Storage

For production, mount persistent volumes for:
- `/app/models/` - Store trained models
- `/app/outputs/` - Store prediction outputs

## Scaling

The service supports horizontal scaling:
- `minReplicas`: 1
- `maxReplicas`: 3

Adjust in `ai-core-config.yaml` based on your needs.

## Monitoring

Health checks available at:
- Readiness: `GET /health`
- Liveness: `GET /health`

## Troubleshooting

### Container fails to start
- Check Docker logs: `docker logs <container-id>`
- Verify all dependencies in requirements.txt
- Ensure PORT is not already in use

### Out of memory errors
- Increase memory limits in ai-core-config.yaml
- Reduce TRAIN_WINDOW_MONTHS
- Use smaller dataset

### Model not found errors
- Ensure models are persisted to volume storage
- Check MODEL_DIR configuration
- Verify model files exist in /app/models/

## Production Checklist

- [ ] Update registry URL in deploy.sh
- [ ] Configure persistent storage for models
- [ ] Set up monitoring and alerting
- [ ] Configure resource limits appropriately
- [ ] Test with production data volume
- [ ] Set up backup for trained models
- [ ] Configure API authentication if needed
- [ ] Document API endpoints for consumers
- [ ] Set up CI/CD pipeline
- [ ] Configure log aggregation

## Next Steps

1. Test locally using Docker
2. Push image to registry
3. Deploy to AI Core development environment
4. Test all API endpoints
5. Monitor performance
6. Deploy to production when ready

## Support

For issues specific to:
- **Application**: Check main.py logs
- **Docker**: Review Dockerfile and build logs
- **AI Core**: Check AI Core documentation
- **Model Performance**: Review prediction metrics in outputs/
