# Deployment Guide - HIPAA-Compliant Prior Authorization System

## Table of Contents
1. [Quick Start](#quick-start)
2. [Local Development](#local-development)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Production Deployment](#kubernetes-production-deployment)
5. [Testing](#testing)
6. [Monitoring](#monitoring)
7. [Security Hardening](#security-hardening)

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- kubectl (for K8s deployment)
- Git

### Clone and Setup
```bash
# Clone the repository
git clone <repo-url>
cd prior-auth-system

# Install dependencies
pip install -r requirements.txt
```

---

## Local Development

### Run Individual Services

Each agent can run independently for development:

```bash
# Terminal 1: Auth Service
cd src/auth
python main.py

# Terminal 2: Validation Agent
cd src/agents/validation_agent
python main.py

# Terminal 3: Planner Agent
cd src/agents/planner_agent
python main.py

# Continue for other agents...
```

### Service Ports
- Auth Service: 8000
- Validation Agent: 8001
- Planner Agent: 8002
- Denial Prediction Agent: 8003
- FHIR Agent: 8004
- EDI Agent: 8005
- Explanation Agent: 8006
- Monitoring Agent: 8007
- API Gateway: 8080

---

## Docker Deployment

### Build and Run All Services

```bash
# Build all images
docker-compose build

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### Individual Service Management

```bash
# Restart a specific service
docker-compose restart planner-agent

# View logs for specific service
docker-compose logs -f fhir-agent

# Scale a service
docker-compose up -d --scale planner-agent=3
```

---

## Kubernetes Production Deployment

### Prerequisites
- Kubernetes cluster (1.24+)
- kubectl configured
- Container registry access

### Step 1: Build and Push Images

```bash
# Build images
docker build -t your-registry/prior-auth-auth:v1.0 -f Dockerfile \
  --build-arg SERVICE=auth .

docker build -t your-registry/prior-auth-validation:v1.0 -f Dockerfile \
  --build-arg SERVICE=validation .

# Repeat for all services...

# Push to registry
docker push your-registry/prior-auth-auth:v1.0
# ... push all images
```

### Step 2: Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Apply secrets (update with real values first!)
kubectl apply -f k8s/secrets.yaml

# Deploy services
kubectl apply -f k8s/deployments/

# Verify deployment
kubectl get pods -n prior-auth
kubectl get services -n prior-auth
```

### Step 3: Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n prior-auth

# Check services
kubectl get svc -n prior-auth

# View logs
kubectl logs -n prior-auth deployment/auth-service

# Port forward for testing
kubectl port-forward -n prior-auth svc/auth-service 8000:8000
```

---

## Testing

### Run Integration Tests

```bash
# Ensure all services are running
docker-compose up -d

# Wait for services to be ready (30 seconds)
sleep 30

# Run integration tests
python tests/integration/test_full_workflow.py
```

### Manual API Testing

```bash
# 1. Get authentication token
curl -X POST http://localhost:8000/token \
  -d "username=clinician&password=clinician123"

# 2. Submit prior auth request
curl -X POST http://localhost:8001/validate \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d @sample_request.json

# 3. Check status
curl http://localhost:8007/status/<REQUEST_ID>
```

### Sample Request (sample_request.json)

```json
{
  "request_type": "fhir",
  "payer": "UnitedHealthcare",
  "patient": {
    "id": "P12345",
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "1975-05-15",
    "gender": "Male",
    "member_id": "UHC123456789"
  },
  "provider": {
    "npi": "1234567890",
    "name": "Dr. Sarah Smith",
    "organization": "City Medical Center"
  },
  "service_request": {
    "procedure_code": "27447",
    "procedure_description": "Total knee arthroplasty",
    "diagnosis_codes": ["M17.11"],
    "quantity": 1,
    "place_of_service": "21",
    "service_date": "2024-03-15"
  }
}
```

---

## Monitoring

### Health Checks

```bash
# Check API Gateway health
curl http://localhost:8080/health

# Check individual service health
curl http://localhost:8000/health  # Auth
curl http://localhost:8001/health  # Validation
curl http://localhost:8002/health  # Planner
# ... etc
```

### Metrics

```bash
# Get system metrics
curl http://localhost:8080/metrics

# Denial prediction metrics
curl http://localhost:8003/metrics
```

### Logs

```bash
# Docker logs
docker-compose logs -f --tail=100

# Kubernetes logs
kubectl logs -n prior-auth -l app=planner-agent --tail=100 -f
```

---

## Security Hardening

### Production Checklist

#### 1. Secrets Management
- [ ] Replace all placeholder passwords in `k8s/secrets.yaml`
- [ ] Use HashiCorp Vault or AWS Secrets Manager
- [ ] Enable automatic secret rotation
- [ ] Never commit secrets to version control

#### 2. Network Security
- [ ] Enable TLS for all service-to-service communication
- [ ] Configure network policies to restrict pod-to-pod traffic
- [ ] Use ingress controller with TLS termination
- [ ] Enable VPC/subnet isolation

#### 3. Authentication & Authorization
- [ ] Implement OAuth2 with real identity provider
- [ ] Enable MFA for admin users
- [ ] Configure RBAC with least-privilege principle
- [ ] Regular token rotation

#### 4. Audit & Compliance
- [ ] Configure centralized logging (ELK/Splunk)
- [ ] Set up SIEM for security monitoring
- [ ] Enable audit log encryption
- [ ] Configure 6+ year log retention

#### 5. Container Security
- [ ] Scan images for vulnerabilities
- [ ] Use minimal base images (alpine)
- [ ] Run containers as non-root
- [ ] Enable pod security policies

### Update Secrets

```bash
# Generate strong secrets
openssl rand -base64 32

# Update Kubernetes secrets
kubectl create secret generic prior-auth-secrets \
  --from-literal=JWT_SECRET=$(openssl rand -base64 32) \
  --from-literal=DB_PASSWORD=$(openssl rand -base64 32) \
  -n prior-auth --dry-run=client -o yaml | kubectl apply -f -
```

### Enable TLS

```yaml
# Example ingress with TLS
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: prior-auth-ingress
  namespace: prior-auth
spec:
  tls:
  - hosts:
    - api.priorauth.example.com
    secretName: tls-secret
  rules:
  - host: api.priorauth.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: auth-service
            port:
              number: 8000
```

---

## Troubleshooting

### Common Issues

#### Services Not Starting
```bash
# Check logs
docker-compose logs <service-name>

# Check if ports are in use
netstat -tulpn | grep 800

# Restart services
docker-compose restart
```

#### Authentication Failing
```bash
# Verify credentials
# Default users:
# - username: admin, password: admin123
# - username: clinician, password: clinician123
# - username: reviewer, password: reviewer123

# Check auth service logs
docker-compose logs auth-service
```

#### Database Connection Issues
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Access database
docker-compose exec postgres psql -U audit_user -d prior_auth_audit

# Reset database
docker-compose down -v
docker-compose up -d
```

---

## Maintenance

### Backup

```bash
# Backup PostgreSQL audit logs
docker-compose exec postgres pg_dump -U audit_user prior_auth_audit > backup.sql

# Backup in Kubernetes
kubectl exec -n prior-auth postgres-0 -- pg_dump -U audit_user prior_auth_audit > backup.sql
```

### Updates

```bash
# Update images
docker-compose pull
docker-compose up -d

# Rolling update in Kubernetes
kubectl set image deployment/auth-service auth-service=new-image:tag -n prior-auth
kubectl rollout status deployment/auth-service -n prior-auth
```

---

## Support

For issues or questions:
1. Check the logs first
2. Review this documentation
3. Contact the development team
