import asyncio
import threading
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI
from typing import List, Iterator, Any
from agent.thread import Thread
from agent.internal_tools import InternalTools

def run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result = []
    error = []

    def runner():
        try:
            result.append(asyncio.run(coro))
        except BaseException as e:
            error.append(e)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()

    if error:
        raise error[0]

    return result[0]


class Agent:
    def __init__(self, model: ChatOpenAI, tools: List = None):
        self.model = model
        self.tools = tools
        self.tool_map = {}
        if self.tools:
            self.tools.extend(InternalTools.tools())
            self.model = self.model.bind_tools(self.tools)
            self.tool_map = {tool.name: tool for tool in self.tools}
            
    async def ainvoke(self, thread: Thread, self_append: bool = True):
        if thread.tail is not None:
            thread = thread.tail
        thread.agent = self
        while True:
            response = await self.model.ainvoke(thread.messages)
            
            if not self_append:
                thread.agent = None
                return response
                
            thread.append(response)
            if response.tool_calls:
                for tool in response.tool_calls:
                    args=tool["args"]
                    call_id = tool["id"]
                    name = tool["name"]
                    try:
                        result = await self.tool_map[name].ainvoke(args)
                    except Exception as e:
                        result = f"Error: {e}"
                    thread.append(ToolMessage(name=name, content=str(result), tool_call_id=call_id))
            else:
                thread.agent = None
                return response

    def invoke(self, thread: Thread, self_append: bool = True):
        return run_sync(
            self.ainvoke(
                thread=thread, 
                self_append=self_append
            )
        )
    
    def stream(
        self,
        thread: Thread,
        self_append: bool = True,
    ) -> Iterator[Any]:

        if thread.tail is not None:
            thread = thread.tail

        thread.agent = self

        try:
            while True:

                # Accumulated complete AI response
                response = None

                # Stream from model
                for chunk in self.model.stream(thread.messages):

                    # Send chunk to caller immediately
                    yield chunk

                    # Accumulate chunks
                    if response is None:
                        response = chunk
                    else:
                        response = response + chunk

                # If requested, save complete response
                if not self_append:
                    return

                thread.append(response)

                # Check for tool calls after the complete
                # streamed response has been assembled
                if response.tool_calls:

                    for tool in response.tool_calls:

                        args = tool["args"]
                        call_id = tool["id"]
                        name = tool["name"]

                        try:
                            result = self.tool_map[name].invoke(args)
                        except Exception as e:
                            result = f"Error: {e}"

                        tool_message = ToolMessage(
                            name=name,
                            content=result,
                            tool_call_id=call_id,
                        )

                        thread.append(tool_message)

                        # Continue while-loop.
                        # The next iteration sends:
                        #
                        # previous messages
                        # + AIMessage(tool_call)
                        # + ToolMessage(result)
                        #
                        # back to the model.

                else:
                    return

        finally:
            thread.agent = None


    def __ror__(self, thread: Thread):
        return self.invoke(thread)