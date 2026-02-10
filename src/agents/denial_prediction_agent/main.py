"""
Denial Prediction Agent - ML-based risk scoring for prior auth requests
"""
from fastapi import FastAPI, HTTPException
import numpy as np
from typing import List
import joblib
import os

import sys
sys.path.append('/home/claude/prior-auth-system/src')

from models.schemas import PriorAuthRequest, DenialPrediction, PayerType
from common.utils import AuditLogger


app = FastAPI(title="Denial Prediction Agent", version="1.0.0")
audit_logger = AuditLogger("denial_prediction_agent")


class DenialPredictor:
    """
    Machine Learning model for predicting denial risk
    Uses rule-based logic as baseline (can be replaced with trained ML model)
    """
    
    # High-risk procedure codes (examples)
    HIGH_RISK_PROCEDURES = {
        "99203", "99204", "99205",  # High-level office visits
        "27447",  # Total knee arthroplasty
        "43644",  # Laparoscopic gastric bypass
        "72148",  # MRI lumbar spine
    }
    
    # Payer-specific denial rates (historical data)
    PAYER_DENIAL_RATES = {
        PayerType.UHC: 0.15,
        PayerType.CIGNA: 0.18,
        PayerType.AETNA: 0.12,
    }
    
    def predict(self, request: PriorAuthRequest) -> DenialPrediction:
        """
        Predict denial risk for a prior auth request
        Returns risk score (0-1) and contributing factors
        """
        risk_factors = []
        risk_score = 0.0
        
        # Factor 1: Base payer risk
        base_risk = self.PAYER_DENIAL_RATES.get(request.payer, 0.15)
        risk_score += base_risk
        
        # Factor 2: Procedure complexity
        if request.service_request.procedure_code in self.HIGH_RISK_PROCEDURES:
            risk_score += 0.20
            risk_factors.append("High-complexity procedure")
        
        # Factor 3: Missing documentation
        if not request.supporting_docs or len(request.supporting_docs) == 0:
            risk_score += 0.25
            risk_factors.append("Missing supporting documentation")
        
        # Factor 4: Multiple diagnosis codes (complexity)
        if len(request.service_request.diagnosis_codes) > 3:
            risk_score += 0.10
            risk_factors.append("Multiple diagnosis codes")
        
        # Factor 5: Provider history (simplified - in production, check database)
        # For demo, randomly flag some providers
        if hash(request.provider.npi) % 5 == 0:
            risk_score += 0.15
            risk_factors.append("Provider has elevated denial history")
        
        # Cap risk score at 1.0
        risk_score = min(risk_score, 1.0)
        
        # Determine risk level
        if risk_score < 0.3:
            risk_level = "low"
        elif risk_score < 0.6:
            risk_level = "medium"
        else:
            risk_level = "high"
        
        # Calculate confidence (simplified)
        confidence = 0.75 + (0.15 * len(risk_factors) / 5)
        confidence = min(confidence, 0.95)
        
        return DenialPrediction(
            request_id=request.request_id,
            risk_score=round(risk_score, 3),
            risk_level=risk_level,
            contributing_factors=risk_factors if risk_factors else ["No significant risk factors"],
            confidence=round(confidence, 3)
        )
    
    def get_recommendations(self, prediction: DenialPrediction) -> List[str]:
        """
        Get recommendations to reduce denial risk
        """
        recommendations = []
        
        for factor in prediction.contributing_factors:
            if "documentation" in factor.lower():
                recommendations.append("Add clinical notes and medical necessity documentation")
            elif "procedure" in factor.lower():
                recommendations.append("Include detailed procedure justification")
            elif "diagnosis" in factor.lower():
                recommendations.append("Prioritize primary diagnosis code")
            elif "provider" in factor.lower():
                recommendations.append("Review provider credentialing and prior submissions")
        
        if prediction.risk_level == "high":
            recommendations.append("Consider human review before submission")
        
        return recommendations


# Initialize predictor
predictor = DenialPredictor()


@app.post("/predict", response_model=DenialPrediction)
async def predict_denial_risk(request: PriorAuthRequest):
    """
    Predict denial risk for prior authorization request
    """
    audit_logger.log_event(
        request_id=request.request_id,
        action="prediction_started",
        status="in_progress"
    )
    
    try:
        # Run prediction
        prediction = predictor.predict(request)
        
        audit_logger.log_event(
            request_id=request.request_id,
            action="prediction_completed",
            status="success",
            details={
                "risk_score": prediction.risk_score,
                "risk_level": prediction.risk_level,
                "num_factors": len(prediction.contributing_factors)
            }
        )
        
        return prediction
    
    except Exception as e:
        audit_logger.log_event(
            request_id=request.request_id,
            action="prediction_failed",
            status="error",
            details={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommendations")
async def get_recommendations(prediction: DenialPrediction):
    """
    Get recommendations to reduce denial risk
    """
    recommendations = predictor.get_recommendations(prediction)
    return {"recommendations": recommendations}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "denial_prediction_agent"}


@app.get("/metrics")
async def metrics():
    """
    Return model metrics (for monitoring)
    """
    return {
        "model_version": "1.0.0",
        "model_type": "rule_based",
        "features": [
            "payer_type",
            "procedure_code",
            "documentation_count",
            "diagnosis_complexity",
            "provider_history"
        ],
        "high_risk_threshold": 0.6,
        "medium_risk_threshold": 0.3
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
