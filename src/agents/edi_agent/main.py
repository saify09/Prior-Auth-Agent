"""
EDI Agent - Handles X12 EDI 278 transactions for prior authorization
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime
from typing import Dict, Any

import sys
sys.path.append('/home/claude/prior-auth-system/src')

from models.schemas import PriorAuthRequest, PayerType
from common.utils import AuditLogger


app = FastAPI(title="EDI Agent", version="1.0.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8000/token")
audit_logger = AuditLogger("edi_agent")


# Payer EDI endpoints (AS2/VAN connections in production)
PAYER_EDI_ENDPOINTS = {
    PayerType.UHC: "uhc-edi-gateway.example.com",
    PayerType.CIGNA: "cigna-edi-gateway.example.com",
    PayerType.AETNA: "aetna-edi-gateway.example.com"
}


class EDITranslator:
    """
    X12 EDI 278 (Health Care Services Review) translator
    HIPAA 5010 standard
    """
    
    def build_278_request(self, request: PriorAuthRequest) -> str:
        """
        Build X12 278 EDI message for prior authorization request
        """
        # ISA - Interchange Control Header
        isa = self._build_isa_segment()
        
        # GS - Functional Group Header
        gs = self._build_gs_segment()
        
        # ST - Transaction Set Header (278)
        st = "ST*278*0001*005010X217~"
        
        # BHT - Beginning of Hierarchical Transaction
        bht = f"BHT*0007*13*{request.request_id}*{datetime.utcnow().strftime('%Y%m%d')}*{datetime.utcnow().strftime('%H%M')}~"
        
        # HL - Hierarchical Level (Requester)
        hl_requester = "HL*1**20*1~"
        
        # NM1 - Requester Name
        nm1_requester = f"NM1*X3*2*{request.provider.organization or 'HOSPITAL'}*****XX*{request.provider.tax_id or '123456789'}~"
        
        # HL - Hierarchical Level (Patient)
        hl_patient = "HL*2*1*22*0~"
        
        # NM1 - Patient Name
        nm1_patient = f"NM1*IL*1*{request.patient.last_name}*{request.patient.first_name}****MI*{request.patient.member_id}~"
        
        # DMG - Patient Demographics
        dmg = f"DMG*D8*{request.patient.date_of_birth.replace('-', '')}*{request.patient.gender[0].upper()}~"
        
        # UM - Service Request
        um = "UM*HS*I*******Y~"
        
        # HCR - Health Care Services Review Information
        hcr = "HCR*A1*R1*I~"
        
        # REF - Service Date
        ref = f"REF*D9*{request.service_request.service_date.replace('-', '')}~"
        
        # HI - Diagnosis Codes
        hi_segments = self._build_hi_segments(request.service_request.diagnosis_codes)
        
        # SV1 - Professional Service
        sv1 = f"SV1*HC:{request.service_request.procedure_code}*100*UN*{request.service_request.quantity}***{request.service_request.place_of_service}~"
        
        # SE - Transaction Set Trailer
        segment_count = 14 + len(hi_segments)  # Count all segments between ST and SE
        se = f"SE*{segment_count}*0001~"
        
        # GE - Functional Group Trailer
        ge = "GE*1*1~"
        
        # IEA - Interchange Control Trailer
        iea = "IEA*1*000000001~"
        
        # Combine all segments
        edi_message = "\n".join([
            isa, gs, st, bht,
            hl_requester, nm1_requester,
            hl_patient, nm1_patient, dmg,
            um, hcr, ref,
            *hi_segments,
            sv1,
            se, ge, iea
        ])
        
        return edi_message
    
    def _build_isa_segment(self) -> str:
        """Build ISA (Interchange Control Header)"""
        return (
            "ISA*00*          *00*          *ZZ*SENDER         "
            "*ZZ*RECEIVER       *"
            f"{datetime.utcnow().strftime('%y%m%d')}*"
            f"{datetime.utcnow().strftime('%H%M')}*"
            "^*00501*000000001*0*P*:~"
        )
    
    def _build_gs_segment(self) -> str:
        """Build GS (Functional Group Header)"""
        return (
            f"GS*HS*SENDER*RECEIVER*{datetime.utcnow().strftime('%Y%m%d')}*"
            f"{datetime.utcnow().strftime('%H%M')}*1*X*005010X217~"
        )
    
    def _build_hi_segments(self, diagnosis_codes: list) -> list:
        """Build HI (Health Care Diagnosis Code) segments"""
        hi_segments = []
        
        # Primary diagnosis
        if diagnosis_codes:
            primary = f"HI*ABK:{diagnosis_codes[0]}"
            
            # Additional diagnoses (up to 11 more)
            for code in diagnosis_codes[1:12]:
                primary += f"*ABF:{code}"
            
            primary += "~"
            hi_segments.append(primary)
        
        return hi_segments
    
    def parse_278_response(self, edi_response: str) -> Dict[str, Any]:
        """
        Parse X12 278 response from payer
        """
        # In production, implement full EDI parser
        # For demo, return mock parsed response
        return {
            "control_number": "0001",
            "status": "A1",  # Approved
            "auth_number": f"AUTH{datetime.utcnow().timestamp()}",
            "response_date": datetime.utcnow().isoformat()
        }


# Initialize EDI translator
edi_translator = EDITranslator()


@app.post("/submit")
async def submit_edi_request(
    request: PriorAuthRequest,
    token: str = Depends(oauth2_scheme)
):
    """
    Submit prior authorization via EDI X12 278
    """
    audit_logger.log_event(
        request_id=request.request_id,
        action="edi_submission_started",
        status="in_progress",
        details={"payer": request.payer.value}
    )
    
    try:
        # Build EDI 278 message
        edi_message = edi_translator.build_278_request(request)
        
        audit_logger.log_event(
            request_id=request.request_id,
            action="edi_message_created",
            status="success",
            details={
                "payer": request.payer.value,
                "message_length": len(edi_message)
            }
        )
        
        # In production, send via AS2 or VAN
        # For demo, we log the message and return mock response
        payer_endpoint = PAYER_EDI_ENDPOINTS.get(request.payer)
        
        audit_logger.log_event(
            request_id=request.request_id,
            action="edi_transmission",
            status="success",
            details={
                "endpoint": payer_endpoint,
                "transmission_id": f"EDI-{request.request_id}"
            }
        )
        
        # Mock response
        response = {
            "payer_id": f"EDI-{request.request_id}",
            "status": "submitted",
            "control_number": "000000001",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return response
    
    except Exception as e:
        audit_logger.log_event(
            request_id=request.request_id,
            action="edi_submission_failed",
            status="error",
            details={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse-response")
async def parse_response(edi_response: Dict[str, str]):
    """
    Parse EDI 278 response from payer
    """
    try:
        parsed = edi_translator.parse_278_response(edi_response.get("message", ""))
        return parsed
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/format-sample")
async def get_sample_format():
    """
    Return sample EDI 278 format for reference
    """
    sample_request = PriorAuthRequest(
        request_id="SAMPLE-001",
        request_type="edi",
        payer="UnitedHealthcare",
        patient={
            "id": "P001",
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1980-01-01",
            "gender": "Male",
            "member_id": "M123456789"
        },
        provider={
            "npi": "1234567890",
            "name": "Dr. Smith",
            "organization": "City Hospital"
        },
        service_request={
            "procedure_code": "99213",
            "procedure_description": "Office visit",
            "diagnosis_codes": ["M54.5"],
            "quantity": 1,
            "place_of_service": "11",
            "service_date": "2024-03-01"
        }
    )
    
    return {
        "sample_278": edi_translator.build_278_request(sample_request)
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "edi_agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
