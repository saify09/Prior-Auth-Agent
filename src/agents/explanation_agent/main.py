"""
Explanation Agent - Provides explanations for decisions and predictions
"""
from fastapi import FastAPI
from typing import List, Dict, Any

import sys
sys.path.append('/home/claude/prior-auth-system/src')

from models.schemas import DenialPrediction, PriorAuthResponse
from common.utils import AuditLogger


app = FastAPI(title="Explanation Agent", version="1.0.0")
audit_logger = AuditLogger("explanation_agent")


class ExplanationGenerator:
    """
    Generate human-readable explanations for AI decisions
    """
    
    def explain_denial_prediction(
        self, 
        prediction: DenialPrediction
    ) -> Dict[str, Any]:
        """
        Explain denial risk prediction
        """
        explanation = {
            "request_id": prediction.request_id,
            "risk_assessment": self._format_risk_level(prediction),
            "key_factors": self._explain_factors(prediction.contributing_factors),
            "recommendations": self._get_recommendations(prediction),
            "confidence_note": self._explain_confidence(prediction.confidence)
        }
        
        return explanation
    
    def _format_risk_level(self, prediction: DenialPrediction) -> str:
        """Format risk level with context"""
        if prediction.risk_level == "high":
            return (
                f"HIGH RISK ({prediction.risk_score:.1%}): "
                "This request has a significant likelihood of denial. "
                "We strongly recommend human review and additional documentation."
            )
        elif prediction.risk_level == "medium":
            return (
                f"MEDIUM RISK ({prediction.risk_score:.1%}): "
                "This request may face denial. "
                "Consider reviewing the contributing factors and strengthening documentation."
            )
        else:
            return (
                f"LOW RISK ({prediction.risk_score:.1%}): "
                "This request has a good probability of approval with current documentation."
            )
    
    def _explain_factors(self, factors: List[str]) -> List[Dict[str, str]]:
        """Provide detailed explanations for each factor"""
        explanations = []
        
        factor_details = {
            "Missing supporting documentation": {
                "impact": "High",
                "explanation": "Payers require clinical notes, test results, or medical necessity documentation to approve requests.",
                "action": "Attach relevant medical records, test results, and clinical notes that justify the procedure."
            },
            "High-complexity procedure": {
                "impact": "Medium",
                "explanation": "Complex procedures typically require more scrutiny and detailed justification.",
                "action": "Include detailed procedure notes and explanation of medical necessity."
            },
            "Multiple diagnosis codes": {
                "impact": "Low",
                "explanation": "Multiple diagnoses may indicate complexity but can also raise questions about primary diagnosis.",
                "action": "Ensure primary diagnosis is clearly indicated and all codes are relevant to the procedure."
            },
            "Provider has elevated denial history": {
                "impact": "Medium",
                "explanation": "Historical denial patterns may influence payer review process.",
                "action": "Ensure all documentation requirements are met and consider peer review."
            }
        }
        
        for factor in factors:
            detail = factor_details.get(
                factor, 
                {
                    "impact": "Unknown",
                    "explanation": factor,
                    "action": "Review request details carefully."
                }
            )
            
            explanations.append({
                "factor": factor,
                **detail
            })
        
        return explanations
    
    def _get_recommendations(self, prediction: DenialPrediction) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if prediction.risk_score >= 0.6:
            recommendations.append("CRITICAL: Route to human reviewer before submission")
            recommendations.append("Gather all supporting clinical documentation")
        
        if "documentation" in str(prediction.contributing_factors).lower():
            recommendations.append("Add comprehensive clinical notes")
            recommendations.append("Include relevant test results and imaging reports")
        
        if "procedure" in str(prediction.contributing_factors).lower():
            recommendations.append("Provide detailed medical necessity statement")
            recommendations.append("Include alternative treatments considered")
        
        if prediction.risk_score < 0.3:
            recommendations.append("Request appears well-documented and ready for submission")
        
        return recommendations
    
    def _explain_confidence(self, confidence: float) -> str:
        """Explain prediction confidence level"""
        if confidence >= 0.8:
            return f"High confidence ({confidence:.1%}) - Prediction based on strong historical patterns."
        elif confidence >= 0.6:
            return f"Moderate confidence ({confidence:.1%}) - Prediction based on available data with some uncertainty."
        else:
            return f"Low confidence ({confidence:.1%}) - Limited data available for this scenario."
    
    def explain_workflow_decision(
        self, 
        response: PriorAuthResponse
    ) -> Dict[str, Any]:
        """
        Explain why a particular workflow path was chosen
        """
        explanation = {
            "request_id": response.request_id,
            "decision": response.status.value,
            "reason": self._explain_status(response),
            "next_steps": self._get_next_steps(response)
        }
        
        return explanation
    
    def _explain_status(self, response: PriorAuthResponse) -> str:
        """Explain the status decision"""
        if response.requires_review:
            return (
                "This request has been flagged for human review due to high denial risk. "
                f"Review notes: {response.reviewer_notes}"
            )
        elif response.status.value == "pending":
            return "Request submitted to payer and awaiting response."
        elif response.status.value == "approved":
            return f"Request approved by payer. Authorization number: {response.approval_number}"
        elif response.status.value == "denied":
            return f"Request denied by payer. Reason: {response.denial_reason}"
        else:
            return f"Request status: {response.status.value}"
    
    def _get_next_steps(self, response: PriorAuthResponse) -> List[str]:
        """Get next steps based on response status"""
        if response.requires_review:
            return [
                "Clinician to review denial risk factors",
                "Add additional documentation if needed",
                "Approve or modify request before final submission"
            ]
        elif response.status.value == "pending":
            return [
                "Monitor for payer response",
                "Typical response time: 2-5 business days",
                "Receive notification upon payer decision"
            ]
        elif response.status.value == "denied":
            return [
                "Review denial reason",
                "Gather additional documentation",
                "Consider appeal process",
                "Consult with clinical team"
            ]
        else:
            return ["No action required at this time"]


# Initialize explanation generator
explainer = ExplanationGenerator()


@app.post("/explain/prediction")
async def explain_prediction(prediction: DenialPrediction):
    """
    Get explanation for denial prediction
    """
    audit_logger.log_event(
        request_id=prediction.request_id,
        action="explanation_requested",
        status="success",
        details={"type": "prediction"}
    )
    
    return explainer.explain_denial_prediction(prediction)


@app.post("/explain/workflow")
async def explain_workflow(response: PriorAuthResponse):
    """
    Get explanation for workflow decision
    """
    audit_logger.log_event(
        request_id=response.request_id,
        action="explanation_requested",
        status="success",
        details={"type": "workflow"}
    )
    
    return explainer.explain_workflow_decision(response)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "explanation_agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
