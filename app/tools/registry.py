# Tool registry for CanopyIQ MCP
from . import cost_estimator, cloud_ops, fs_io

TOOLS = {
    "cloud.estimate": {
        "schema": cost_estimator.SCHEMA,
        "handler": cost_estimator.estimate
    },
    "cloud.ops": {
        "schema": cloud_ops.SCHEMA,
        "handler": cloud_ops.execute
    },
    "fs.write": {
        "schema": fs_io.SCHEMA,
        "handler": fs_io.write
    }
}

def list_tools():
    """Return list of available tools for MCP tools/list"""
    return [
        {
            "name": name,
            **tool["schema"]
        }
        for name, tool in TOOLS.items()
    ]

def get_handler(tool_name: str):
    """Get handler function for a tool"""
    if tool_name not in TOOLS:
        raise KeyError(f"Unknown tool: {tool_name}")
    return TOOLS[tool_name]["handler"]