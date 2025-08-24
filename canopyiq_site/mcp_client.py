"""
MCP API Client - Proxy for calling internal MCP server endpoints
Enhanced with OpenTelemetry tracing support
"""
import httpx
import os
import json
from typing import Dict, Any, Optional
from fastapi import HTTPException
from opentelemetry import trace

class MCPClient:
    def __init__(self):
        self.base_url = os.getenv("MCP_BASE_URL", "http://localhost:8080")
        self.bearer_token = os.getenv("CONSOLE_BEARER")
        self.timeout = 10.0
        self.tracer = trace.get_tracer("canopyiq.console")
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for MCP API requests"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "CanopyIQ-Console/1.0"
        }
        
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
            
        return headers
    
    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle HTTP response and raise appropriate exceptions"""
        if response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"status": "ok", "data": response.text}
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="MCP endpoint not found")
        elif response.status_code == 401:
            raise HTTPException(status_code=401, detail="MCP authentication required")
        elif response.status_code == 403:
            raise HTTPException(status_code=403, detail="MCP access forbidden")
        else:
            try:
                error_data = response.json()
                detail = error_data.get("detail", f"MCP API error: {response.status_code}")
            except:
                detail = f"MCP API error: {response.status_code}"
            raise HTTPException(status_code=response.status_code, detail=detail)
    
    def list_approvals(self, tenant: str = "", status: str = "pending", limit: int = 50) -> Dict[str, Any]:
        """Get list of approvals from MCP server"""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                params = {}
                if tenant:
                    params["tenant"] = tenant
                if status:
                    params["status"] = status
                if limit:
                    params["limit"] = str(limit)
                
                response = client.get(
                    f"{self.base_url}/v1/approvals",
                    params=params,
                    headers=self._get_headers()
                )
                return self._handle_response(response)
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"MCP server unavailable: {str(e)}")
    
    def get_approval(self, approval_id: str) -> Dict[str, Any]:
        """Get specific approval by ID"""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.base_url}/v1/approvals/{approval_id}",
                    headers=self._get_headers()
                )
                return self._handle_response(response)
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"MCP server unavailable: {str(e)}")
    
    def simulate_policy(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate a policy decision"""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/v1/policy/simulate",
                    json=body,
                    headers=self._get_headers()
                )
                return self._handle_response(response)
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"MCP server unavailable: {str(e)}")
    
    def diff_policy(self, current_file: Optional[bytes], proposed_file: bytes) -> Dict[str, Any]:
        """Diff policies using multipart upload"""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                files = {}
                
                if current_file:
                    files["current"] = ("current.yaml", current_file, "application/x-yaml")
                
                files["proposed"] = ("proposed.yaml", proposed_file, "application/x-yaml")
                
                # Remove Content-Type for multipart
                headers = self._get_headers()
                headers.pop("Content-Type", None)
                
                response = client.post(
                    f"{self.base_url}/v1/policy/diff",
                    files=files,
                    headers=headers
                )
                return self._handle_response(response)
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"MCP server unavailable: {str(e)}")
    
    def policy_status(self) -> Dict[str, Any]:
        """Get current policy status - tolerate 404"""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.base_url}/v1/policy/status",
                    headers=self._get_headers()
                )
                
                if response.status_code == 404:
                    return {"status": "not_available", "message": "Policy status endpoint not found"}
                
                return self._handle_response(response)
        except httpx.RequestError as e:
            return {"status": "error", "message": f"MCP server unavailable: {str(e)}"}

# Global instance
mcp_client = MCPClient()