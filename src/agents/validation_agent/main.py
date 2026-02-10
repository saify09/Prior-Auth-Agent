"""
Validation Agent - Validates incoming requests and authentication
"""
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Any
import httpx

import sys
sys.path.append('/home/claude/prior-auth-system/src')

from models.schemas import PriorAuthRequest, RequestType, PayerType
from common.utils import verify_token, AuditLogger, sanitize_for_logging


app = FastAPI(title="Validation Agent", version="1.0.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8000/token")
audit_logger = AuditLogger("validation_agent")

AUTH_SERVICE_URL = "http://localhost:8000"
PLANNER_SERVICE_URL = "http://localhost:8002"


async def validate_token(token: str) -> Dict[str, Any]:
    """Validate token with auth service"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{AUTH_SERVICE_URL}/verify",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Auth service unavailable: {str(e)}"
            )


def validate_fhir_request(request: PriorAuthRequest) -> Dict[str, Any]:
    """
    Validate FHIR prior auth request structure
    """
    errors = []
    
    # Validate patient info
    if not request.patient.member_id:
        errors.append("Missing patient member_id")
    
    if not request.patient.date_of_birth:
        errors.append("Missing patient date_of_birth")
    
    # Validate provider
    if not request.provider.npi or len(request.provider.npi) != 10:
        errors.append("Invalid or missing provider NPI")
    
    # Validate service request
    if not request.service_request.procedure_code:
        errors.append("Missing procedure code")
    
    if not request.service_request.diagnosis_codes:
        errors.append("Missing diagnosis codes")
    
    if errors:
        return {"valid": False, "errors": errors}
    
    return {"valid": True, "errors": []}


def validate_edi_request(request: PriorAuthRequest) -> Dict[str, Any]:
    """
    Validate EDI X12 278 request structure
    """
    errors = []
    
    # EDI-specific validation
    if not request.patient.id:
        errors.append("Missing patient ID for EDI")
    
    # Validate required EDI fields
    if not request.service_request.place_of_service:
        errors.append("Missing place of service code")
    
    if errors:
        return {"valid": False, "errors": errors}
    
    return {"valid": True, "errors": []}


@app.post("/validate")
async def validate_request(
    request: PriorAuthRequest,
    token: str = Depends(oauth2_scheme)
):
    """
    Main validation endpoint
    Validates authentication and request structure
    """
    # Log request (PHI-safe)
    audit_logger.log_event(
        request_id=request.request_id,
        action="validation_started",
        status="in_progress",
        details=sanitize_for_logging(request.dict())
    )
    
    # Validate token
    try:
        user_info = await validate_token(token)
        
        # Check required scopes
        if "write" not in user_info.get("scopes", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
    except HTTPException:
        audit_logger.log_event(
            request_id=request.request_id,
            action="validation_failed",
            status="auth_failure"
        )
        raise
    
    # Validate request structure based on type
    if request.request_type == RequestType.FHIR:
        validation_result = validate_fhir_request(request)
    elif request.request_type == RequestType.EDI:
        validation_result = validate_edi_request(request)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request type"
        )
    
    if not validation_result["valid"]:
        audit_logger.log_event(
            request_id=request.request_id,
            action="validation_failed",
            status="schema_errors",
            details={"errors": validation_result["errors"]}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": validation_result["errors"]}
        )
    
    # Forward to planner agent
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PLANNER_SERVICE_URL}/plan",
                json=request.dict(),
                headers={"Authorization": f"Bearer {token}"},
                timeout=30.0
            )
            
            audit_logger.log_event(
                request_id=request.request_id,
                action="validation_success",
                status="forwarded_to_planner",
                user_id=user_info.get("username")
            )
            
            return response.json()
    except Exception as e:
        audit_logger.log_event(
            request_id=request.request_id,
            action="forwarding_failed",
            status="error",
            details={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Planner service unavailable: {str(e)}"
        )


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "validation_agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
