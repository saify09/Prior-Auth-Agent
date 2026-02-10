#!/bin/bash

# Quick Start Script for Prior Authorization System
# This script sets up and runs the entire system locally

set -e

echo "=============================================="
echo " Prior Authorization System - Quick Start"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites met${NC}"
echo ""

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Build Docker images
echo -e "${YELLOW}Building Docker images...${NC}"
docker-compose build --quiet
echo -e "${GREEN}✓ Images built${NC}"
echo ""

# Start services
echo -e "${YELLOW}Starting services...${NC}"
docker-compose up -d

echo -e "${GREEN}✓ Services started${NC}"
echo ""

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to be ready (30 seconds)...${NC}"
sleep 30

# Health check
echo -e "${YELLOW}Performing health checks...${NC}"
echo ""

services=(
    "auth-service:8000"
    "validation-agent:8001"
    "planner-agent:8002"
    "denial-prediction-agent:8003"
    "fhir-agent:8004"
    "edi-agent:8005"
    "explanation-agent:8006"
    "monitoring-agent:8007"
)

all_healthy=true

for service in "${services[@]}"; do
    IFS=':' read -r name port <<< "$service"
    if curl -sf http://localhost:$port/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ $name${NC}"
    else
        echo -e "${RED}✗ $name (not responding)${NC}"
        all_healthy=false
    fi
done

echo ""

if [ "$all_healthy" = true ]; then
    echo -e "${GREEN}=============================================="
    echo " ✓ System is ready!"
    echo "==============================================${NC}"
    echo ""
    echo "Services are running on:"
    echo "  - Auth Service:              http://localhost:8000"
    echo "  - Validation Agent:          http://localhost:8001"
    echo "  - Planner Agent:             http://localhost:8002"
    echo "  - Denial Prediction Agent:   http://localhost:8003"
    echo "  - FHIR Agent:                http://localhost:8004"
    echo "  - EDI Agent:                 http://localhost:8005"
    echo "  - Explanation Agent:         http://localhost:8006"
    echo "  - Monitoring Agent:          http://localhost:8007"
    echo ""
    echo "Default credentials:"
    echo "  - Admin:     admin / admin123"
    echo "  - Clinician: clinician / clinician123"
    echo "  - Reviewer:  reviewer / reviewer123"
    echo ""
    echo "To run tests:"
    echo "  python tests/integration/test_full_workflow.py"
    echo ""
    echo "To view logs:"
    echo "  docker-compose logs -f"
    echo ""
    echo "To stop the system:"
    echo "  docker-compose down"
    echo ""
else
    echo -e "${RED}=============================================="
    echo " ✗ Some services failed to start"
    echo "==============================================${NC}"
    echo ""
    echo "Check logs with: docker-compose logs"
    exit 1
fi
