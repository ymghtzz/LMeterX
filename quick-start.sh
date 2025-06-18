#!/bin/bash

# LMeterX Quick Deployment Script
# Use pre-built Docker images to quickly start all services

set -e

echo "🚀 LMeterX Quick Deployment Script"
echo "=================================="

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed, please install Docker first"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Error: Docker Compose is not installed, please install Docker Compose first"
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs

# Download necessary configuration files (if not exists)
if [ ! -f "docker-compose.yml" ]; then
    echo "📥 Downloading docker-compose.yml..."
    curl -o docker-compose.yml https://raw.githubusercontent.com/DataEval/LuckyYC/LMeterX/main/docker-compose.yml
fi

# Pull latest images
echo "📦 Pulling latest Docker images..."
docker pull charmy1220/lmeterx-mysql:latest
docker pull charmy1220/lmeterx-be:latest
docker pull charmy1220/lmeterx-eng:latest
docker pull charmy1220/lmeterx-fe:latest

# Stop and clean up old containers (if exists)
echo "🧹 Cleaning up old containers..."
docker-compose -f docker-compose.yml down --remove-orphans 2>/dev/null || true

# Start services
echo "🚀 Starting LMeterX services..."
docker-compose -f docker-compose.yml up -d

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 10

# Check service status
echo "🔍 Checking service status..."
docker-compose -f docker-compose.yml ps

echo ""
echo "✅ LMeterX deployment completed!"
echo ""
echo "📋 Access Information:"
echo "  🌐 Frontend: http://localhost:8080"
echo "  🔧 Backend API: http://localhost:5001"
echo "  ⚡ Load Testing Engine: http://localhost:5002"
echo ""
echo "📝 Common Commands:"
echo "  Check service status: docker-compose -f docker-compose.yml ps"
echo "  View logs: docker-compose -f docker-compose.yml logs -f"
echo "  Stop services: docker-compose -f docker-compose.yml down"
echo "  Restart services: docker-compose -f docker-compose.yml restart"
echo ""
echo "🎉 Start using LMeterX for performance testing!"
