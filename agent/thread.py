from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from typing import List, Union, Optional, Dict, Literal
import tiktoken
import json
from agent.thread_rules import ThreadHideRule, AutoToolHideRule
from pathlib import Path

class Thread:
    def __init__(
        self, 
        messages: List[Union[AIMessage, HumanMessage, ToolMessage, SystemMessage]] = None, 
        system_prompt: Union[str, SystemMessage] = None,
        compression_prompt: str = None,
        token_limit: int = None,
        tool_hide_rules: List[Union[ThreadHideRule, AutoToolHideRule]] = None   
    ):
        self.messages = []
        self.system_prompt = system_prompt
        self.compression_prompt = compression_prompt
        self.token_limit = token_limit
        self.agent = None
        self.encoder = tiktoken.encoding_for_model("gpt-4o-mini")
        self.root = None
        self.parent = None
        self.child = None
        self.tail = None
        self.tool_hide_rules = tool_hide_rules
        self.path = Path.cwd() / "tool_results"
        self.path.mkdir(parents=True, exist_ok=True)

        
        if messages is not None:
            index = self._find_system_message(messages)
            if index == -1 or index == 0:
                self.messages = messages
            else:
                raise Valueerror(
                    f"system message not at the starting, it was found at {index} index"
                )
                    
        if self.system_prompt is not None:
            index = self._find_system_message(self.messages)
            if isinstance(self.system_prompt, str):
                self.system_prompt = SystemMessage(self.system_prompt)
            if index == 0:
                if len(self.messages) == 0:
                    self.append(self.system_prompt)
                else:
                    self[0] = self.system_prompt
            elif index == -1:
                self.messages = [self.system_prompt] + self.messages
            else:
                pass

    @classmethod
    def get_tool_result_path(cls):
        path = Path.cwd() / "tool_results"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _find_system_message(self, messages: List[Union[AIMessage, HumanMessage, ToolMessage, SystemMessage]]):
        for i in range(len(messages)):
            if isinstance(messages[i], SystemMessage):
                return i
        return -1

    def count_token(self):
        if self.tail is not None:
            content = [m.content for m in self.tail]
        else:
            content = [m.content for m in self]
        merged = "\n".join(content)
        return len(self.encoder.encode(merged))

    def calculate_tokens(self, content):
        return len(self.encoder.encode(content))
        
        
    def append(self, message: Union[AIMessage, HumanMessage, ToolMessage, SystemMessage]):
        if self.root is not None:
            tool_hide_rules = self.root.tool_hide_rules
        else:
            tool_hide_rules = self.tool_hide_rules

        thread_hide_rules = [rule for rule in tool_hide_rules if isinstance(rule, ThreadHideRule)]
        
        auto_tool_hide_rules = None
        for rule in tool_hide_rules:
            if isinstance(rule, AutoToolHideRule):
                auto_tool_hide_rules = rule
                break
        
            
        if isinstance(message, ToolMessage) and tool_hide_rules is not None:
            name = message.name
            match = False
            tool_hide_rule = None
            for rule in thread_hide_rules:
                if rule.name == name:
                    match = True
                    tool_hide_rule = rule
                    break
            if match:
                for m in reversed(self):
                    if isinstance(m, ToolMessage) and m.name == name:
                        self.save_tool_result(m)
                        m.content = tool_hide_rule.message + f"\n tool call id {m.tool_call_id}. use the ID to retrive this tool result using collapsed_tool_result"
                        break
                        
        if auto_tool_hide_rules is not None:
            total_tokens = self.count_token()
            if total_tokens >= auto_tool_hide_rules.token_limit:
                if auto_tool_hide_rules.per_tool_token_limit is not None:
                    per_tool_token_limit = auto_tool_hide_rules.per_tool_token_limit
                    for m in reversed(self):
                        if isinstance(m, ToolMessage) and self.calculate_tokens(m.content) > per_tool_token_limit:
                            self.save_tool_result(m)
                            m.content = f"This tool call result has been collapsed due to token size constraints.\n tool call id {m.tool_call_id}. use the ID to retrive this tool result using collapsed_tool_result"
                else:
                    per_tool_token_limit = 8_000
                    for m in reversed(self):
                        if isinstance(m, ToolMessage) and self.calculate_tokens(m.content) > per_tool_token_limit:
                            self.save_tool_result(m)
                            m.content = f"This tool call result has been collapsed due to token size constraints.\n tool call id {m.tool_call_id}. use the ID to retrive this tool result using collapsed_tool_result"

                        
        token_usuage = self.count_token()
        if self.token_limit is not None and token_usuage > self.token_limit and self.agent is not None and self.compression_prompt is not None:
            self.messages.append(HumanMessage(self.compression_prompt))
            compression_report = self.agent.invoke(self, self_append=False).content
            self.messages.pop()
            
            new_thread = self.copy()
            self.child = new_thread
            new_thread.parent = self
            new_thread.root = self.root if self.root is not None else self
            self.root.tail = new_thread

            new_thread.messages = []
            if isinstance(self.root[0], SystemMessage):
                new_thread.append(self.root[0])
            new_thread.append(HumanMessage(compression_report)) 
        else:
            self.messages.append(message)

    def save_tool_result(self, message: ToolMessage) -> bool:
        try:
            with open(self.path / str(message.tool_call_id), "w", encoding="utf-8") as f:
                f.write(message.content)
            return True
        except:
            return False

    def count(self):
        counts = {
            "depth":0,
            "system":0, 
            "human":0,
            "ai":0,
            "tool":0
        }
        thread = self
        depth = 0
        if isinstance(thread[0], SystemMessage):
            counts["system"]=1
        while True:
            for m in thread:
                if isinstance(m, AIMessage):
                    counts["ai"]+=1
                elif isinstance(m, HumanMessage):
                    counts["human"]+=1
                elif isinstance(m, ToolMessage):
                    counts["tool"]+=1
                else:
                    pass
            if thread.child is None:
                break
            else:
                thread = thread.child
                depth += 1
        counts["depth"] = depth
        return counts

    def __ror__(self, other: Union[AIMessage, HumanMessage, ToolMessage, SystemMessage]):
        if self.tail is not None:
            self.tail.append(other)
        else:
            self.append(other)

    # def __add__(self, other: Thread):
    #     new_thread = Thread()
    #     new_thread.messages = self.messages + other.messages
    #     return new_thread

    def __str__(self):
        counts = self.count()
        return json.dumps(counts)

    def __repr__(self):
        counts = self.count()
        return json.dumps(counts)

    def __iter__(self):
        if self.tail is not None:
            for msg in self.tail.messages:
                yield msg
        else:
            for msg in self.messages:
                yield msg
                
    def __getitem__(self, index):
        if self.tail is not None:
            return self.tail.messages[index]
        else:
            return self.messages[index]

    def __len__(self):
        if self.tail is not None:
            return len(self.tail.messages)
        else:
            return len(self.messages)

    def __setitem__(self, index, value):
        if self.tail is not None:
            self.tail.messages[index] = value
        else:
            self.messages[index] = value

    def __copy__(self):
        new_instance = Thread()
        return new_instance
        