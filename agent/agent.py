from langchain_openai import ChatOpenAI
from typing import List
from agent.thread import Thread
from agent.internal_tools import InternalTools

class Agent:
    def __init__(self, model: ChatOpenAI, tools=List):
        self.model = model
        self.tools = tools
        if self.tools:
            self.tools.extend(InternalTools.tools())
            self.model = self.model.bind_tools(self.tools)
        self.tool_map = {tool.name: tool for tool in self.tools}
            
    def invoke(self, thread: Thread, self_append: bool = True):
        if thread.tail is not None:
            thread = thread.tail
        thread.agent = self
        while True:
            response = self.model.invoke(thread.messages)
            
            if not self_append:
                thread.agent = None
                return response
                
            thread.append(response)
            if response.tool_calls:
                for tool in response.tool_calls:
                    args=tool["args"]
                    call_id = tool["id"]
                    name = tool["name"]
                    result = self.tool_map[name].invoke(args)
                    thread.append(ToolMessage(name=name, content=result, tool_call_id=call_id))
            else:
                thread.agent = None
                return response

    def __ror__(self, thread: Thread):
        return self.invoke(thread)