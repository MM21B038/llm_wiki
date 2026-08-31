class ThreadHideRule:
    def __init__(
        self,
        name: str,
        message: str,
    ):
        self.name = name
        self.message = message

class AutoToolHideRule:
    def __init__(
        self,
        token_limit: int,
        per_tool_token_limit: Optional[int] = None
    ):
        self.token_limit = token_limit
        self.per_tool_token_limit = per_tool_token_limit