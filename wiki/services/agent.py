import os
from composer import Agent, Thread, SystemMessage, HumanMessage, ToolMessage, ToolResultHideRule
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

agent = Agent(
    model=os.getenv("LLM"),
    base_url=os.getenv("BASE_URL"), 
    api_key=os.getenv("API_KEY"),
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
            compression_max_tokens=96000,
            compression_prompt=compression_prompt,
            compression_tail_messages=4,
            tool_hide_rules=[
                ToolResultHideRule(
                    tool_name="read_wiki_page",
                    on_hide_message="[earlier read_wiki_page result collapsed — see latest]",
                    hide_mode="persist",
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
