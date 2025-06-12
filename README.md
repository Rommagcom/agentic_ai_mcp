# LLM Chat Assistant

This project is a chat assistant application that integrates MCP client (MCP host) with an LLM (Large Language Model) and external tools (MCP Servers). It allows users to interact with the LLM, which can either provide direct answers or call external tools (MCP servers) to process user requests.

# Supported modes
 - stdio Mode
 - SSE (Server-Sent Events) Mode - Under development
 - http Mode - Under development
## Features

- **LLM Integration**: Communicates with an LLM using the `pydantic-ai` library.
- **Tool Execution**: Supports external tools - MCP servers that can be executed based on user input.
- **Structured Responses**: Handles structured responses from the LLM, including tool calls and direct answers.
- **Server Management**: Manages multiple MCP servers for tool execution.

## Requirements

- Python 3.11 or higher
- MCP server(s) configured for tool execution
- LLM used local installed Ollama with qwen3:0.6b - You can change it if needed (https://ollama.com - instruction how to.)
- .env LLM_API_KEY=your-api-key-here if exteral LLM used

## Installation
To execute demo MCP servers from 'mcp-servers' folder
1.FatMCP - https://github.com/modelcontextprotocol/python-sdk?tab=readme-ov-file#adding-mcp-to-your-python-project 
- More information about FastMCP -> https://gofastmcp.com/getting-started/welcome
2. Clone the repository:
   ```bash
   git clone https://github.com/Rommagcom/agentic_ai_mcp.git
   cd agentic_ai_mcp

   pip install -r requirements.txt
   python mcp_sse_client.py

## Interaction Example
- You: echo test (After this request LLM determine to call neccessery Tool from MCP server)
- Assistant: The result of the echo test is a text containing the message "This is echo test test". (Direct answer from MCP server)

- You: How is the weather in Phuket ?
- Assistant: The weather in Phuket is currently being retrieved via the API, with the mock response indicating it's a simulated result.


## Add your MCP server

	1. Add to mcp-server folder new .py file as in example echo.py or weater_server.py
	2. Add section to servers_config.json like where 'echo' is tool name in .py file -> @mcp.tool(description="A simple echo tool", name="echo")
	"args": ["mcp-servers/weather_server.py"] full server file path
	
	```Example:
	{
		"mcpServers": {
			"echo": {
				"command": "python",
				"args": ["mcp-servers/echo.py"]
			},
			"weather_server": {
				"command": "python",
				"args": ["mcp-servers/weather_server.py"]
			}
		}
	}
