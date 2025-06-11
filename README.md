# LLM Chat Assistant

This project is a chat assistant application that integrates MCP servers with an LLM (Large Language Model) and external tools (MCP Servers). It allows users to interact with the LLM, which can either provide direct answers or call external tools to process user requests.

## Features

- **LLM Integration**: Communicates with an LLM using the `pydantic-ai` library.
- **Tool Execution**: Supports external tools that can be executed based on user input.
- **Structured Responses**: Handles structured responses from the LLM, including tool calls and direct answers.
- **Server Management**: Manages multiple MCP servers for tool execution.

## Requirements

- Python 3.9 or higher
- MCP server(s) configured for tool execution
- LLM used local installed Ollama with qwen3:0.6b
- .env LLM_API_KEY=your-api-key-here if exteral LLM used

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-folder>

   pip install -r requirements.txt
   python mcp_sse_client.py

## Example Interaction
- You: echo test
- Assistant: The result of the echo test is a text containing the message "This is echo test test".  

- You: How is the weather in Phuket ?
- Assistant: The weather in Phuket is currently being retrieved via the API, with the mock response indicating it's a simulated result.


## Add your MCP server

	1. Add to mcp-server folder new .py file as in example echo.py or weater_server.py
	2. Add section to servers_config.json like where 'echo' is m tool name in .py file -> @mcp.tool(description="A simple echo tool", name="echo")
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
