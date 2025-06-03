# ollama_agent.py
import ollama
from datetime import datetime, date, timedelta
import re
from mcp_client import MCPClient  # Import our custom client
from typing import List, Dict, Optional, Tuple, Union

class OllamaFlightAgent:
    def __init__(self, ollama_model: str = "qwen3:0.6b", mcp_base_url: str = "http://127.0.0.1:5000", ollama_base_url: str = "http://127.0.01:11434"):
        self.ollama_model = ollama_model
        self.mcp_client = MCPClient(mcp_base_url)
        self.ollama_base_url = ollama_base_url
        ollama.configure(base_url=self.ollama_base_url)  # Configure Ollama to use the specified server
        print(f"Ollama Flight Agent initialized with model '{self.ollama_model}', MCP server '{mcp_base_url}', and Ollama server '{self.ollama_base_url}'")

    def _extract_query_parameters(self, query: str) -> Dict:
        """
        Uses Ollama to extract relevant parameters (dates, flight ID, flight number)
        from a natural language query.
        """
        prompt = f"""
        Analyze the following user query and extract any specified dates, flight IDs, or flight numbers.
        
        If a date range is requested (e.g., "from X to Y", "this week", "next month"), provide 'dateFrom' and 'dateTo'.
        If only one date is mentioned, assume it's both the start and end date for a range query.
        If relative terms like "today", "tomorrow", "next week", "this week", "next month" are used,
        convert them to specific YYYY-MM-DD dates relative to today ({date.today().isoformat()}).
        "Next week" means from next Monday to next Sunday.
        "This week" means from this Monday to this Sunday.
        "Next month" means the entire next calendar month.

        If a specific flight ID is mentioned (e.g., "рейс с ID 1234"), extract 'flightId'.
        If a specific flight number and date are mentioned (e.g., "рейс SU123 на 2025-06-05"), extract 'flightNumber' and 'flightDate'.

        Prioritize specific flight details (ID or number/date) over date ranges if both are present.
        If no specific flight details or date range is specified, assume today as the date range.

        Output the extracted parameters in JSON format.
        Example outputs:
        {{"dateFrom": "YYYY-MM-DD", "dateTo": "YYYY-MM-DD"}}
        {{"flightId": 1234}}
        {{"flightNumber": "SU123", "flightDate": "YYYY-MM-DD"}}
        {{}} (if no parameters found, implies today's date range by default)

        User query: "{query}"
        """

        try:
            response = ollama.generate(model=self.ollama_model, prompt=prompt, format='json', options={'temperature': 0.1})
            if isinstance(response['response'], str):
                import json
                params = json.loads(response['response'])
            else:
                params = response['response']

            # Convert date strings to datetime.date objects if present
            if 'dateFrom' in params and isinstance(params['dateFrom'], str):
                params['dateFrom'] = datetime.strptime(params['dateFrom'], '%Y-%m-%d').date()
            if 'dateTo' in params and isinstance(params['dateTo'], str):
                params['dateTo'] = datetime.strptime(params['dateTo'], '%Y-%m-%d').date()
            if 'flightDate' in params and isinstance(params['flightDate'], str):
                params['flightDate'] = datetime.strptime(params['flightDate'], '%Y-%m-%d').date()

            # Default to today if no parameters found
            if not params:
                params = {"dateFrom": date.today(), "dateTo": date.today()}

            return params
        except Exception as e:
            print(f"Error calling Ollama for parameter extraction: {e}")
            # Fallback to today's date if extraction fails
            return {"dateFrom": date.today(), "dateTo": date.today()}

    def process_query(self, user_query: str) -> str:
        """
        Processes a user query to get flight information using multi-step reasoning.
        """
        print(f"\nUser: {user_query}")

        # Step 1: Use Ollama to extract parameters from the user's query
        print("Agent: Extracting query parameters using Ollama...")
        params = self._extract_query_parameters(user_query)
        print(f"Agent: Detected parameters: {params}")

        response_text = ""

        # Step 2: Decide which MCP endpoint to call based on extracted parameters (Multi-step reasoning)
        if 'flightId' in params or ('flightNumber' in params and 'flightDate' in params):
            # User is asking for specific flight details
            flight_id = params.get('flightId')
            flight_number = params.get('flightNumber')
            flight_date = params.get('flightDate')

            print(f"Agent: User requested specific flight details. Calling MCP server for details...")
            flight_data = self.mcp_client.get_flight_details(
                flight_id=flight_id, 
                flight_number=flight_number, 
                flight_date=flight_date
            )

            if flight_data:
                flight_datetime = datetime.fromisoformat(flight_data['flightDate'])
                response_text = f"""
                Информация о рейсе {flight_data['flightNumber']} (ID: {flight_data['flightId']}):
                Маршрут: {flight_data['origin']} -> {flight_data['destination']}
                Дата и время: {flight_datetime.strftime('%Y-%m-%d %H:%M')}
                Погода в пункте назначения: {flight_data['weather']}, Температура: {flight_data['temperature']}
                """
            else:
                response_text = "Извините, не удалось найти информацию по указанному рейсу. Пожалуйста, проверьте ID рейса, номер рейса и дату."
        elif 'dateFrom' in params and 'dateTo' in params:
            # User is asking for a range of flights
            date_from = params['dateFrom']
            date_to = params['dateTo']

            print(f"Agent: User requested flights for a date range. Calling MCP server for general info...")
            flights_data = self.mcp_client.get_flights_info(date_from, date_to)

            if not flights_data:
                response_text = "Извините, не удалось получить информацию о рейсах. Возможно, сервер недоступен или произошла ошибка."
            elif not flights_data: # Check again after potential error handling in client
                response_text = f"На период с {date_from.isoformat()} по {date_to.isoformat()} рейсов не найдено."
            else:
                # Prepare flight data for LLM
                flights_summary = []
                for flight in flights_data:
                    flight_datetime = datetime.fromisoformat(flight['flightDate'])
                    flights_summary.append(
                        f"Рейс {flight['flightNumber']} из {flight['origin']} в {flight['destination']} "
                        f"{flight_datetime.strftime('%Y-%m-%d %H:%M')} (Погода: {flight['weather']}, Темп: {flight['temperature']})"
                    )
                
                # Limit the number of flights sent to LLM to avoid context window issues
                if len(flights_summary) > 10:
                    flights_list_for_llm = "\n".join(flights_summary[:10]) + f"\n...и еще {len(flights_summary) - 10} рейсов."
                else:
                    flights_list_for_llm = "\n".join(flights_summary)

                llm_prompt = f"""
                Вы - полезный ассистент авиакомпании. Вам предоставлена информация о рейсах.
                Сформируйте дружелюбный и информативный ответ для пользователя, который запросил рейсы на даты
                с {date_from.isoformat()} по {date_to.isoformat()}.
                Включите в ответ список найденных рейсов, указывая номер рейса, маршрут, дату/время, погоду и температуру.

                Найденные рейсы:
                {flights_list_for_llm}

                Если рейсов не найдено, сообщите об этом.
                """
                print("Agent: Formatting response using Ollama...")
                response_ollama = ollama.generate(model=self.ollama_model, prompt=llm_prompt, options={'temperature': 0.3})
                response_text = response_ollama['response']
        else:
            response_text = "Извините, я не смог понять ваш запрос. Пожалуйста, уточните, какие рейсы вы ищете (по дате, номеру рейса или ID)."

        return response_text

# Main execution
if __name__ == "__main__":

    models = ollama.list()
    
    model_names = [model['name'] for model in models]

    if 'qwen3:0.6b' in model_names:
        print("Model 'qwen3:0.6b' exists in the list.")
    else:
        ollama.pull('qwen3:0.6b')
        print("Model 'qwen3:0.6b' does not exist in the list.")

    # Ensure your Ollama server is running and 'llama3' model is pulled.
    # Ensure your mcp_server.py is running on http://127.0.0.1:5000.
    
    agent = OllamaFlightAgent()

    # Example queries demonstrating multi-step reasoning and new features
    print(agent.process_query("Покажи мне рейсы на завтра."))
    print(agent.process_query("Какие рейсы есть на эту неделю?"))
    print(agent.process_query("Мне нужны рейсы с 2025-06-05 по 2025-06-07."))
    print(agent.process_query("Есть ли рейсы на следующий месяц?"))
    print(agent.process_query("Рейсы на сегодня."))
    
    # --- New queries for specific flight details ---
    # You might need to check your mcp_server.py output for actual flight IDs/numbers
    # or adjust the dummy data generation range to ensure flights exist.
    # For testing, you can temporarily hardcode an ID/number/date that you know exists.
    
    # Example: Assuming a flight with ID 1001 exists for today's date
    print(agent.process_query("Расскажи мне про рейс с ID 1001.")) 
    
    # Example: Assuming flight SU123 exists on today's date
    print(agent.process_query("Что известно про рейс SU123 на сегодня?"))
    
    # Example: Query for a non-existent flight
    print(agent.process_query("Покажи детали рейса BA999 на 2025-12-25."))

    print(agent.process_query("Найди рейсы на 2025-07-10."))
