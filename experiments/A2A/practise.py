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
from experiments.A2A.skill import SQL_INJECTION
from agent.mcp_config import MCPClient
from dotenv import load_dotenv


load_dotenv()

HOST = "localhost"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

llm = ChatOpenAI(
    model = os.getenv("LLM"),
    base = os.getenv("")
)

