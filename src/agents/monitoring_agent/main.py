"""
Monitoring Agent - Tracks prior authorization status and polls payer systems
"""
from fastapi import FastAPI, BackgroundTasks
from typing import Dict, List
import asyncio
from datetime import datetime
import httpx

import sys
sys.path.append('/home/claude/prior-auth-system/src')

from models.schemas import AuthStatus
from common.utils import AuditLogger


app = FastAPI(title="Monitoring Agent", version="1.0.0")
audit_logger = AuditLogger("monitoring_agent")

# In-memory tracking (in production, use database)
tracked_requests: Dict[str, Dict] = {}

FHIR_AGENT_URL = "http://localhost:8004"


class StatusMonitor:
    """
    Monitor and track prior authorization requests
    """
    
    def __init__(self):
        self.polling_interval = 300  # 5 minutes
        self.max_polls = 288  # 24 hours worth of 5-min polls
    
    async def track_request(
        self, 
        request_id: str,
        payer_id: str,
        request_type: str
    ):
        """
        Start tracking a prior auth request
        """
        tracked_requests[request_id] = {
            "request_id": request_id,
            "payer_id": payer_id,
            "request_type": request_type,
            "status": AuthStatus.PENDING.value,
            "poll_count": 0,
            "started_at": datetime.utcnow().isoformat(),
            "last_checked": None,
            "last_status": None
        }
        
        audit_logger.log_event(
            request_id=request_id,
            action="tracking_started",
            status="success",
            details={"payer_id": payer_id, "type": request_type}
        )
    
    async def poll_status(self, request_id: str) -> Dict:
        """
        Poll payer for status update
        """
        if request_id not in tracked_requests:
            return {"error": "Request not being tracked"}
        
        tracking_info = tracked_requests[request_id]
        
        # Simulate polling (in production, call actual payer API)
        if tracking_info["request_type"] == "fhir":
            status_update = await self._poll_fhir_status(request_id)
        else:
            status_update = await self._poll_edi_status(request_id)
        
        # Update tracking info
        tracking_info["poll_count"] += 1
        tracking_info["last_checked"] = datetime.utcnow().isoformat()
        tracking_info["last_status"] = status_update["status"]
        tracking_info["status"] = status_update["status"]
        
        audit_logger.log_event(
            request_id=request_id,
            action="status_polled",
            status="success",
            details={
                "poll_count": tracking_info["poll_count"],
                "current_status": status_update["status"]
            }
        )
        
        return status_update
    
    async def _poll_fhir_status(self, request_id: str) -> Dict:
        """
        Poll FHIR endpoint for status
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{FHIR_AGENT_URL}/status/{request_id}",
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            audit_logger.log_event(
                request_id=request_id,
                action="fhir_poll_failed",
                status="error",
                details={"error": str(e)}
            )
        
        # Return default pending status on error
        return {
            "request_id": request_id,
            "status": "pending",
            "last_updated": datetime.utcnow().isoformat()
        }
    
    async def _poll_edi_status(self, request_id: str) -> Dict:
        """
        Poll EDI/AS2 for 277 response
        """
        # In production, check for 277 response file or database
        # For demo, simulate status
        tracking_info = tracked_requests[request_id]
        
        # Simulate approval after 3 polls
        if tracking_info["poll_count"] >= 3:
            return {
                "request_id": request_id,
                "status": "approved",
                "auth_number": f"AUTH{request_id[-6:]}",
                "last_updated": datetime.utcnow().isoformat()
            }
        
        return {
            "request_id": request_id,
            "status": "pending",
            "last_updated": datetime.utcnow().isoformat()
        }
    
    async def auto_poll_all(self):
        """
        Background task to auto-poll all tracked requests
        """
        while True:
            for request_id in list(tracked_requests.keys()):
                tracking_info = tracked_requests[request_id]
                
                # Stop polling after max attempts or if final status reached
                if tracking_info["poll_count"] >= self.max_polls:
                    continue
                
                if tracking_info["status"] in ["approved", "denied"]:
                    continue
                
                await self.poll_status(request_id)
            
            # Wait before next poll cycle
            await asyncio.sleep(self.polling_interval)


# Initialize monitor
monitor = StatusMonitor()


@app.post("/track")
async def start_tracking(
    request_id: str,
    payer_id: str,
    request_type: str,
    background_tasks: BackgroundTasks
):
    """
    Start tracking a prior authorization request
    """
    await monitor.track_request(request_id, payer_id, request_type)
    return {
        "message": "Tracking started",
        "request_id": request_id,
        "polling_interval_seconds": monitor.polling_interval
    }


@app.get("/status/{request_id}")
async def get_status(request_id: str):
    """
    Get current status of tracked request
    """
    if request_id not in tracked_requests:
        return {"error": "Request not being tracked"}
    
    # Poll for latest status
    status_update = await monitor.poll_status(request_id)
    
    return {
        **tracked_requests[request_id],
        "latest_update": status_update
    }


@app.get("/list")
async def list_tracked():
    """
    List all tracked requests
    """
    return {
        "total_tracked": len(tracked_requests),
        "requests": list(tracked_requests.values())
    }


@app.delete("/stop/{request_id}")
async def stop_tracking(request_id: str):
    """
    Stop tracking a request
    """
    if request_id in tracked_requests:
        del tracked_requests[request_id]
        
        audit_logger.log_event(
            request_id=request_id,
            action="tracking_stopped",
            status="success"
        )
        
        return {"message": "Tracking stopped"}
    
    return {"error": "Request not being tracked"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "monitoring_agent",
        "tracked_requests": len(tracked_requests)
    }


@app.on_event("startup")
async def startup_event():
    """
    Start background polling on startup
    """
    # In production, uncomment to enable background polling
    # asyncio.create_task(monitor.auto_poll_all())
    pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
