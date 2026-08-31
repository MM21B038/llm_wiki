from langchain_core.tools import tool

class InternalTools:
    @classmethod
    def tools(cls):
        @tool("collapsed_tool_result", description="Fetch old collapsed tool result using tool call id.")
        def collapsed_tool_result(tool_call_id: str) -> str:
            # Ensure path is a Path object and join it with the filename
            file_path = Thread.get_tool_result_path() / tool_call_id
            
            try:
                # Direct, clean reading using pathlib
                return file_path.read_text(encoding="utf-8")
            except Exception as e:
                return str(e)

        return [collapsed_tool_result]
