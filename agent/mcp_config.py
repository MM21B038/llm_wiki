from pydantic import BaseModel
from typing import List, Union, Optional, Dict, Literal, Callable, Any
from langchain_mcp_adapters.client import MultiServerMCPClient

class AddServer:
    def __init__(
        self,
        name: str,
        transport: Literal["stdio", "http"] = "http",
        url: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, Any]] = None
    ):
        
        self.name = name
        self.transport = transport
        self.url = url
        self.command = command
        self.args = args
        self.env = env

    def dump_json(self):
        config = {}
        config["transport"] = self.transport
        if self.env is not None:
            config["env"] = self.env
        
        match self.transport:
            case "http":
                config["url"] = self.url
            case "stdio":
                config["command"] = self.command
                config["args"] = self.args

        return config  

class DuplicateValueError(BaseModel):
    error: str

class MCPClient:
    
    def __init__(
        self,
        servers: List[AddServer]
    ):
        self.servers = servers
        self.names = [server.name for server in servers]
        self.client = None

    def connect(self):
        servers = {}
        for server in self.servers:
            if server.name in servers:
                raise DuplicateValueError(f"server name {server.name} found twice")
            servers[server.name] = server.dump_json()

        self.client = MultiServerMCPClient(servers)

    def append(self, server: Server):
        if server.name in self.names:
            return DuplicateValueError(error=f"server with name {server.name} already there")
        self.server.append(server)
        return True

    def _ensure_connected(self):
        if self.client is None:
            self.connect()

    async def get_tools(self):
        self._ensure_connected()

        return await self.client.get_tools()

    async def list_prompts(self, server_name: str):
        self._ensure_connected()

        async with self.client.session(server_name) as session:
            result = await session.list_prompts()

        return result

    async def list_resources(self, server_name: str):
        self._ensure_connected()

        async with self.client.session(server_name) as session:
            result = await session.list_resources()

        return result

    async def get_prompt(
        self,
        server_name: str,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ):
        self._ensure_connected()

        return await self.client.get_prompt(
            server_name=server_name,
            prompt_name=prompt_name,
            arguments=arguments
        )

    async def get_resources(
        self,
        server_name: Optional[str] = None,
        uris: Optional[Union[str, List[str]]] = None
    ):
        self._ensure_connected()

        return await self.client.get_resources(
            server_name=server_name,
            uris=uris
        )