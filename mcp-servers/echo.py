from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="EchoServer", stateless_http=True)


@mcp.tool(description="A simple echo tool", name="echo")
def echo(message: str) -> str:
    return f"Echo: {message} test"

@mcp.tool(description="A simple test echo tool", name="echo_test")
def echo_test(message: str) -> str:
    return f"This is echo {message} test"

if __name__ == "__main__":
    mcp.run()