"""
Common data models for the Prior Authorization System
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PayerType(str, Enum):
    """Supported payer types"""
    UHC = "UnitedHealthcare"
    CIGNA = "Cigna"
    AETNA = "Aetna"


class RequestType(str, Enum):
    """Type of prior auth request"""
    FHIR = "fhir"
    EDI = "edi"


class AuthStatus(str, Enum):
    """Prior authorization status"""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    NEEDS_REVIEW = "needs_review"
    IN_PROGRESS = "in_progress"


class Patient(BaseModel):
    """Patient information"""
    id: str
    first_name: str
    last_name: str
    date_of_birth: str
    gender: str
    member_id: str
    
    
class Provider(BaseModel):
    """Healthcare provider information"""
    npi: str
    name: str
    organization: Optional[str] = None
    tax_id: Optional[str] = None


class ServiceRequest(BaseModel):
    """Service being requested for authorization"""
    procedure_code: str
    procedure_description: str
    diagnosis_codes: List[str]
    quantity: int = 1
    place_of_service: str
    service_date: str


class PriorAuthRequest(BaseModel):
    """Main prior authorization request"""
    request_id: str = Field(default_factory=lambda: f"PA-{datetime.utcnow().timestamp()}")
    request_type: RequestType
    payer: PayerType
    patient: Patient
    provider: Provider
    service_request: ServiceRequest
    supporting_docs: Optional[List[str]] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    

class DenialPrediction(BaseModel):
    """Denial prediction result"""
    request_id: str
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: str  # low, medium, high
    contributing_factors: List[str]
    confidence: float


class PriorAuthResponse(BaseModel):
    """Prior authorization response"""
    request_id: str
    status: AuthStatus
    payer_response_id: Optional[str] = None
    approval_number: Optional[str] = None
    denial_reason: Optional[str] = None
    requires_review: bool = False
    reviewer_notes: Optional[str] = None
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    

class AuditLog(BaseModel):
    """Audit log entry"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: str
    agent: str
    action: str
    user_id: Optional[str] = None
    status: str
    details: Optional[Dict[str, Any]] = {}
    phi_safe: bool = True  # Ensures no PHI in logs
    

class AuthToken(BaseModel):
    """OAuth2 token"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    scope: List[str]
    

class User(BaseModel):
    """User for authentication"""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: bool = False
    scopes: List[str] = []
