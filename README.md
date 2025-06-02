# Ollama Flight Agent with MCP Integration

This project demonstrates the integration of **Ollama LLM** with the **MCP (Model Context Protocol)** server to process flight-related queries. The system uses natural language understanding to extract parameters from user queries and fetches relevant flight information from the MCP server.

## Features ✈️
- **Natural Language Query Processing**: Extracts flight details (e.g., flight ID, flight number, date range) from user queries using Ollama LLM.
- **Flight Information Retrieval**: Fetches flight details or lists of flights from the MCP server.
- **Multi-Step Reasoning**: Determines the appropriate MCP endpoint to call based on the query.
- **Dynamic Responses**: Formats user-friendly responses with flight details, weather, and temperature.
- **Error Handling**: Handles invalid queries, missing data, and server errors gracefully.

---

## How It Works 🛠️
1. **User Query**: The user provides a natural language query (e.g., "Show me flights for tomorrow").
2. **Parameter Extraction**: The query is processed by Ollama LLM to extract relevant parameters (e.g., dates, flight ID, flight number).
3. **MCP Server Interaction**: The extracted parameters are used to call the appropriate MCP server endpoint.
4. **Response Formatting**: The retrieved flight data is formatted into a user-friendly response using Ollama LLM.

---

## Prerequisites 📋
1. **Python 3.7+**: Ensure Python is installed on your system.
2. **Ollama Server**: Install and run the Ollama server locally. Pull the required model (e.g., `llama3`).
3. **MCP Server**: Ensure the MCP server is running on `http://127.0.0.1:5000`.
4. **Dependencies**: Install the required Python libraries:
   ```bash
   pip install requests