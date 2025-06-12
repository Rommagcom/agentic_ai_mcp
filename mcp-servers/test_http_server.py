from fastmcp import FastMCP

mcp = FastMCP(name="MyHttpServer",stateless_http=True)

@mcp.tool(description="A simple http call tool", name="echo_http")
def greet(name: str) -> str:
    """Greet a user by name."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    # This runs the server, defaulting to STDIO transport
    mcp.run(transport="streamable-http", host="127.0.0.1", port=9000)
