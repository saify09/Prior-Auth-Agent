# System Architecture Documentation

## Overview
This document describes the architecture of the HIPAA-Compliant AI Prior Authorization System.

## System Components

### 1. Authentication Service (Port 8000)
**Purpose**: Centralized OAuth2/JWT authentication  
**Technology**: FastAPI, Python-JOSE  
**Key Features**:
- OAuth2 password flow
- JWT token issuance and validation
- User role management (admin, clinician, reviewer)
- Token expiration and refresh

**Security**:
- Bcrypt password hashing
- 30-minute token expiration
- Audit logging of all auth events

### 2. Validation Agent (Port 8001)
**Purpose**: Request validation and schema checking  
**Responsibilities**:
- Validate FHIR/EDI request structure
- Verify authentication tokens
- Check user permissions
- Sanitize PHI from logs
- Forward valid requests to Planner

**Validation Rules**:
- Patient: member_id, date_of_birth required
- Provider: Valid 10-digit NPI
- Service: procedure_code, diagnosis_codes required

### 3. Planner Agent (Port 8002)
**Purpose**: Workflow orchestration  
**Responsibilities**:
- Coordinate all other agents
- Route requests to FHIR or EDI agent
- Invoke denial prediction
- Determine if human review needed
- Manage request lifecycle

**Decision Logic**:
```python
if risk_score >= 0.6:
    flag_for_human_review()
elif request_type == "fhir":
    send_to_fhir_agent()
else:
    send_to_edi_agent()
```

### 4. Denial Prediction Agent (Port 8003)
**Purpose**: ML-based denial risk scoring  
**Algorithm**: Rule-based model (extensible to ML)  

**Risk Factors**:
1. Base payer denial rate (15-18%)
2. Procedure complexity (+20% if high-risk CPT)
3. Missing documentation (+25%)
4. Multiple diagnoses (+10%)
5. Provider history (+15%)

**Output**:
- Risk score (0.0 - 1.0)
- Risk level (low/medium/high)
- Contributing factors
- Confidence score

### 5. FHIR Agent (Port 8004)
**Purpose**: FHIR R4 API integration  
**Standards**: HL7 FHIR R4, DaVinci PAS IG  

**Resources Created**:
- Patient (US Core profile)
- Claim (prior authorization)
- Bundle (transaction)

**Payer Integration**:
```
UHC    -> https://api.uhc.com/fhir/r4
Cigna  -> https://api.cigna.com/fhir/r4
Aetna  -> https://api.aetna.com/fhir/r4
```

### 6. EDI Agent (Port 8005)
**Purpose**: X12 EDI 278 transaction handling  
**Standard**: HIPAA 5010  

**EDI Segments**:
- ISA: Interchange header
- GS: Functional group
- ST: Transaction set (278)
- BHT: Beginning of transaction
- HL: Hierarchical levels (requester, patient)
- NM1: Entity names
- DMG: Demographics
- HI: Diagnosis codes
- SV1: Service request

### 7. Explanation Agent (Port 8006)
**Purpose**: Decision transparency and explainability  
**Features**:
- Explain denial predictions
- Provide actionable recommendations
- Detail workflow decisions
- Human-readable rationale

**Example Output**:
```
Risk: HIGH (72%)
Factors:
  - Missing supporting documentation (High impact)
  - High-complexity procedure (Medium impact)
Recommendations:
  - CRITICAL: Route to human reviewer
  - Add comprehensive clinical notes
  - Include test results and imaging
```

### 8. Monitoring Agent (Port 8007)
**Purpose**: Track authorization status  
**Features**:
- Poll payer systems for updates
- Track pending requests
- Auto-polling every 5 minutes
- Status change notifications

**Tracking Info**:
- Request ID
- Payer response ID
- Current status
- Poll count
- Last update timestamp

## Data Flow

### Complete Request Flow

```
External Client
    ↓
API Gateway (8080)
    ↓
Auth Service (8000) - Validates token
    ↓
Validation Agent (8001) - Validates request
    ↓
Planner Agent (8002) - Orchestrates workflow
    ↓
    ├→ Denial Prediction Agent (8003)
    │   └→ Returns risk score
    ↓
    ├→ FHIR Agent (8004) - If FHIR request
    │   └→ Payer FHIR API
    │
    └→ EDI Agent (8005) - If EDI request
        └→ Payer EDI Gateway
    ↓
Monitoring Agent (8007) - Tracks status
    ↓
Response to Client
```

## Security Architecture

### Authentication Flow
```
1. Client → POST /token (username, password)
2. Auth Service validates credentials
3. Auth Service issues JWT with scopes
4. Client includes JWT in Authorization header
5. Each agent validates JWT before processing
```

### Audit Trail
Every operation is logged:
```json
{
  "timestamp": "2024-02-10T12:00:00Z",
  "agent": "planner_agent",
  "request_id": "PA-123456",
  "action": "workflow_started",
  "status": "success",
  "user_id": "clinician_001",
  "details": {
    "request_type": "fhir",
    "payer": "UnitedHealthcare"
  }
}
```

### PHI Protection
- PHI never logged in plaintext
- Names/DOB/IDs hashed before logging
- Audit logs encrypted at rest
- Access control via RBAC

## Database Schema

### Audit Logs Table
```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    request_id VARCHAR(255) NOT NULL,
    agent VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    user_id VARCHAR(100),
    status VARCHAR(50) NOT NULL,
    details JSONB,
    phi_safe BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_request_id ON audit_logs(request_id);
CREATE INDEX idx_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_agent ON audit_logs(agent);
```

## Deployment Architecture

### Docker Compose (Development)
- All services in single docker-compose.yml
- Shared network for service discovery
- PostgreSQL for audit logs
- RabbitMQ for messaging (future use)

### Kubernetes (Production)
```
Namespace: prior-auth
├── Deployments
│   ├── auth-service (2 replicas)
│   ├── validation-agent (2 replicas)
│   ├── planner-agent (3 replicas)
│   ├── denial-prediction-agent (2 replicas)
│   ├── fhir-agent (2 replicas)
│   ├── edi-agent (2 replicas)
│   ├── explanation-agent (2 replicas)
│   └── monitoring-agent (2 replicas)
├── Services (ClusterIP)
├── Secrets
│   ├── prior-auth-secrets
│   └── payer-credentials
└── ConfigMaps
```

## Scalability

### Horizontal Scaling
All agents are stateless and can scale horizontally:
```bash
kubectl scale deployment planner-agent --replicas=5 -n prior-auth
```

### Load Balancing
- Kubernetes Service provides automatic load balancing
- Each service has ClusterIP for internal routing
- Ingress controller for external access

### Performance Targets
- Request validation: < 100ms
- Denial prediction: < 500ms
- FHIR submission: < 2s
- EDI submission: < 2s
- End-to-end: < 5s

## Monitoring & Observability

### Health Checks
Every service exposes `/health`:
```json
{
  "status": "healthy",
  "service": "planner_agent",
  "uptime": 3600,
  "version": "1.0.0"
}
```

### Metrics
Prometheus-compatible metrics at `/metrics`:
- Request count
- Response times
- Error rates
- Active connections

### Logging
Structured JSON logs to stdout:
- Captured by Docker/Kubernetes
- Forwarded to centralized logging (ELK/Splunk)
- Searchable by request_id

## Compliance Features

### HIPAA Compliance
✓ Audit logging (6+ year retention)  
✓ Encryption at rest and in transit  
✓ Access controls (RBAC)  
✓ PHI-safe logging  
✓ Secure authentication  
✓ Regular security scans  

### Industry Standards
✓ HL7 FHIR R4  
✓ X12 EDI 278/277  
✓ DaVinci PAS IG  
✓ OAuth2/JWT  
✓ TLS 1.2+  

## Disaster Recovery

### Backup Strategy
- PostgreSQL: Daily automated backups
- Audit logs: Replicated to S3/GCS
- Configuration: Version controlled in Git

### Recovery Procedure
1. Restore database from backup
2. Deploy latest code from Git
3. Apply Kubernetes manifests
4. Verify all services healthy
5. Resume operations

### RTO/RPO
- Recovery Time Objective (RTO): 1 hour
- Recovery Point Objective (RPO): 24 hours

## Future Enhancements

1. **Real ML Model**: Replace rule-based prediction with trained model
2. **Message Queue**: Use RabbitMQ/Kafka for async processing
3. **Caching**: Redis for frequently accessed data
4. **GraphQL**: Alternative API for complex queries
5. **WebSocket**: Real-time status updates
6. **Mobile App**: Native iOS/Android clients
7. **HL7 v2**: Support for legacy HL7 messages
8. **SMART on FHIR**: EHR integration
