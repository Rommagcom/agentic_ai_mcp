from flask import Flask, request, jsonify
import ollama
from datetime import datetime, date, timedelta
from mcp_client import MCPClient  # Import our custom client
from typing import List, Dict, Optional, Tuple, Union

# Initialize Flask app
app = Flask(__name__)

class OllamaFlightAgent:
    def __init__(self, ollama_model: str = "qwen3:0.6b", mcp_base_url: str = "http://127.0.0.1:5000", ollama_base_url: str = "http://127.0.0.1:11434"):
        self.ollama_model = ollama_model
        self.mcp_client = MCPClient(mcp_base_url)
        self.ollama_base_url = ollama_base_url

        # Check if the model exists, and pull it if necessary
        models = ollama.list()  # Get the list of models
        if isinstance(models, list):  # Ensure models is a list
            model_names = [model['name'] for model in models if isinstance(model, dict)]
        else:
            print("Unexpected response from ollama.list(). Ensure the library is working correctly.")
            model_names = []

        if self.ollama_model in model_names:
            print(f"Model '{self.ollama_model}' exists in the list.")
        else:
            print(f"Model '{self.ollama_model}' does not exist. Pulling the model...")
            ollama.pull(self.ollama_model)  # Pull the model if it doesn't exist
            print(f"Model '{self.ollama_model}' has been pulled successfully.")

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

        If a specific flight number - is alpha numeric value and date are mentioned (e.g., "рейс SU123 на 2025-06-05"), extract 'flightNumber' and 'flightDate'.

        If a specific cities are mentioned (e.g., "из Алматы в Астану"), convert it to aitport code and extract 'origin' and 'destination'.
        If both origin and destination details and date ranges are present, prioritize over all.
        If only a date range is specified, extract 'dateFrom' and 'dateTo'.
        Prioritize specific flight details (ID or number/date) over date ranges if both are present.
        If no specific flight details or date range is specified, assume today as the date range.

        Output the extracted parameters in JSON format like this
        example outputs:
        {{"dateFrom": "YYYY-MM-DD", "dateTo": "YYYY-MM-DD"}}
        {{"flightNumber": "KC851", "flightDate": "YYYY-MM-DD"}}
        {{"origin": "", destination": "ALA"
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
        """Processes a user query to get flight information using multi-step reasoning."""
        print(f"\nUser: {user_query}")
        print("Agent: Extracting query parameters using Ollama...")
        params = self._extract_query_parameters(user_query)
        print(f"Agent: Detected parameters: {params}")

        # Check if sufficient parameters are provided for specific flight details
        if 'flightNumber' in params and 'flightDate' in params and params['flightNumber'] and params['flightDate']:
            return self._get_flight_details(params)
        elif 'origin' in params and 'destination' in params and 'flightDate' in params and params['origin'] and params['destination'] and params['flightDate']:
            return self._get_flight_details(params)
        elif 'dateFrom' in params and 'dateTo' in params:
            # If only a date range is provided, fetch flights for the date range
            return self._get_flights_by_date_range(params)
        else:
            return "Извините, я не смог понять ваш запрос. Пожалуйста, уточните, какие рейсы вы ищете (по дате, номеру рейса, городу отправления или назначения)."

    def _get_flight_details(self, params: Dict) -> str:
        """Fetches specific flight details from the MCP server."""
        flight_number = params.get('flightNumber')
        flight_date = params.get('flightDate')
        origin = params.get('origin')
        destination = params.get('destination')

        if flight_number and flight_date:
            print(f"Agent: Fetching flight details for Number: {flight_number}, Date: {flight_date}...")
            flight_data = self.mcp_client.get_flight_details(flight_number=flight_number, flight_date=flight_date)
        elif origin and destination and flight_date:
            print(f"Agent: Fetching flight details for Origin: {origin}, Destination: {destination}, Date: {flight_date}...")
            flight_data = self.mcp_client.get_flight_details(origin=origin, destination=destination, flight_date=flight_date)
        else:
            return "Недостаточно данных для поиска рейса. Укажите номер рейса и дату или город отправления, назначения и дату."

        if flight_data:
            flight_datetime = datetime.fromisoformat(flight_data['flightDate'])
            return f"""
            Информация о рейсе {flight_data['flightNumber']} (ID: {flight_data['flightId']}):
            Маршрут: {flight_data['origin']} -> {flight_data['destination']}
            Дата и время: {flight_datetime.strftime('%Y-%m-%d %H:%M')}
            Погода в пункте назначения: {flight_data['weather']}, Температура: {flight_data['temperature']}
            """
        else:
            return "Извините, не удалось найти информацию по указанному рейсу. Пожалуйста, проверьте данные и попробуйте снова."

    def _get_flights_by_date_range(self, params: Dict) -> str:
        """
        Retrieves flights information for a specific date range from the MCP server.
        """
        date_from = params['dateFrom']
        date_to = params['dateTo']
        origin = params.get('origin')
        destination = params.get('destination')

        print(f"Agent: User requested flights for a date range. Calling MCP server for general info...")
        flights_data = self.mcp_client.get_flights_info(date_from, date_to, origin, destination)

        if not flights_data:
            return f"На период с {date_from.isoformat()} по {date_to.isoformat()} рейсов не найдено."

        # Prepare flight data for LLM
        flights_summary = []
        for flight in flights_data:
            flight_datetime = datetime.fromisoformat(flight.get('flightDate', '1970-01-01T00:00:00'))
            weather = flight.get('weather', 'неизвестно')  # Fallback to 'неизвестно' if 'weather' is missing
            temperature = flight.get('temperature', 'неизвестно')  # Fallback to 'неизвестно' if 'temperature' is missing
            flights_summary.append(
                f"Рейс {flight.get('flightNumber', 'неизвестно')} из {flight.get('origin', 'неизвестно')} "
                f"в {flight.get('destination', 'неизвестно')} {flight_datetime.strftime('%Y-%m-%d %H:%M')} "
                f"(Погода: {weather}, Темп: {temperature})"
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
        response_ollama = ollama.generate(model=self.ollama_model, prompt=llm_prompt, options={'temperature': 0.6})
        return response_ollama.get('response', "Ошибка при форматировании ответа.")

# Flask route to handle queries
@app.route('/query', methods=['POST'])
def query():
    data = request.json
    user_query = data.get('query', '')
    if not user_query:
        return jsonify({"error": "Query is required"}), 400

    agent = OllamaFlightAgent()
    response = agent.process_query(user_query)
    # Extract text after </think>
    if "</think>" in response:
        response = response.split("</think>", 1)[1].strip()

    return jsonify({"response": response})
    

# Run the Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
