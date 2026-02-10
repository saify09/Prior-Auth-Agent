# HIPAA-Compliant AI Prior Authorization System

## Overview
This is a production-ready agentic AI prior authorization platform supporting UnitedHealthcare, Cigna, and Aetna payers. It uses both HL7 FHIR R4 and legacy X12 EDI 278 transactions with strict HIPAA compliance.

## Architecture
The system is built as microservices ("agents") operating under an orchestration layer:
- **Validation Agent**: Validates requests and authentication
- **Planner Agent**: Orchestrates the workflow
- **Denial Prediction Agent**: ML-based risk scoring
- **FHIR Agent**: FHIR R4 API integration
- **EDI Agent**: X12 EDI 278 transaction handling
- **Monitoring Agent**: Tracks authorization status
- **Explanation Agent**: Provides decision rationale

## Tech Stack
- **Backend**: Python 3.11+ with FastAPI
- **Authentication**: OAuth2/JWT
- **Containerization**: Docker
- **Orchestration**: Kubernetes
- **Message Queue**: RabbitMQ
- **Database**: PostgreSQL (Audit logs)
- **Secrets**: HashiCorp Vault simulation
- **ML**: scikit-learn (denial prediction model)

## Project Structure
```
.
├── src/
│   ├── agents/                  # All agent microservices
│   │   ├── validation_agent/
│   │   ├── planner_agent/
│   │   ├── denial_prediction_agent/
│   │   ├── fhir_agent/
│   │   ├── edi_agent/
│   │   ├── explanation_agent/
│   │   └── monitoring_agent/
│   ├── auth/                    # OAuth2 service
│   ├── common/                  # Shared utilities
│   └── models/                  # Data models
├── k8s/                         # Kubernetes manifests
├── docker/                      # Dockerfiles
├── tests/                       # Test suites
└── docs/                        # Documentation

```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- kubectl (for Kubernetes deployment)

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run with Docker Compose
docker-compose up -d

# Access API
curl http://localhost:8000/health
```

### Run Individual Agent
```bash
# Example: Run validation agent
cd src/agents/validation_agent
uvicorn main:app --reload --port 8001
```

## API Endpoints

### Authentication
- `POST /auth/token` - Get JWT token

### Prior Authorization
- `POST /api/v1/prior-auth/fhir` - Submit FHIR prior auth request
- `POST /api/v1/prior-auth/edi` - Submit EDI 278 request
- `GET /api/v1/prior-auth/{id}/status` - Check status

## Security Features
- OAuth2/JWT authentication
- Encrypted audit logs
- PHI-safe logging
- TLS between services
- Secrets vault integration
- RBAC enforcement

## Compliance
- HIPAA compliant audit trails (6+ year retention)
- CMS FHIR R4 mandate support
- X12 EDI 278 standard
- DaVinci PAS/CRD/DTR guidelines

## Testing
```bash
# Run all tests
pytest tests/

# Integration tests
pytest tests/integration/

# Security tests
pytest tests/security/
```

## Deployment

### Kubernetes
```bash
# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/deployments/
kubectl apply -f k8s/services/

# Check status
kubectl get pods -n prior-auth
```

## Monitoring
- Prometheus metrics at `/metrics`
- Health checks at `/health`
- Audit logs in PostgreSQL

## License
### Saifuddin Hanif
Proprietary - Internal Use Only
