import os
from datetime import datetime
from typing import List

from dotenv import load_dotenv
from pymongo import MongoClient

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from agent.thread import Thread

load_dotenv()

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://kali:kali@127.0.0.1:27017/?authSource=admin&directConnection=true",
)
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

db = client["chat_llm"]

def get_collection():
    return db["threads"]


def insert_thread(thread: Thread, workspace_id: int):
    collection = get_collection()
    result = collection.find_one({"workspace_id": workspace_id})
    messages = result["messages"] if result else []
    if thread.tail is not None:
        thread = thread.tail
    for m in thread:
        if isinstance(m, HumanMessage):
            messages.append({
                "role": "user",
                "message": m.model_dump(),
            })
        elif isinstance(m, AIMessage):
            messages.append({
                "role": "assistant",
                "message": m.model_dump(),
            })
        elif isinstance(m, ToolMessage):
            messages.append({
                "role": "tool",
                "message": m.model_dump(),
            })
        elif isinstance(m, SystemMessage):
            messages.append({
                "role": "system",
                "message": m.model_dump(),
            })
    if result:
        collection.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"messages": messages}},
            upsert=True,
        )
    else:
        collection.insert_one({
            "workspace_id": workspace_id,
            "messages": messages,
        })


def get_messages(workspace_id: int):
    collection = get_collection()
    result = collection.find_one({"workspace_id": workspace_id})
    if not result:
        return []
    return result["messages"]
