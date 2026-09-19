import os
import logging
import uvicorn
from fastapi import FastAPI
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.helpers import new_text_message, new_task_from_user_message, get_message_text
from a2a.types import (
    AgentCard, 
    AgentCapabilities, 
    AgentInterface,
    AgentSkill,
    Part,
    Task,
    TaskState,
    TaskStatus,
)
from a2a.utils import TransportProtocol
from agent.agent import Agent
from agent.thread import Thread
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from experiments.A2A.mcp_server import webgent, task_manager, recon
from experiments.A2A.skill import RECON_CONTEXT
from agent.mcp_config import MCPClient
from dotenv import load_dotenv

load_dotenv()

HOST = "localhost"
PORT = 8003
URL = f"http://{HOST}:{PORT}/"

RPC_URL = "/"

llm = ChatOpenAI(
    base_url= os.getenv("BASE_URL"),
    api_key=os.getenv("API_KEY"),
    model=os.getenv("LLM"),
)

system = """
You are a ReAct agent. Complete the user-provided recon task, at the end after completion of the task return with a full findings report.
Just do as much told to, Not to do full recon unless specified.

You will be provided `WEBGENT SERVER SKILL` and `TASK MANAGER SERVER SKILL` for your references to how you can optimally use tools respectively.
You will also be provided an `RECON SKILL` to how to specifically do full recon.

=====================
WEBGENT SERVER SKILL
=====================

{webgent}

=====================
TASK MANAGER SERVER SKILL
=====================

{task_manager}

=====================
RECON SKILL
=====================

{recon}
"""

class MyExecutor(AgentExecutor):

    def __init__(self):
        self.servers = [webgent, task_manager, recon]
        self.client = MCPClient(self.servers)
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:

        self.agent = Agent(
            model = llm,
            tools = await self.client.get_tools()
        )


        user_text = get_message_text(context.message)

        task = context.current_task or new_task_from_user_message(context.message)

        await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        await updater.update_status(
            TaskState.TASK_STATE_WORKING,
            message = updater.new_agent_message([Part(text="Working on the task.")])
        )

        try:
            webgent_skill = (await self.client.get_prompt(
                "webgent",
                "agent_system_prompt"
            ))[0].content

            task_manager_skill = (await self.client.get_prompt(
                "task_manager",
                "agent_system_prompt"
            ))[0].content

            thread = Thread()
            SystemMessage(
                system.format(
                    webgent = webgent_skill,
                    task_manager = task_manager_skill,
                    recon = RECON_CONTEXT
                )
            ) | thread

            HumanMessage(user_text) | thread

            response = self.agent.invoke(thread)
            response_text = response.content
            
            await updater.update_status(
                TaskState.TASK_STATE_COMPLETED,
                message = updater.new_agent_message([Part(text=response_text)])
            )
            
        except Exception as e:
            await updater.update_status(
                TaskState.TASK_STATE_FAILED,
                message = updater.new_agent_message([Part(text=str(e))])
            )
            

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass

skill = AgentSkill(
    id="Web Recon",
    name="Web Recon",
    description="Agent is capabale to do a full recon on the provided target or any specific target or multi targets",
    tags=[
        "recon",
        "browsing-capability",
        "task-rought-note-management-capability",
        "nmap_scan",
        "gobuster_scan",
        "dirb_scan",
        "nikto_scan",
        "metasploit_run",
        "hydra_attack",
        "john_crack",
        "wpscan_analyze",
        "enum4linux_scan",
    ],
    examples=[
        "Do a full recon on scanme.nmap.org",
        "Look for any critical findings on https://ginandjuice.shop/vulnerabilities"
    ],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

agent_card = AgentCard(
    name = "Web Recon",
    description = "Agent is capabale to do a full recon on the provided target or any specific target or multi targets",
    version = "0.1.0",
    supported_interfaces = [
        AgentInterface(
            url = URL,
            protocol_binding = TransportProtocol.JSONRPC
        )
    ],
    capabilities = AgentCapabilities(streaming = False, push_notifications = False),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=[skill],
)

task_store = InMemoryTaskStore()

agent_executor = MyExecutor()

request_handler = DefaultRequestHandler(
    agent_executor = agent_executor,
    task_store = task_store,
    agent_card = agent_card,
)

app = FastAPI()

for route in create_agent_card_routes(agent_card = agent_card):
    app.router.routes.append(route)
for route in create_jsonrpc_routes(request_handler = request_handler, rpc_url = RPC_URL):
    app.router.routes.append(route)

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)