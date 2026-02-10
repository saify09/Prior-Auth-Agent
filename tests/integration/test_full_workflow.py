"""
Integration test for the Prior Authorization System
Tests the complete workflow from request to response
"""
import requests
import json
import time
from typing import Dict, Any


class PriorAuthTester:
    """
    End-to-end integration tester
    """
    
    def __init__(self, base_url="http://localhost"):
        self.base_url = base_url
        self.token = None
    
    def authenticate(self) -> str:
        """
        Get authentication token
        """
        print("\n=== Step 1: Authentication ===")
        
        response = requests.post(
            f"{self.base_url}:8000/token",
            data={
                "username": "clinician",
                "password": "clinician123"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            self.token = data["access_token"]
            print(f"✓ Authentication successful")
            print(f"  Token: {self.token[:20]}...")
            print(f"  Scopes: {data['scope']}")
            return self.token
        else:
            print(f"✗ Authentication failed: {response.status_code}")
            print(f"  Response: {response.text}")
            raise Exception("Authentication failed")
    
    def create_fhir_request(self) -> Dict[str, Any]:
        """
        Create a sample FHIR prior auth request
        """
        return {
            "request_type": "fhir",
            "payer": "UnitedHealthcare",
            "patient": {
                "id": "P12345",
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": "1975-05-15",
                "gender": "Male",
                "member_id": "UHC123456789"
            },
            "provider": {
                "npi": "1234567890",
                "name": "Dr. Sarah Smith",
                "organization": "City Medical Center",
                "tax_id": "987654321"
            },
            "service_request": {
                "procedure_code": "27447",
                "procedure_description": "Total knee arthroplasty",
                "diagnosis_codes": ["M17.11", "M25.561"],
                "quantity": 1,
                "place_of_service": "21",
                "service_date": "2024-03-15"
            },
            "supporting_docs": [
                "clinical_notes_20240210.pdf",
                "xray_results_20240201.pdf"
            ]
        }
    
    def create_edi_request(self) -> Dict[str, Any]:
        """
        Create a sample EDI prior auth request
        """
        request = self.create_fhir_request()
        request["request_type"] = "edi"
        request["payer"] = "Cigna"
        return request
    
    def submit_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit prior auth request
        """
        print(f"\n=== Step 2: Submit {request['request_type'].upper()} Request ===")
        print(f"  Payer: {request['payer']}")
        print(f"  Procedure: {request['service_request']['procedure_code']}")
        print(f"  Patient: {request['patient']['first_name']} {request['patient']['last_name']}")
        
        response = requests.post(
            f"{self.base_url}:8001/validate",
            json=request,
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Request submitted successfully")
            print(f"  Request ID: {data.get('request_id')}")
            print(f"  Status: {data.get('status')}")
            print(f"  Requires Review: {data.get('requires_review')}")
            
            if data.get('reviewer_notes'):
                print(f"  Notes: {data.get('reviewer_notes')[:100]}...")
            
            return data
        else:
            print(f"✗ Request failed: {response.status_code}")
            print(f"  Response: {response.text}")
            raise Exception("Request submission failed")
    
    def check_health(self):
        """
        Check health of all services
        """
        print("\n=== Health Check ===")
        
        services = {
            "Auth Service": 8000,
            "Validation Agent": 8001,
            "Planner Agent": 8002,
            "Denial Prediction Agent": 8003,
            "FHIR Agent": 8004,
            "EDI Agent": 8005,
            "Explanation Agent": 8006,
            "Monitoring Agent": 8007
        }
        
        for name, port in services.items():
            try:
                response = requests.get(f"{self.base_url}:{port}/health", timeout=2)
                if response.status_code == 200:
                    print(f"✓ {name:25} - Healthy")
                else:
                    print(f"✗ {name:25} - Unhealthy ({response.status_code})")
            except Exception as e:
                print(f"✗ {name:25} - Unavailable")
    
    def test_denial_prediction(self):
        """
        Test denial prediction directly
        """
        print("\n=== Testing Denial Prediction ===")
        
        request = self.create_fhir_request()
        
        response = requests.post(
            f"{self.base_url}:8003/predict",
            json=request
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Prediction successful")
            print(f"  Risk Score: {data['risk_score']:.2%}")
            print(f"  Risk Level: {data['risk_level'].upper()}")
            print(f"  Confidence: {data['confidence']:.2%}")
            print(f"  Factors:")
            for factor in data['contributing_factors']:
                print(f"    - {factor}")
            return data
        else:
            print(f"✗ Prediction failed: {response.status_code}")
    
    def run_full_test(self):
        """
        Run complete end-to-end test
        """
        print("="*70)
        print(" HIPAA-Compliant Prior Authorization System - Integration Test")
        print("="*70)
        
        try:
            # Health check
            self.check_health()
            
            # Authenticate
            self.authenticate()
            
            # Test denial prediction
            self.test_denial_prediction()
            
            # Test FHIR request
            fhir_request = self.create_fhir_request()
            fhir_response = self.submit_request(fhir_request)
            
            # Test EDI request
            edi_request = self.create_edi_request()
            edi_response = self.submit_request(edi_request)
            
            print("\n" + "="*70)
            print(" ✓ All tests passed successfully!")
            print("="*70)
            
            return True
        
        except Exception as e:
            print("\n" + "="*70)
            print(f" ✗ Test failed: {str(e)}")
            print("="*70)
            return False


if __name__ == "__main__":
    tester = PriorAuthTester()
    success = tester.run_full_test()
    exit(0 if success else 1)
