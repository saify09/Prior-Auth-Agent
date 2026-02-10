"""
OAuth2/JWT Authentication Service
"""
from datetime import timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

import sys
sys.path.append('/home/claude/prior-auth-system/src')

from common.utils import (
    create_access_token,
    verify_password,
    get_password_hash,
    verify_token,
    AuditLogger
)
from models.schemas import User, AuthToken


app = FastAPI(title="Auth Service", version="1.0.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
audit_logger = AuditLogger("auth_service")


# Mock user database (in production, use actual database)
fake_users_db = {
    "admin": {
        "username": "admin",
        "full_name": "System Admin",
        "email": "admin@hospital.com",
        "hashed_password": get_password_hash("admin123"),
        "disabled": False,
        "scopes": ["read", "write", "admin"]
    },
    "clinician": {
        "username": "clinician",
        "full_name": "Dr. Smith",
        "email": "smith@hospital.com",
        "hashed_password": get_password_hash("clinician123"),
        "disabled": False,
        "scopes": ["read", "write"]
    },
    "reviewer": {
        "username": "reviewer",
        "full_name": "Reviewer Jones",
        "email": "jones@hospital.com",
        "hashed_password": get_password_hash("reviewer123"),
        "disabled": False,
        "scopes": ["read", "review"]
    }
}


def get_user(username: str) -> Optional[User]:
    """Get user from database"""
    if username in fake_users_db:
        user_dict = fake_users_db[username]
        return User(**user_dict)
    return None


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate user credentials"""
    user = get_user(username)
    if not user:
        return None
    
    user_dict = fake_users_db[username]
    if not verify_password(password, user_dict["hashed_password"]):
        return None
    
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Get current user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    
    user = get_user(username)
    if user is None:
        raise credentials_exception
    
    return user


@app.post("/token", response_model=AuthToken)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 token endpoint
    """
    user = authenticate_user(form_data.username, form_data.password)
    
    if not user:
        audit_logger.log_event(
            request_id="auth-attempt",
            action="login_failed",
            status="failure",
            user_id=form_data.username
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": user.scopes},
        expires_delta=access_token_expires
    )
    
    audit_logger.log_event(
        request_id="auth-success",
        action="login_success",
        status="success",
        user_id=user.username
    )
    
    return AuthToken(
        access_token=access_token,
        token_type="bearer",
        expires_in=1800,
        scope=user.scopes
    )


@app.get("/verify")
async def verify(current_user: User = Depends(get_current_user)):
    """
    Verify token validity
    """
    return {
        "username": current_user.username,
        "scopes": current_user.scopes,
        "valid": True
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "auth"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
