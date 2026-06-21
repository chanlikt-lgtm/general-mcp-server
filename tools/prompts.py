from mcp.server.fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:

    @mcp.prompt()
    def analyze(dataset: str, goal: str) -> str:
        """Analyze a dataset to achieve a stated goal using available tools."""
        return f"""Analyze the {dataset} dataset to achieve: {goal}.

Steps:
1. Use list_tables to see available data
2. Use query_database to fetch relevant rows
3. Summarize findings clearly with numbers"""

    @mcp.prompt()
    def debug(error: str, context: str) -> str:
        """Debug an error given the error message and surrounding context."""
        return f"""Debug this error: {error}

Context: {context}

Use read_file to inspect relevant source files, then explain the root cause and the fix."""

    @mcp.prompt()
    def summarize(topic: str) -> str:
        """Summarize a topic using all available tools."""
        return f"Summarize everything you know about '{topic}' using the available tools to gather data first."
