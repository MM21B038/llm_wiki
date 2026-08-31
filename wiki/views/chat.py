from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from agent.agent import Agent
from agent.thread import Thread
from wiki.services.mongo_client import insert_thread, get_messages, get_collection
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from rest_framework.response import Response
from agent.thread_rules import AutoToolHideRule, ThreadHideRule
from wiki.services.prompts import chat_compression_prompt, chat_system_prompt
from wiki.tools import chat_tools
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
load_dotenv()

llm = ChatOpenAI(
    base_url=os.getenv("BASE_URL"),
    api_key=os.getenv("API_KEY"),
    model=os.getenv("LLM"),
)
agent = Agent(
    model=llm,
    tools=chat_tools,
)

def prepare_thread(messages, workspace_id: int):
    thread = Thread(
        compression_prompt=chat_compression_prompt,
        token_limit=96000,
        tool_hide_rules=[
            ThreadHideRule(
                name="read_wiki_page",
                message="[earlier read_wiki_page result collapsed — see latest]",
            ),
            AutoToolHideRule(
                token_limit=80_000,
                per_tool_token_limit=8_000,
            )
        ]
    )
    SystemMessage(content=chat_system_prompt.format(workspace_id=workspace_id)) | thread
    for message in messages:
        if isinstance(message, HumanMessage):
            HumanMessage(**message["message"]) | thread
        elif isinstance(message, AIMessage):
            AIMessage(**message["message"]) | thread
        elif isinstance(message, ToolMessage):
            ToolMessage(**message["message"]) | thread
    return thread

class ChatView(APIView):
    def post(self, request, workspace_id: int):
        messages = get_messages(workspace_id)
        thread = prepare_thread(messages, workspace_id)
        HumanMessage(content=request.data["message"]) | thread
        

        def generate(workspace_id: int, thread: Thread):
            for chunk in agent.stream(thread):
                yield chunk
            insert_thread(thread, workspace_id)

        return StreamingHttpResponse(
            generate(workspace_id, thread),
            content_type="text/plain",
        )

    def get(self, request, workspace_id: int):
        messages = get_messages(workspace_id)
        return Response({"messages": messages})
