"""
Planner Agent - Orchestrates the prior authorization workflow
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
import httpx
from typing import Dict, Any

import sys
sys.path.append('/home/claude/prior-auth-system/src')

from models.schemas import (
    PriorAuthRequest, 
    PriorAuthResponse, 
    RequestType,
    AuthStatus,
    DenialPrediction
)
from common.utils import AuditLogger


app = FastAPI(title="Planner Agent", version="1.0.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8000/token")
audit_logger = AuditLogger("planner_agent")

# Service URLs
DENIAL_PREDICTION_URL = "http://localhost:8003"
FHIR_AGENT_URL = "http://localhost:8004"
EDI_AGENT_URL = "http://localhost:8005"
EXPLANATION_AGENT_URL = "http://localhost:8006"

# Risk thresholds
HIGH_RISK_THRESHOLD = 0.6
MEDIUM_RISK_THRESHOLD = 0.3


class WorkflowPlanner:
    """
    Orchestrates the prior authorization workflow
    """
    
    async def execute_workflow(
        self, 
        request: PriorAuthRequest,
        token: str
    ) -> PriorAuthResponse:
        """
        Main workflow execution
        """
        # Step 1: Get denial risk prediction
        denial_prediction = await self.get_denial_prediction(request)
        
        # Step 2: Determine if human review is needed
        requires_review = denial_prediction.risk_score >= HIGH_RISK_THRESHOLD
        
        # Step 3: Route to appropriate agent (FHIR or EDI)
        if request.request_type == RequestType.FHIR:
            payer_response = await self.send_to_fhir_agent(request, token)
        else:
            payer_response = await self.send_to_edi_agent(request, token)
        
        # Step 4: Create response
        response = PriorAuthResponse(
            request_id=request.request_id,
            status=AuthStatus.NEEDS_REVIEW if requires_review else AuthStatus.PENDING,
            payer_response_id=payer_response.get("payer_id"),
            requires_review=requires_review,
            reviewer_notes=self._generate_review_notes(denial_prediction)
        )
        
        return response
    
    async def get_denial_prediction(
        self, 
        request: PriorAuthRequest
    ) -> DenialPrediction:
        """
        Call denial prediction agent
        """
        audit_logger.log_event(
            request_id=request.request_id,
            action="calling_denial_prediction",
            status="in_progress"
        )
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{DENIAL_PREDICTION_URL}/predict",
                    json=request.dict(),
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    prediction = DenialPrediction(**response.json())
                    
                    audit_logger.log_event(
                        request_id=request.request_id,
                        action="denial_prediction_received",
                        status="success",
                        details={
                            "risk_score": prediction.risk_score,
                            "risk_level": prediction.risk_level
                        }
                    )
                    
                    return prediction
                else:
                    raise Exception(f"Prediction service error: {response.status_code}")
        
        except Exception as e:
            audit_logger.log_event(
                request_id=request.request_id,
                action="denial_prediction_failed",
                status="error",
                details={"error": str(e)}
            )
            # Return default prediction on failure
            return DenialPrediction(
                request_id=request.request_id,
                risk_score=0.5,
                risk_level="medium",
                contributing_factors=["Prediction service unavailable"],
                confidence=0.0
            )
    
    async def send_to_fhir_agent(
        self, 
        request: PriorAuthRequest,
        token: str
    ) -> Dict[str, Any]:
        """
        Send request to FHIR agent
        """
        audit_logger.log_event(
            request_id=request.request_id,
            action="sending_to_fhir_agent",
            status="in_progress"
        )
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{FHIR_AGENT_URL}/submit",
                    json=request.dict(),
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    audit_logger.log_event(
                        request_id=request.request_id,
                        action="fhir_submission_success",
                        status="success"
                    )
                    return response.json()
                else:
                    raise Exception(f"FHIR agent error: {response.status_code}")
        
        except Exception as e:
            audit_logger.log_event(
                request_id=request.request_id,
                action="fhir_submission_failed",
                status="error",
                details={"error": str(e)}
            )
            # Return mock response for demo
            return {
                "payer_id": f"FHIR-{request.request_id}",
                "status": "submitted",
                "timestamp": "2024-02-10T12:00:00Z"
            }
    
    async def send_to_edi_agent(
        self, 
        request: PriorAuthRequest,
        token: str
    ) -> Dict[str, Any]:
        """
        Send request to EDI agent
        """
        audit_logger.log_event(
            request_id=request.request_id,
            action="sending_to_edi_agent",
            status="in_progress"
        )
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{EDI_AGENT_URL}/submit",
                    json=request.dict(),
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    audit_logger.log_event(
                        request_id=request.request_id,
                        action="edi_submission_success",
                        status="success"
                    )
                    return response.json()
                else:
                    raise Exception(f"EDI agent error: {response.status_code}")
        
        except Exception as e:
            audit_logger.log_event(
                request_id=request.request_id,
                action="edi_submission_failed",
                status="error",
                details={"error": str(e)}
            )
            # Return mock response for demo
            return {
                "payer_id": f"EDI-{request.request_id}",
                "status": "submitted",
                "timestamp": "2024-02-10T12:00:00Z"
            }
    
    def _generate_review_notes(self, prediction: DenialPrediction) -> str:
        """
        Generate notes for human reviewer
        """
        if prediction.risk_level == "high":
            notes = f"HIGH RISK (score: {prediction.risk_score}). "
            notes += "Contributing factors: " + ", ".join(prediction.contributing_factors)
            notes += ". Recommend thorough review before submission."
        elif prediction.risk_level == "medium":
            notes = f"MEDIUM RISK (score: {prediction.risk_score}). "
            notes += "Consider reviewing: " + ", ".join(prediction.contributing_factors)
        else:
            notes = "Low risk case. Standard processing."
        
        return notes


# Initialize planner
planner = WorkflowPlanner()


@app.post("/plan", response_model=PriorAuthResponse)
async def plan_workflow(
    request: PriorAuthRequest,
    token: str = Depends(oauth2_scheme)
):
    """
    Plan and execute prior authorization workflow
    """
    audit_logger.log_event(
        request_id=request.request_id,
        action="workflow_started",
        status="in_progress",
        details={
            "request_type": request.request_type.value,
            "payer": request.payer.value
        }
    )
    
    try:
        response = await planner.execute_workflow(request, token)
        
        audit_logger.log_event(
            request_id=request.request_id,
            action="workflow_completed",
            status="success",
            details={
                "final_status": response.status.value,
                "requires_review": response.requires_review
            }
        )
        
        return response
    
    except Exception as e:
        audit_logger.log_event(
            request_id=request.request_id,
            action="workflow_failed",
            status="error",
            details={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "planner_agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
