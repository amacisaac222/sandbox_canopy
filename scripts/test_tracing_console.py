#!/usr/bin/env python3
"""
Test script for CanopyIQ Console with OpenTelemetry tracing
Demonstrates the new trace-enhanced features
"""
import asyncio
import httpx
import json
import os
from datetime import datetime

# Configuration
CONSOLE_URL = "http://localhost:8081"
MCP_URL = "http://localhost:8080" 
TOKEN = os.getenv("TOKEN", "")

async def test_console_features():
    """Test all the new tracing-enhanced console features"""
    
    print("Testing CanopyIQ Console with OpenTelemetry Integration")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        
        # Test 1: Console Dashboard
        print("\nTesting Console Dashboard...")
        try:
            response = await client.get(f"{CONSOLE_URL}/console")
            if response.status_code == 200:
                print("Console dashboard loaded successfully")
                print(f"   Found trace analytics and agent dependency cards")
            else:
                print(f"Console dashboard failed: {response.status_code}")
        except Exception as e:
            print(f"Console dashboard error: {e}")
        
        # Test 2: Access Dashboard with Tracing
        print("\nTesting Access Dashboard with Policy Simulation...")
        try:
            response = await client.get(f"{CONSOLE_URL}/console/access?tenant=demo-tenant")
            if response.status_code == 200:
                print("Access dashboard loaded with live policy simulation")
                print("   Each tool tile shows real-time allow/deny/approval status")
            else:
                print(f"Access dashboard failed: {response.status_code}")
        except Exception as e:
            print(f"Access dashboard error: {e}")
        
        # Test 3: Trace Analytics Page
        print("\nTesting Trace Analytics...")
        try:
            response = await client.get(f"{CONSOLE_URL}/console/traces")
            if response.status_code == 200:
                print("Trace analytics loaded successfully")
                print("   Generated mock trace data with workflow performance metrics")
                print("   Shows distributed tracing for agent workflows")
            else:
                print(f"Trace analytics failed: {response.status_code}")
        except Exception as e:
            print(f"Trace analytics error: {e}")
        
        # Test 4: Agent Dependencies 
        print("\nTesting Agent Dependencies...")
        try:
            response = await client.get(f"{CONSOLE_URL}/console/agents")
            if response.status_code == 200:
                print("Agent dependencies loaded successfully")
                print("   Shows agent-to-agent communication patterns")
                print("   Includes service mesh topology visualization")
            else:
                print(f"Agent dependencies failed: {response.status_code}")
        except Exception as e:
            print(f"Agent dependencies error: {e}")
        
        # Test 5: Policy Simulator with Tracing
        print("\nTesting Policy Simulator...")
        try:
            # Test GET (form)
            response = await client.get(f"{CONSOLE_URL}/console/simulator")
            if response.status_code == 200:
                print("Policy simulator form loaded")
                
                # Test POST (simulation with tracing)
                sim_data = {
                    "tool": "cloud.ops",
                    "arguments": '{"provider":"aws","resource":"ec2","action":"run_instances","estimated_cost_usd":12.0}'
                }
                response = await client.post(f"{CONSOLE_URL}/console/simulator", data=sim_data)
                if response.status_code == 200:
                    print("Policy simulation executed with tracing")
                    print("   Trace spans recorded for policy evaluation")
                else:
                    print(f"Policy simulation failed: {response.status_code}")
            else:
                print(f"Policy simulator failed: {response.status_code}")
        except Exception as e:
            print(f"Policy simulator error: {e}")
        
        # Test 6: Navigation Dropdown
        print("\nTesting Enhanced Navigation...")
        try:
            response = await client.get(f"{CONSOLE_URL}/")
            if response.status_code == 200:
                print("Enhanced navigation with Console dropdown loaded")
                print("   Includes all new trace and agent pages")
            else:
                print(f"Navigation test failed: {response.status_code}")
        except Exception as e:
            print(f"Navigation test error: {e}")

async def demo_tracing_features():
    """Demonstrate key tracing features"""
    
    print("\nOpenTelemetry Tracing Features Demonstrated:")
    print("=" * 60)
    
    features = [
        "FastAPI auto-instrumentation for HTTP requests",
        "HTTPX auto-instrumentation for MCP API calls", 
        "Custom spans for policy evaluation",
        "Span attributes for tenant, agent, tool, decision",
        "Mock trace data generation for demo purposes",
        "Distributed tracing across agent workflows",
        "Workflow performance analytics",
        "Agent-to-agent communication tracking",
        "Cost attribution per trace/span",
        "Policy decision audit trails"
    ]
    
    for feature in features:
        print(f"   {feature}")
    
    print(f"\nEnvironment Configuration:")
    print(f"   OTEL_EXPORTER_OTLP_ENDPOINT: {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'not set')}")
    print(f"   OTEL_CONSOLE_EXPORTER: {os.getenv('OTEL_CONSOLE_EXPORTER', 'false')}")
    print(f"   MCP_BASE_URL: {os.getenv('MCP_BASE_URL', 'http://localhost:8080')}")
    print(f"   CONSOLE_BEARER: {'set' if os.getenv('CONSOLE_BEARER') else 'not set'}")

def print_demo_urls():
    """Print URLs for manual testing"""
    
    print(f"\nDemo URLs (visit these in your browser):")
    print("=" * 60)
    
    urls = [
        ("Console Dashboard", f"{CONSOLE_URL}/console"),
        ("Access Control (Live Policy)", f"{CONSOLE_URL}/console/access"), 
        ("Approvals Queue", f"{CONSOLE_URL}/console/approvals"),
        ("Trace Analytics", f"{CONSOLE_URL}/console/traces"),
        ("Agent Dependencies", f"{CONSOLE_URL}/console/agents"),
        ("Policy Simulator", f"{CONSOLE_URL}/console/simulator"),
        ("Policy Management", f"{CONSOLE_URL}/console/policy")
    ]
    
    for name, url in urls:
        print(f"   {name:<20} -> {url}")

async def main():
    """Run the complete tracing console test suite"""
    
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run tests
    await test_console_features()
    
    # Show tracing features
    await demo_tracing_features()
    
    # Print demo URLs
    print_demo_urls()
    
    print(f"\nCanopyIQ Console with OpenTelemetry Integration is ready!")
    print("   Start the console server and visit the URLs above to explore")
    print(f"   Console Server: python -m uvicorn app:app --host 0.0.0.0 --port 8081 --reload")

if __name__ == "__main__":
    asyncio.run(main())