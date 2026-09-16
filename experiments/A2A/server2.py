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
from dotenv import load_dotenv

load_dotenv()

HOST = "localhost"
PORT = 8002
URL = f"http://{HOST}:{PORT}/"

RPC_URL = "/"

llm = ChatOpenAI(
    base_url= os.getenv("BASE_URL"),
    api_key=os.getenv("API_KEY"),
    model=os.getenv("LLM"),
)

system = SystemMessage("""
You are specialized in CyberSecurity Domain for any query related to cybersecurity you have to respond in a well in-depth report. For other related queries or general queries respond with message - I can't answer your query. Please ask Cybersecurity related query.
""")

class MyExecutor(AgentExecutor):

    def __init__(self):
        self.agent = Agent(
            model = llm
        )
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:

        user_text = get_message_text(context.message)
        
        task = context.current_task or new_task_from_user_message(context.message)
        # user_text = context.get_user_input()

        await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        await updater.update_status(
            TaskState.TASK_STATE_WORKING,
            message = updater.new_agent_message([Part(text="Working on the task.")])
        )

        try:
            thread = Thread()
            system | thread
            HumanMessage(user_text) | thread
            response = self.agent.invoke(thread)
            response_text = response.content
            # response_message = new_text_message(response_text)
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

cybersecurity_skill = AgentSkill(
    id="cybersecurity_analysis",
    name="Cybersecurity Analysis",
    description=(
        "Analyzes and answers cybersecurity-related questions, including "
        "vulnerability assessment, penetration testing, security concepts, "
        "threat analysis, and security best practices."
    ),
    tags=[
        "cybersecurity",
        "vulnerability-assessment",
        "penetration-testing",
        "security-analysis",
        "threat-analysis",
    ],
    examples=[
        "Explain SQL injection and how to prevent it",
        "Analyze this web application vulnerability",
        "How does SSRF work?",
        "Explain CVE impact and mitigation",
    ],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

agent_card = AgentCard(
    name = "CyberSecurity Agent",
    description = "It will answer to any cybersecurity related query",
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
    skills=[cybersecurity_skill],
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