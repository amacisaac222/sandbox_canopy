"""
OpenTelemetry instrumentation for CanopyIQ
Provides distributed tracing for agent workflows, policy decisions, and A2A communication
"""
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.trace import Status, StatusCode
import random
import json

# Configure logging
logger = logging.getLogger(__name__)

class CanopyTracing:
    """CanopyIQ OpenTelemetry integration"""
    
    def __init__(self):
        self.tracer = None
        self.meter = None
        self.initialized = False
        
    def init_tracing(self, app=None):
        """Initialize OpenTelemetry tracing and instrumentation"""
        if self.initialized:
            return
            
        # Configure trace provider
        provider = TracerProvider()
        
        # Add exporters
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
        
        if otlp_endpoint and otlp_endpoint != "disabled":
            try:
                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(f"OTLP tracing enabled: {otlp_endpoint}")
            except Exception as e:
                logger.warning(f"Failed to initialize OTLP exporter: {e}")
        
        # Development console exporter
        if os.getenv("OTEL_CONSOLE_EXPORTER", "false").lower() == "true":
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            
        trace.set_tracer_provider(provider)
        self.tracer = trace.get_tracer("canopyiq")
        
        # Initialize metrics
        metrics.set_meter_provider(MeterProvider())
        self.meter = metrics.get_meter("canopyiq")
        
        # Auto-instrument frameworks
        if app:
            FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()
        SQLAlchemyInstrumentor().instrument()
        
        self.initialized = True
        logger.info("CanopyIQ tracing initialized")
    
    def trace_policy_evaluation(self, tenant: str, agent_id: str, tool: str, decision: str, **attributes):
        """Create span for policy evaluation"""
        if not self.tracer:
            return None
            
        span = self.tracer.start_span("canopy.policy.evaluate")
        span.set_attributes({
            "canopy.tenant": tenant,
            "canopy.agent_id": agent_id, 
            "canopy.tool": tool,
            "canopy.decision": decision,
            **{k: str(v) for k, v in attributes.items()}
        })
        
        if decision == "deny":
            span.set_status(Status(StatusCode.ERROR, "Policy denied"))
        elif decision == "approval":
            span.add_event("approval_required")
            
        return span
    
    def trace_approval_workflow(self, approval_id: str, action: str, approver: str = None):
        """Create span for approval workflow"""
        if not self.tracer:
            return None
            
        span = self.tracer.start_span("canopy.approval.workflow")
        span.set_attributes({
            "canopy.approval.id": approval_id,
            "canopy.approval.action": action,
        })
        
        if approver:
            span.set_attribute("canopy.approval.approver", approver)
            
        return span
    
    def trace_a2a_call(self, caller_agent: str, target_agent: str, capability: str, **attributes):
        """Create span for agent-to-agent communication"""
        if not self.tracer:
            return None
            
        span = self.tracer.start_span("canopy.a2a.call")
        span.set_attributes({
            "canopy.caller.agent": caller_agent,
            "canopy.target.agent": target_agent, 
            "canopy.capability": capability,
            **{k: str(v) for k, v in attributes.items()}
        })
        
        return span
    
    def trace_budget_check(self, tenant: str, budget_name: str, remaining: float, requested: float):
        """Create span for budget evaluation"""
        if not self.tracer:
            return None
            
        span = self.tracer.start_span("canopy.budget.check")
        span.set_attributes({
            "canopy.tenant": tenant,
            "canopy.budget.name": budget_name,
            "canopy.budget.remaining_usd": remaining,
            "canopy.budget.requested_usd": requested,
            "canopy.budget.would_exceed": remaining < requested
        })
        
        if remaining < requested:
            span.add_event("budget_exceeded", {
                "shortfall_usd": requested - remaining,
                "suggested_action": "request_approval"
            })
            
        return span

# Global instance
canopy_tracing = CanopyTracing()

# Mock trace data generator for demo purposes
class MockTraceData:
    """Generate realistic trace data for demo/development"""
    
    AGENTS = [
        "marketing-bot", "finance-bot", "hr-bot", "sales-bot", 
        "legal-bot", "operations-bot", "security-bot", "data-bot"
    ]
    
    TOOLS = [
        "net.http", "fs.read", "fs.write", "cloud.ops", "mail.send", 
        "database.query", "api.call", "document.process"
    ]
    
    DECISIONS = ["allow", "deny", "approval"]
    
    @staticmethod
    def generate_traces(count: int = 100) -> List[Dict[str, Any]]:
        """Generate mock trace data for visualization"""
        traces = []
        base_time = datetime.utcnow() - timedelta(hours=24)
        
        for i in range(count):
            trace_id = f"trace_{i:06d}_{random.randint(1000, 9999)}"
            timestamp = base_time + timedelta(minutes=random.randint(0, 1440))
            
            # Create realistic workflow scenarios
            workflow_type = random.choice([
                "quarterly-planning", "customer-onboarding", "incident-response",
                "compliance-audit", "data-analysis", "budget-approval"
            ])
            
            # Generate spans for the trace
            spans = MockTraceData._generate_workflow_spans(trace_id, workflow_type, timestamp)
            
            trace = {
                "trace_id": trace_id,
                "workflow_type": workflow_type,
                "start_time": timestamp.isoformat(),
                "duration_ms": sum(s["duration_ms"] for s in spans),
                "total_cost_usd": sum(s.get("cost_usd", 0) for s in spans),
                "status": "success" if all(s["status"] == "ok" for s in spans) else "error",
                "spans": spans,
                "agent_count": len(set(s["agent_id"] for s in spans if "agent_id" in s)),
                "approval_count": len([s for s in spans if s.get("decision") == "approval"])
            }
            
            traces.append(trace)
            
        return sorted(traces, key=lambda x: x["start_time"], reverse=True)
    
    @staticmethod
    def _generate_workflow_spans(trace_id: str, workflow_type: str, base_time: datetime) -> List[Dict[str, Any]]:
        """Generate realistic spans for a workflow"""
        spans = []
        current_time = base_time
        
        if workflow_type == "quarterly-planning":
            # Marketing → Finance → Sales → Approval workflow
            workflow_steps = [
                ("marketing-bot", "market.research", "net.http", 500, 2.50),
                ("finance-bot", "budget.analysis", "database.query", 300, 1.20), 
                ("sales-bot", "forecast.generate", "api.call", 800, 5.75),
                ("approval", "manager.review", None, 120000, 0.0)  # 2 min approval
            ]
        elif workflow_type == "customer-onboarding":
            workflow_steps = [
                ("sales-bot", "customer.validate", "api.call", 200, 0.50),
                ("legal-bot", "contract.review", "document.process", 2000, 8.90),
                ("finance-bot", "billing.setup", "database.query", 400, 1.80)
            ]
        else:
            # Generic workflow
            workflow_steps = [
                (random.choice(MockTraceData.AGENTS), "generic.task", 
                 random.choice(MockTraceData.TOOLS), 
                 random.randint(100, 1000), 
                 random.uniform(0.10, 5.0))
                for _ in range(random.randint(2, 5))
            ]
        
        for i, (agent, operation, tool, duration_ms, cost_usd) in enumerate(workflow_steps):
            span_start = current_time + timedelta(milliseconds=i * 50)  # Small gap between spans
            
            span = {
                "span_id": f"span_{trace_id}_{i:02d}",
                "operation_name": f"canopy.{operation}",
                "start_time": span_start.isoformat(),
                "duration_ms": duration_ms,
                "status": "ok" if random.random() > 0.1 else "error",
                "attributes": {
                    "canopy.tenant": "demo-tenant",
                    "canopy.workflow.type": workflow_type
                }
            }
            
            if agent != "approval":
                span["attributes"].update({
                    "canopy.agent_id": agent,
                    "canopy.tool": tool,
                    "canopy.decision": random.choice(["allow", "allow", "allow", "deny", "approval"]),  # Weighted
                })
                span["cost_usd"] = cost_usd
            else:
                span["attributes"].update({
                    "canopy.approval.required": True,
                    "canopy.approval.approver": "manager@company.com"
                })
                span["decision"] = "approval"
            
            spans.append(span)
            current_time = span_start + timedelta(milliseconds=duration_ms)
        
        return spans
    
    @staticmethod
    def generate_agent_dependency_map() -> Dict[str, Any]:
        """Generate mock agent dependency data"""
        agents = MockTraceData.AGENTS
        connections = []
        
        # Create realistic agent-to-agent communication patterns
        patterns = [
            ("marketing-bot", "finance-bot", "budget.inquiry", 45, 12, 2),
            ("marketing-bot", "data-bot", "analytics.request", 78, 5, 1),
            ("sales-bot", "finance-bot", "pricing.check", 123, 8, 0),
            ("sales-bot", "legal-bot", "contract.review", 34, 23, 8),
            ("hr-bot", "finance-bot", "payroll.query", 67, 2, 0),
            ("operations-bot", "security-bot", "access.request", 23, 18, 12),
            ("data-bot", "finance-bot", "report.generate", 89, 15, 3)
        ]
        
        for source, target, capability, success_count, approval_count, error_count in patterns:
            total_calls = success_count + approval_count + error_count
            avg_latency = random.randint(150, 800)
            
            connections.append({
                "source": source,
                "target": target, 
                "capability": capability,
                "total_calls": total_calls,
                "success_rate": round(success_count / total_calls * 100, 1),
                "approval_rate": round(approval_count / total_calls * 100, 1),
                "error_rate": round(error_count / total_calls * 100, 1),
                "avg_latency_ms": avg_latency,
                "total_cost_usd": round(total_calls * random.uniform(0.5, 3.0), 2)
            })
        
        # Generate agent metadata
        agent_metadata = {}
        for agent in agents:
            agent_metadata[agent] = {
                "total_calls": random.randint(50, 300),
                "success_rate": random.uniform(85, 99),
                "avg_latency_ms": random.randint(100, 600),
                "cost_per_call_usd": random.uniform(0.1, 2.0),
                "capabilities": random.sample([
                    "data.read", "data.write", "api.call", "document.process", 
                    "email.send", "budget.check", "approval.request"
                ], random.randint(2, 4))
            }
        
        return {
            "agents": agent_metadata,
            "connections": connections,
            "generated_at": datetime.utcnow().isoformat()
        }

# Export the global instance and mock data
__all__ = ["canopy_tracing", "MockTraceData"]