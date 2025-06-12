import asyncio
import json
import logging
import os
import re
import shutil
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

import pydantic_ai
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, UserContent # Often not needed directly when using Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

# Assuming these are part of your mcp library
from mcp import ClientSession, StdioServerParameters
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.stdio import stdio_client


# Configure logging
logging.basicConfig(
    level=logging.ERROR, # Set to INFO for debugging, ERROR for production
    format="%(asctime)s - %(levelname)s - %(message)s" # Ensure logs go to stdout, not just stderr by default
)

# --- Configuration ---
class AppConfiguration:
    """Manages application configuration, including LLM API keys and server settings."""

    def __init__(self) -> None:
        """Initializes configuration by loading environment variables."""
        # Using python-dotenv's load_dotenv directly here for simplicity
        from dotenv import load_dotenv
        load_dotenv()
        self._api_key: Optional[str] = os.getenv("LLM_API_KEY")

    def load_server_config(self, file_path: str) -> Dict[str, Any]:
        """Loads server configurations from a JSON file.

        Args:
            file_path: The path to the JSON configuration file.

        Returns:
            A dictionary containing the server configurations.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            json.JSONDecodeError: If the configuration file contains invalid JSON.
        """
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"Configuration file not found: {file_path}")
            raise
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON in configuration file: {file_path}")
            raise

    @property
    def llm_api_key(self) -> str:
        """Retrieves the LLM API key from environment variables.

        Returns:
            The LLM API key.

        Raises:
            ValueError: If the LLM_API_KEY environment variable is not set.
        """
        if not self._api_key:
            raise ValueError("LLM_API_KEY environment variable not found. Please set it.")
        return self._api_key

# --- Pydantic Models for LLM Interaction (Crucial for structured output) ---

class ToolCallArguments(BaseModel):
    """Base model for tool arguments, allowing dynamic fields."""
    # This will capture any arguments defined in the tool's inputSchema
    # For more strict typing, you'd define specific argument models per tool
    # Example: message: str = Field(...) for an 'echo' tool
    pass

class ToolCall(BaseModel):
    """Represents a structured request from the LLM to call a tool."""
    tool: str = Field(description="The name of the tool to be called.")
    arguments: Dict[str, Any] = Field(description="A dictionary of arguments for the tool.")
    url: Optional[str] = Field(
        None, description="Optional URL for the tool if it requires an HTTP endpoint."
    )

class LLMResponse(BaseModel):
    """
    Defines the expected structured output from the LLM.
    The LLM will either decide to use a tool or provide a direct answer.
    """
    tool_call: Optional[ToolCall] = Field(
        None, description="A structured request to call a tool, if applicable."
    )
    direct_answer: Optional[str] = Field(
        None, description="A direct natural language answer if no tool is needed."
    )


# --- Tool Definition and Formatting ---
class Tool:
    """Represents a tool with its properties and provides formatting for LLM context."""

    def __init__(self, name: str, description: str, input_schema: Dict[str, Any]) -> None:
        self.name: str = name
        self.description: str = description
        self.input_schema: Dict[str, Any] = input_schema

    def format_for_llm(self) -> str:
        """Formats tool information into a string suitable for LLM instructions."""
        args_desc: List[str] = []
        properties = self.input_schema.get("properties", {})
        required_params = self.input_schema.get("required", [])

        for param_name, param_info in properties.items():
            desc = param_info.get("description", "No description provided.")
            is_required = "(required)" if param_name in required_params else ""
            args_desc.append(f"- {param_name}: {desc} {is_required}")

        formatted_args = "\n".join(args_desc) if args_desc else "  No arguments."

        return (
            f"Tool: {self.name}\n"
            f"Description: {self.description}\n"
            f"Arguments:\n{formatted_args}\n"
        )


# --- Server Management ---
class ServerManager:
    """Manages MCP server connections and tool execution for a single server."""

    def __init__(self, name: str, config: Dict[str, Any]) -> None:
        self.name: str = name
        self.config: Dict[str, Any] = config
        self._session: Optional[ClientSession] = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self._exit_stack: AsyncExitStack = AsyncExitStack()
        self._tools_cache: Optional[List[Tool]] = None # Cache tools after first listing

    async def initialize(self) -> None:
        """Initializes the MCP client session for the server."""
        command = (
            shutil.which("node")
            if self.config.get("command") == "node"
            else self.config.get("command")
        )
        
        url = self.config.get("url", None)

        if url:
            logging.info(f"Using URL for server {self.name}: {url}")
            server_params = streamablehttp_client(url=url)
        else:
            logging.info(f"Using STDIO for server {self.name}")
            server_params = StdioServerParameters(
                command=command,
                args=self.config.get("args", []),
                env={**os.environ, **self.config.get("env", {})},
            )

        logging.info(f"Initializing server {self.name} with command: {command} args: {server_params.args}")
        try:
            if not url:
                logging.info(f"Using stdio transport for server {self.name}.")
                stdio_transport  = await self._exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                read, write = stdio_transport
                self._session = await self._exit_stack.enter_async_context(
                        ClientSession(read, write)
                    )
                await self._session.initialize()
                
            else:
                logging.info(f"Using streamable HTTP transport for server {self.name}.")

                read_stream, write_stream, _ = await self._exit_stack.enter_async_context(
                    streamablehttp_client(url)
                )
                self._session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await self._session.initialize()

            logging.info(f"Server {self.name} initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize server {self.name}: {e}")
            await self.cleanup()  # Ensure cleanup on failed initialization
            raise

    async def list_tools(self) -> List[Tool]:
        """Lists available tools from the server, using a cache to avoid repeated calls."""
        if self._tools_cache is not None:
            return self._tools_cache

        if not self._session:
            raise RuntimeError(f"Server {self.name} not initialized to list tools.")

        logging.info(f"Listing tools for server {self.name}...")
        tools_response = await self._session.list_tools()
        tools: List[Tool] = []

        for item in tools_response:
            # Assuming 'tools' is the identifier in the tuple for actual tool definitions
            if isinstance(item, tuple) and item[0] == "tools":
                tools.extend(
                    Tool(tool.name, tool.description, tool.inputSchema)
                    for tool in item[1]
                )
        self._tools_cache = tools # Cache the tools
        logging.info(f"Found {len(tools)} tools for server {self.name}.")
        print("Available tools:")
        for tool in tools:
            print(f"- {tool.name}: {tool.description}")
            print(f"  Arguments: {tool.input_schema.get('properties', {})}")
            print(f"---------------------------------------")
        return tools

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        retries: int = 2,
        delay: float = 1.0,
    ) -> Any:
        """Executes a named tool on the server with a retry mechanism."""
        if not self._session:
            raise RuntimeError(f"Server {self.name} not initialized to execute tool '{tool_name}'.")

        for attempt in range(retries + 1): # +1 to include the initial attempt
            try:
                logging.info(f"Attempt {attempt + 1}: Executing tool '{tool_name}' with arguments: {arguments}")
                result = await self._session.call_tool(tool_name, arguments)
                logging.info(f"Tool '{tool_name}' executed successfully. Result type: {type(result)}")

                # Optional: Add specific handling for progress updates if 'progress' is always a dict
                if isinstance(result, dict) and "progress" in result and "total" in result:
                    try:
                        progress = result["progress"]
                        total = result["total"]
                        percentage = (progress / total) * 100
                        logging.info(f"Tool Progress: {progress}/{total} ({percentage:.1f}%)")
                    except (TypeError, ZeroDivisionError) as e:
                        logging.warning(f"Could not parse progress data for tool '{tool_name}': {result}. Error: {e}")

                return result
            except Exception as e:
                logging.warning(f"Error executing tool '{tool_name}': {e}.")
                if attempt < retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logging.error(f"Max retries reached for tool '{tool_name}'. Failing.")
                    raise

    async def cleanup(self) -> None:
        """Cleans up resources associated with the server session."""
        async with self._cleanup_lock:
            if self._session:
                logging.info(f"Cleaning up server {self.name}...")
                try:
                    await self._exit_stack.aclose()
                    self._session = None
                    logging.info(f"Server {self.name} cleaned up.")
                except Exception as e:
                    logging.error(f"Error during cleanup of server {self.name}: {e}")


# --- LLM Client ---
class LLMClient:
    """Manages communication with the LLM provider using pydantic-ai for structured output."""

    def __init__(self, api_key: str):
        # Configure the OpenAI provider with the base URL for Ollama
        provider = OpenAIProvider(base_url='http://localhost:11434/v1', api_key=api_key) # Use actual API key if needed by Ollama
        self.ollama_model = OpenAIModel(
            model_name='qwen3:0.6b',
            provider=provider
        )
    async def get_json_from_response(self, response: str) -> LLMResponse:
        """
        Extracts and returns the JSON object from the LLM response.

        Args:
            response: The raw response from the LLM.

        Returns:
            A dictionary representing the JSON object.

        Raises:
            ValueError: If no valid JSON object is found in the response.
        """
        try:
            # Use regex to extract the JSON part from the response
            match = re.search(r"{.*}", response, flags=re.DOTALL)
            if match:
                json_str = match.group(0)
                return LLMResponse.model_validate_json(json_str.replace("\n", "").strip())  # Parse the JSON string into a dictionary
            else:
                raise ValueError("No valid JSON object found in the response.")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")
        
    async def get_structured_response(self, user_prompt: str, instructions: str) -> LLMResponse:
        """
        Gets a structured response from the LLM, either a tool call or a direct answer.

        Args:
            user_prompt: The user's input message.
            instructions: System-level instructions for the LLM.

        Returns:
            An LLMResponse object containing either a tool call or a direct answer.

        Raises:
            pydantic_ai.exceptions.UnexpectedModelBehavior: If the model's output doesn't conform to LLMResponse.
            Exception: For other errors during LLM processing.
        """
        agent = Agent(
            model=self.ollama_model,
            output_type=str, # <-- THIS IS THE KEY CHANGE!
            instructions=instructions,
            max_result_retries=8,
            #result_type= str,  # <-- Use the structured response model
            #format=LLMResponse.model_json_schema()
            # Adjust messages based on how pydantic-ai's Agent expects them
            # For simplicity, Agent.run usually handles this when you provide user_prompt
        )

        try:
            logging.info("Requesting structured response from LLM...")
            # Agent.run expects user_prompt directly and often manages messages internally
            llm_response_obj  = await agent.run(user_prompt=user_prompt)
            #print(f"LLM Response: {llm_response_obj.output}")  # For debugging
            json_data = await self.get_json_from_response(llm_response_obj.output)
           
            return json_data
        except pydantic_ai.exceptions.UnexpectedModelBehavior as e:
            logging.error(f"LLM output did not conform to schema: {e}")
            # The model tried to output something but it didn't fit LLMResponse.
            # You might want to try again with a stricter prompt or return a default error.
            return LLMResponse(direct_answer="I couldn't understand the model's output.")
        except Exception as e:
            logging.error(f"Error during LLM processing: {e}")
            print(f"Assistant: An error occurred while processing your request. Please try again.")
            return LLMResponse(direct_answer="An unexpected error occurred with the LLM. Please try again.")

    async def get_text_from_response(self, response: str) -> str:
        """
        Extracts and returns the string from the LLM response.

        Args:
            response: The raw response from the LLM.

        Returns:
            A dstring representing the String object.

        Raises:
            ValueError: If no valid String object is found in the response.
        """
        try:
            # Use regex to extract the JSON part from the response
            match = re.search(r"</think>(.*)", response, flags=re.DOTALL)
            if match:
                data_str = match.group(1)  # Extract the string part after </think>
                return data_str # Return the string without extra whitespace  
            else:
                raise ValueError("No valid string object found in the response.")
        except Exception as e:
            raise ValueError(f"Invalid string format: {e}")
        
    async def get_natural_language_response(self, context: str, user_prompt: str) -> str:
        """
        Gets a natural language response from the LLM based on tool execution context.

        Args:
            context: The result of tool execution or previous LLM response.
            user_prompt: The original user's prompt to maintain context.

        Returns:
            The LLM's natural language response.
        """
        # This agent is for free-form text generation
        agent = Agent(
            model=self.ollama_model,
            output_type=str, # Now we want a plain string
            instructions=(
                "You are a helpful assistant. Based on the provided context and the original user's intent, "
                "generate a natural, concise, and informative response. Do not repeat the raw data. "
                "Focus on the most relevant information and use appropriate context."
                "You **MUST** respond **ONLY** with a natural language response, "
                "without any JSON formatting, reasoning, or additional text. "
                "Your response should be clear and directly address the user's request.\n\n"
                f"\n\nOriginal User Prompt: {user_prompt}"
            ),
            max_result_retries=3 # Fewer retries for simple text generation
        )
        try:
            logging.info("Requesting natural language response from LLM...")
            # Pass the context as part of the message to the LLM
            # You might need to adjust this to fit pydantic-ai's message structure,
            # e.g., using specific message types if `Agent.run` expects them.
            # For `Agent.run(user_prompt=...)`, the whole `context` string might be the prompt.
            # Or you might structure it as: messages=[UserContent(content=context), ...]
            natural_response = await agent.run(user_prompt=context)
            logging.info(f"Natural Language LLM Response: {natural_response.output}")
            logging.info(f"Parsing response to extract text...")
            llm_result = await self.get_text_from_response(natural_response.output)
                      
            return llm_result
        except Exception as e:
            logging.error(f"Error generating natural language response: {e}")
            return "I had trouble formulating a response based on the tool's output."

# --- Chat Session ---
class ChatSession:
    """Orchestrates the interaction between user, LLM, and external tools."""

    def __init__(self, servers: List[ServerManager], llm_client: LLMClient) -> None:
        self.servers: List[ServerManager] = servers
        self.llm_client: LLMClient = llm_client
        self._all_tools_description: Optional[str] = None # Cache formatted tools

    async def _initialize_servers(self) -> None:
        """Initializes all configured servers."""
        logging.info("Initializing servers...")
        for server in self.servers:
            try:
                await server.initialize()
            except Exception:
                logging.critical(f"Critical error: Failed to initialize server {server.name}. Shutting down.")
                raise # Re-raise to stop the main loop

    async def _get_tools_description(self) -> str:
        """Generates and caches the formatted description of all available tools."""
        if self._all_tools_description is None:
            all_tools: List[Tool] = []
            for server in self.servers:
                try:
                    tools = await server.list_tools()
                    all_tools.extend(tools)
                except RuntimeError as e:
                    logging.warning(f"Could not list tools from server {server.name}: {e}")
            self._all_tools_description = "\n".join([tool.format_for_llm() for tool in all_tools])
            if not self._all_tools_description.strip():
                logging.warning("No tools found or described. The LLM will not be able to use tools.")
            logging.info(f"Tools description generated:\n{self._all_tools_description}")
        return self._all_tools_description

    def _build_system_instructions(self, tools_description: str) -> str:
        return (
            "You are a helpful assistant with access to external tools. Your primary goal is to assist the user by either "
            "providing direct answers or by calling the appropriate tool. "
            "You **MUST** respond **ONLY** with a valid JSON object. "
            "You **MUST NOT** include any other text, reasoning, preamble, postamble, or Markdown delimiters (like ```json) "
            "outside the JSON object. "
            "The JSON object **MUST** strictly conform to the following schema:"
             # This markdown block is just for the LLM's understanding of the schema, not actual output
            "{"
            '    "tool_call": {'
            '        "tool": "string",'
            '        "arguments": {"key": "value"}'
            '    },'
            '    "direct_answer": "string"'
            "}"
            "**Rules for your JSON response:**\n"
            "1.  If a tool is required, you **MUST** set the `tool_call` field and leave `direct_answer` as `null`.\n"
            "2.  If no tool is needed, you **MUST** set the `direct_answer` field with your natural language response and leave `tool_call` as `null`.\n"
            "3.  You **MUST NOT** include any other text, reasoning, or formatting outside this JSON object.\n"
            "4.  You **MUST NOT** wrap the JSON in Markdown code blocks.\n" # <-- Explicitly state this!
            "5.  Only use tools that are explicitly defined below.\n\n"
            f"Available Tools:\n{tools_description}\n\n"
            "Example JSON for a tool call (e.g., if user asks to 'echo hello'):\n"
            "```json\n"
            "{\n"
            '    "tool_call": {\n'
            '        "tool": "echo",\n'
            '        "arguments": {\n'
            '            "message": "hello"\n'
            '        }\n'
            '    },\n'
            '    "direct_answer": null\n'
            "}\n"
            "```\n\n"
            "Example JSON for a direct answer (e.g., if user asks 'what is 2+2?'):\n"
            "```json\n"
            "{\n"
            '    "tool_call": null,\n'
            '    "direct_answer": "Two plus two equals four."\n'
            "}\n"
            "```"
        )


    async def _process_llm_structured_response(self, llm_response: LLMResponse, original_user_prompt: str) -> str:
        """Processes the structured LLM response (tool call or direct answer)."""
        if llm_response.tool_call:
            tool_name = llm_response.tool_call.tool
            tool_args = llm_response.tool_call.arguments
            logging.info(f"LLM requested tool: {tool_name} with arguments: {tool_args}")

            for server in self.servers:
                try:
                    # Check if the tool exists on this server (optional, but good for robustness)
                    server_tools = await server.list_tools()
                    if any(tool.name == tool_name for tool in server_tools):
                        tool_result = await server.execute_tool(tool_name, tool_args)
                        logging.info(f"Tool '{tool_name}' returned: {tool_result}")

                        # Now, send the tool result back to the LLM for a natural language summary
                        # The `context` here is the tool's raw result
                        return await self.llm_client.get_natural_language_response(
                            context=f"Tool '{tool_name}' executed with result: {tool_result.text if hasattr(tool_result, 'text') else tool_result}",
                            user_prompt=original_user_prompt
                        )
                except RuntimeError as e:
                    logging.warning(f"Server {server.name} error during tool check/execution: {e}")
                except Exception as e:
                    logging.error(f"Error processing tool call {tool_name} on server {server.name}: {e}")
                    return f"An error occurred while executing tool '{tool_name}': {e}"

            return f"Error: No server found with tool '{tool_name}'."
        elif llm_response.direct_answer:
            logging.info("LLM provided a direct answer.")
            return llm_response.direct_answer
        else:
            logging.warning("LLM response did not contain a tool call or a direct answer.")
            return "I'm sorry, I couldn't process your request."

    async def start(self) -> None:
        """Starts the main chat session, handling user input and LLM/tool interactions."""
        await self._initialize_servers()
        system_instructions = self._build_system_instructions(await self._get_tools_description())
        #logging.info(f"Full System Instructions:\n{system_instructions}") # Uncomment for debugging system prompt

        try:
            while True:
                user_input = input("You: ").strip()
                if user_input.lower() in ["quit", "exit"]:
                    logging.info("Exiting chat session.")
                    break

                # Get structured response from LLM (tool call or direct answer)
                llm_structured_response = await self.llm_client.get_structured_response(
                    user_prompt=user_input, instructions=system_instructions
                )

                # Process the structured response (execute tool or return direct answer)
                final_response = await self._process_llm_structured_response(
                    llm_structured_response, original_user_prompt=user_input
                )
                print(f"Assistant: {final_response}")  # Print the final response to the user
                logging.info(f"Assistant: {final_response}")

        except KeyboardInterrupt:
            logging.info("Chat session interrupted. Exiting.")
        except Exception as e:
            logging.critical(f"An unhandled error occurred in the chat session: {e}", exc_info=True)
        finally:
            logging.info("Cleaning up all server resources.")
            for server in self.servers:
                await server.cleanup()


async def main() -> None:
    """Initializes and runs the main application."""
    try:
        config = AppConfiguration()
        server_configs = config.load_server_config("servers_config.json")

        servers = [
            ServerManager(name, srv_config)
            for name, srv_config in server_configs.get("mcpServers", {}).items()
        ]
        llm_client = LLMClient(config.llm_api_key)

        chat_session = ChatSession(servers, llm_client)
        await chat_session.start()

    except Exception as e:
        logging.critical(f"Application failed to start: {e}", exc_info=True)


if __name__ == "__main__":
    # Ensure sys is imported for logging handler
    import sys
    asyncio.run(main())