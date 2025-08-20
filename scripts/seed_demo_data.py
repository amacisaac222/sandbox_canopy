#!/usr/bin/env python3
"""
Seed demo data for Agent Sandbox
"""
import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8080"

def create_tenant_and_agent():
    """Create demo tenant and agent"""
    print("Creating demo tenant...")
    
    # Create tenant
    tenant_resp = requests.post(f"{BASE_URL}/v1/tenants", json={
        "name": "acme_corp"
    })
    
    if tenant_resp.status_code != 200:
        print(f"Failed to create tenant: {tenant_resp.text}")
        return None
    
    tenant = tenant_resp.json()
    tenant_id = tenant["id"]
    print(f"Created tenant: {tenant}")
    
    # Create agent
    agent_resp = requests.post(f"{BASE_URL}/v1/tenants/{tenant_id}/agents", json={
        "agent_id": "sales_assistant",
        "api_key": "DEV-AGENT-KEY-123"
    })
    
    if agent_resp.status_code != 200:
        print(f"Failed to create agent: {agent_resp.text}")
        return None
    
    agent = agent_resp.json()
    print(f"Created agent: {agent}")
    
    return tenant_id, agent["agent_id"]

def upload_policy():
    """Upload demo policy"""
    print("Uploading sales agent policy...")
    
    policy_path = Path("policies/examples/sales_agent.yaml")
    if not policy_path.exists():
        print(f"Policy file not found: {policy_path}")
        return False
    
    with open(policy_path, 'rb') as f:
        policy_resp = requests.put(
            f"{BASE_URL}/v1/policies/sales_assistant",
            headers={
                "Content-Type": "application/x-yaml",
                "X-Agent-Key": "DEV-AGENT-KEY-123"
            },
            data=f.read()
        )
    
    if policy_resp.status_code != 200:
        print(f"Failed to upload policy: {policy_resp.text}")
        return False
    
    policy = policy_resp.json()
    print(f"Uploaded policy: {policy}")
    return True

def main():
    """Seed demo data"""
    print("=== Agent Sandbox Demo Data Seeder ===\n")
    
    try:
        # Check if control plane is running
        health_resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if health_resp.status_code != 200:
            print("Control plane is not running or not healthy")
            return 1
        
        # Create tenant and agent
        result = create_tenant_and_agent()
        if not result:
            return 1
        
        # Upload policy
        if not upload_policy():
            return 1
        
        print("\n[SUCCESS] Demo data seeded successfully!")
        print(f"Control plane: {BASE_URL}")
        print(f"Approvals UI: {BASE_URL}/approvals")
        print(f"Run demo: python demos/demo_agent.py")
        
        return 0
        
    except requests.ConnectionError:
        print("[ERROR] Could not connect to control plane. Is it running?")
        print("   Start it with: ./scripts/run_control_plane.sh")
        return 1
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())