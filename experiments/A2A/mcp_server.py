from agent.mcp_config import AddServer

webgent = AddServer(
    name = "webgent",
    transport = "http",
    url = "http://0.0.0.0:3333/mcp"
)

task_manager = AddServer(
    name = "task_manager",
    transport = "http",
    url = "http://0.0.0.0:8000/mcp"
)

recon = AddServer(
    name = "recon",
    transport = "stdio",
    command = "uv",
    args = [
        "run",
        "--directory",
        "/home/butcher/projects/recon-mcp",
        "client.py",
        "--server",
        "http://127.0.0.1:5000"
    ]
)