from fastmcp import FastMCP
from pathlib import Path
import subprocess

mcp = FastMCP("MyServer")

@mcp.tool
def execute_command(command: str) -> str:
    result = subprocess.run(
    command,
    shell=True,
    capture_output=True,
    text=True,
    timeout=30,
    )

    return result.stdout

@mcp.tool
def read_file(path: str) -> str:
    file = Path(path)
    
    if not file.exists():
        return f"File does not exists: {path}"
    
    return file.read_text(encoding="utf-8")


if __name__ == "__main__":
    print("🚀 MyServer MCP starting...")
    mcp.run(transport="http")
