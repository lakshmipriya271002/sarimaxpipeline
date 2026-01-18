#!/bin/bash

# Deployment script for AI Core

echo "==================================="
echo "AI Core Deployment Script"
echo "==================================="

# Variables
IMAGE_NAME="time-series-forecasting"
IMAGE_TAG="latest"
DOCKER_USER="priyaannamalai"
REGISTRY_URL="docker.io/${DOCKER_USER}"

# Step 1: Build Docker image
echo ""
echo "Step 1: Building Docker image..."
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

if [ $? -ne 0 ]; then
    echo "Error: Docker build failed"
    exit 1
fi

echo "Docker image built successfully: ${IMAGE_NAME}:${IMAGE_TAG}"

# Step 2: Login to Docker Hub
echo ""
echo "Step 2: Logging in to Docker Hub..."
echo "Please enter your Docker Hub password or access token:"
docker login -u ${DOCKER_USER}

# Step 3: Tag image for registry
echo ""
echo "Step 3: Tagging image for registry..."
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}

# Step 4: Push to registry
echo ""
echo "Step 4: Pushing image to registry..."
echo "Registry URL: ${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}"
read -p "Do you want to push to registry? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker push ${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}
    
    if [ $? -ne 0 ]; then
        echo "Error: Docker push failed"
        exit 1
    fi
    
    echo "Image pushed successfully!"
else
    echo "Skipping push to registry"
fi

# Step 5: Test locally (optional)
echo ""
echo "Step 5: Testing locally (optional)"
read -p "Do you want to test the container locally? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting container on port 5000..."
    docker run -p 5000:5000 --name ${IMAGE_NAME}-test ${IMAGE_NAME}:${IMAGE_TAG}
fi

echo ""
echo "==================================="
echo "Deployment script completed!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Update REGISTRY_URL in this script with your actual registry URL"
echo "2. Deploy to AI Core using the image: ${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}"
echo "3. Configure environment variables if needed"
echo "4. Set up persistent storage for models/ and outputs/ directories"
