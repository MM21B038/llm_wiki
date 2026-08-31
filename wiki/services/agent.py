import os
from agent.agent import Agent
from agent.thread import Thread
from agent.thread_rules import ThreadHideRule, AutoToolHideRule
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from wiki.tools import tools
from dotenv import load_dotenv
load_dotenv()
from wiki.services.prompts import system_prompt, compression_prompt
from wiki.models import Chunk
from typing import Any
from pathlib import Path
from wiki.enum import Status
import frontmatter

wiki_skill = frontmatter.load(Path("wiki/services/skills/wiki.md")).content
wiki_mcp_skill = frontmatter.load(Path("wiki/services/skills/wiki_mcp.md")).content

llm = ChatOpenAI(
    model=os.getenv("LLM"),
    base_url=os.getenv("BASE_URL"), 
    api_key=os.getenv("API_KEY"),
)

agent = Agent(
    model=llm,
    tools=tools,
)

def wiki_agent(workspace_id: int, chunk: Chunk) -> Any:
    print(f"Processing chunk {chunk.id} for workspace {workspace_id}")
    chunk.status = Status.PROCESSING
    chunk.save()
    try:
        message = (
            "Here is the new job to be performed:",
            f"- the workspace id is for the job to be performed: {workspace_id}",
            f"- the chunk id is for the job to be performed: {chunk.id}",
            f"- this is the new content to be processed: {chunk.content}",
        )
        thread = Thread(
            compression_prompt=compression_prompt,
            token_limit=96000,
            tool_hide_rules=[
                ThreadHideRule(
                    name="read_wiki_page",
                    message="[earlier read_wiki_page result collapsed — see latest]",
                ),
                AutoToolHideRule(
                    token_limit=64_000,
                    per_tool_token_limit=6_000,
                )
            ]
        )
        SystemMessage(content=system_prompt + "\n" + wiki_skill + "\n" + wiki_mcp_skill) | thread
        HumanMessage(content="\n".join(message)) | thread
        thread | agent
        chunk.status = Status.COMPLETED
        chunk.save()
        print(f"Chunk {chunk.id} for workspace {workspace_id} processed successfully")
    except Exception as e:
        print(f"Error processing chunk {chunk.id} for workspace {workspace_id}: {e}")
        chunk.status = Status.FAILED
        chunk.save()
        raise e
