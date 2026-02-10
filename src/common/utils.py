"""
Common utilities for all agents
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

# Security configuration
SECRET_KEY = "your-secret-key-change-in-production"  # Should come from vault
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_logger(name: str) -> logging.Logger:
    """
    Get a PHI-safe logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def hash_phi(data: str) -> str:
    """
    Hash PHI for logging purposes (one-way hash)
    """
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def sanitize_for_logging(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove or hash PHI fields before logging
    """
    sensitive_fields = [
        'first_name', 'last_name', 'date_of_birth', 
        'member_id', 'ssn', 'phone', 'email', 'address'
    ]
    
    sanitized = data.copy()
    for field in sensitive_fields:
        if field in sanitized:
            sanitized[field] = hash_phi(str(sanitized[field]))
    
    return sanitized


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create JWT access token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode JWT token
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password
    """
    return pwd_context.hash(password)


class AuditLogger:
    """
    HIPAA-compliant audit logger
    """
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = get_logger(f"audit.{agent_name}")
    
    def log_event(
        self,
        request_id: str,
        action: str,
        status: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log an audit event with PHI safety
        """
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": self.agent_name,
            "request_id": request_id,
            "action": action,
            "status": status,
            "user_id": user_id,
            "details": sanitize_for_logging(details or {})
        }
        
        self.logger.info(json.dumps(audit_entry))
        
        # In production, also write to database
        # await self.write_to_audit_db(audit_entry)
    
    async def write_to_audit_db(self, audit_entry: Dict[str, Any]):
        """
        Write audit entry to database (stub)
        """
        # TODO: Implement database write
        pass
