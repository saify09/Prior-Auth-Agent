"""
API Gateway - Single entry point for all external requests
Handles routing, rate limiting, and initial security
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from typing import Dict
import time

import sys
sys.path.append('/home/claude/prior-auth-system/src')

from common.utils import AuditLogger


app = FastAPI(
    title="Prior Authorization API Gateway",
    version="1.0.0",
    description="HIPAA-Compliant AI Prior Authorization System"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

audit_logger = AuditLogger("api_gateway")

# Service URLs
VALIDATION_SERVICE = "http://localhost:8001"
AUTH_SERVICE = "http://localhost:8000"
MONITORING_SERVICE = "http://localhost:8007"
EXPLANATION_SERVICE = "http://localhost:8006"


# Rate limiting (simple in-memory, use Redis in production)
request_counts: Dict[str, list] = {}
RATE_LIMIT = 100  # requests per minute
RATE_WINDOW = 60  # seconds


def check_rate_limit(client_ip: str) -> bool:
    """Simple rate limiting"""
    now = time.time()
    
    if client_ip not in request_counts:
        request_counts[client_ip] = []
    
    # Remove old requests
    request_counts[client_ip] = [
        req_time for req_time in request_counts[client_ip]
        if now - req_time < RATE_WINDOW
    ]
    
    # Check limit
    if len(request_counts[client_ip]) >= RATE_LIMIT:
        return False
    
    request_counts[client_ip].append(now)
    return True


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    client_ip = request.client.host
    
    if not check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."}
        )
    
    response = await call_next(request)
    return response


@app.get("/")
async def root():
    """API information"""
    return {
        "service": "Prior Authorization API Gateway",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "authentication": "/auth/token",
            "prior_auth": "/api/v1/prior-auth",
            "status": "/api/v1/status/{request_id}",
            "health": "/health"
        }
    }


@app.post("/auth/token")
async def authenticate(request: Request):
    """Proxy to auth service"""
    body = await request.json()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{AUTH_SERVICE}/token",
            data=body
        )
        return response.json()


@app.post("/api/v1/prior-auth")
async def submit_prior_auth(request: Request):
    """
    Submit prior authorization request
    Main endpoint for external clients
    """
    body = await request.json()
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing authentication")
    
    audit_logger.log_event(
        request_id=body.get("request_id", "unknown"),
        action="gateway_received",
        status="in_progress",
        details={
            "request_type": body.get("request_type"),
            "payer": body.get("payer")
        }
    )
    
    # Forward to validation agent
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{VALIDATION_SERVICE}/validate",
            json=body,
            headers={"Authorization": auth_header},
            timeout=60.0
        )
        
        if response.status_code == 200:
            audit_logger.log_event(
                request_id=body.get("request_id", "unknown"),
                action="gateway_forwarded",
                status="success"
            )
        else:
            audit_logger.log_event(
                request_id=body.get("request_id", "unknown"),
                action="gateway_error",
                status="error",
                details={"status_code": response.status_code}
            )
        
        return response.json()


@app.get("/api/v1/status/{request_id}")
async def get_status(request_id: str):
    """Get status of prior authorization request"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{MONITORING_SERVICE}/status/{request_id}",
            timeout=10.0
        )
        return response.json()


@app.get("/health")
async def health():
    """
    Health check for the entire system
    """
    health_status = {
        "gateway": "healthy",
        "services": {}
    }
    
    services = {
        "auth": AUTH_SERVICE,
        "validation": VALIDATION_SERVICE,
        "monitoring": MONITORING_SERVICE
    }
    
    async with httpx.AsyncClient() as client:
        for name, url in services.items():
            try:
                response = await client.get(f"{url}/health", timeout=2)
                health_status["services"][name] = "healthy" if response.status_code == 200 else "unhealthy"
            except:
                health_status["services"][name] = "unavailable"
    
    # Overall status
    all_healthy = all(status == "healthy" for status in health_status["services"].values())
    health_status["overall"] = "healthy" if all_healthy else "degraded"
    
    return health_status


@app.get("/metrics")
async def metrics():
    """
    Prometheus-compatible metrics endpoint
    """
    # In production, use prometheus_client library
    return {
        "requests_total": sum(len(reqs) for reqs in request_counts.values()),
        "active_clients": len(request_counts),
        "rate_limit": RATE_LIMIT,
        "timestamp": time.time()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
