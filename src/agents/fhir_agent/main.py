"""
FHIR Agent - Handles FHIR R4 API integration with payers
Implements DaVinci PAS (Prior Authorization Support) IG
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime
from typing import Dict, Any
import httpx

import sys
sys.path.append('/home/claude/prior-auth-system/src')

from models.schemas import PriorAuthRequest, PayerType
from common.utils import AuditLogger


app = FastAPI(title="FHIR Agent", version="1.0.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8000/token")
audit_logger = AuditLogger("fhir_agent")


# Payer FHIR endpoints (in production, these would be real URLs)
PAYER_ENDPOINTS = {
    PayerType.UHC: "https://api.uhc.com/fhir/r4",
    PayerType.CIGNA: "https://api.cigna.com/fhir/r4",
    PayerType.AETNA: "https://api.aetna.com/fhir/r4"
}


class FHIRClient:
    """
    FHIR R4 client for prior authorization
    Implements DaVinci PAS IG
    """
    
    def build_claim_resource(self, request: PriorAuthRequest) -> Dict[str, Any]:
        """
        Build FHIR Claim resource for prior authorization
        Based on DaVinci PAS IG
        """
        claim = {
            "resourceType": "Claim",
            "id": request.request_id,
            "status": "active",
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                    "code": "professional"
                }]
            },
            "use": "preauthorization",
            "patient": {
                "reference": f"Patient/{request.patient.id}",
                "display": f"{request.patient.first_name} {request.patient.last_name}"
            },
            "created": datetime.utcnow().isoformat(),
            "insurer": {
                "display": request.payer.value
            },
            "provider": {
                "reference": f"Practitioner/{request.provider.npi}",
                "display": request.provider.name
            },
            "priority": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/processpriority",
                    "code": "normal"
                }]
            },
            "diagnosis": [
                {
                    "sequence": i + 1,
                    "diagnosisCodeableConcept": {
                        "coding": [{
                            "system": "http://hl7.org/fhir/sid/icd-10",
                            "code": code
                        }]
                    }
                }
                for i, code in enumerate(request.service_request.diagnosis_codes)
            ],
            "item": [{
                "sequence": 1,
                "productOrService": {
                    "coding": [{
                        "system": "http://www.ama-assn.org/go/cpt",
                        "code": request.service_request.procedure_code,
                        "display": request.service_request.procedure_description
                    }]
                },
                "servicedDate": request.service_request.service_date,
                "locationCodeableConcept": {
                    "coding": [{
                        "system": "https://www.cms.gov/Medicare/Coding/place-of-service-codes",
                        "code": request.service_request.place_of_service
                    }]
                },
                "quantity": {
                    "value": request.service_request.quantity
                }
            }]
        }
        
        return claim
    
    def build_patient_resource(self, request: PriorAuthRequest) -> Dict[str, Any]:
        """
        Build FHIR Patient resource
        """
        patient = {
            "resourceType": "Patient",
            "id": request.patient.id,
            "identifier": [{
                "system": "http://hospital.example.org/member-id",
                "value": request.patient.member_id
            }],
            "name": [{
                "family": request.patient.last_name,
                "given": [request.patient.first_name]
            }],
            "gender": request.patient.gender.lower(),
            "birthDate": request.patient.date_of_birth
        }
        
        return patient
    
    async def submit_to_payer(
        self, 
        request: PriorAuthRequest,
        token: str
    ) -> Dict[str, Any]:
        """
        Submit FHIR resources to payer endpoint
        """
        payer_url = PAYER_ENDPOINTS.get(request.payer)
        if not payer_url:
            raise ValueError(f"Unknown payer: {request.payer}")
        
        # Build FHIR bundle
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": self.build_patient_resource(request)
                },
                {
                    "resource": self.build_claim_resource(request)
                }
            ]
        }
        
        # In production, this would actually POST to payer API
        # For demo, we simulate the response
        audit_logger.log_event(
            request_id=request.request_id,
            action="fhir_bundle_created",
            status="success",
            details={
                "payer": request.payer.value,
                "endpoint": payer_url,
                "resource_count": len(bundle["entry"])
            }
        )
        
        # Simulate API call (in production, uncomment and use real endpoint)
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         f"{payer_url}/Claim",
        #         json=bundle,
        #         headers={
        #             "Authorization": f"Bearer {token}",
        #             "Content-Type": "application/fhir+json"
        #         },
        #         timeout=30.0
        #     )
        #     return response.json()
        
        # Mock response for demo
        return {
            "resourceType": "ClaimResponse",
            "id": f"CR-{request.request_id}",
            "status": "active",
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                    "code": "professional"
                }]
            },
            "use": "preauthorization",
            "patient": {
                "reference": f"Patient/{request.patient.id}"
            },
            "created": datetime.utcnow().isoformat(),
            "insurer": {
                "display": request.payer.value
            },
            "outcome": "queued",
            "preAuthRef": f"PA{datetime.utcnow().timestamp()}"
        }


# Initialize FHIR client
fhir_client = FHIRClient()


@app.post("/submit")
async def submit_fhir_request(
    request: PriorAuthRequest,
    token: str = Depends(oauth2_scheme)
):
    """
    Submit prior authorization via FHIR
    """
    audit_logger.log_event(
        request_id=request.request_id,
        action="fhir_submission_started",
        status="in_progress",
        details={"payer": request.payer.value}
    )
    
    try:
        response = await fhir_client.submit_to_payer(request, token)
        
        audit_logger.log_event(
            request_id=request.request_id,
            action="fhir_submission_completed",
            status="success",
            details={
                "payer_response_id": response.get("id"),
                "outcome": response.get("outcome")
            }
        )
        
        return {
            "payer_id": response.get("id"),
            "status": "submitted",
            "payer_reference": response.get("preAuthRef"),
            "outcome": response.get("outcome"),
            "timestamp": response.get("created")
        }
    
    except Exception as e:
        audit_logger.log_event(
            request_id=request.request_id,
            action="fhir_submission_failed",
            status="error",
            details={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{request_id}")
async def get_status(request_id: str):
    """
    Check FHIR authorization status (poll payer)
    """
    # In production, would query payer API
    # For demo, return mock status
    return {
        "request_id": request_id,
        "status": "pending",
        "last_updated": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "fhir_agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
