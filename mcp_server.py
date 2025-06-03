# mcp_server.py
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import random

app = Flask(__name__)

# Simulated flight data generation
def generate_dummy_flights(date_from, date_to):
    """Generates dummy flight data for a given date range."""
    flights = []
    current_date = date_from
    flight_id_counter = 1000

    # Example weather and temperature data
    weather_conditions = ['Sunny', 'Cloudy', 'Rainy', 'Snowy', 'Windy']
    temperature_range = {'min': -10, 'max': 35}  # Temperature range in Celsius

    while current_date <= date_to:
        num_flights_per_day = random.randint(3, 7)  # 3 to 7 flights per day
        for _ in range(num_flights_per_day):
            flight_id_counter += 1
            # Generate random flight number
            flight_number = f"{random.choice(['SS', 'KC', 'LH', 'TK'])}{random.randint(100, 999)}"
            
            # Generate random origin/destination
            airports = ['ALA', 'MOW', 'DXB', 'IST', 'AMS', 'FRA', 'CDG', 'DEL']
            origin = random.choice(airports)
            destination = random.choice([a for a in airports if a != origin])

            # Generate random time within the day
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            flight_datetime = current_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Generate random weather and temperature
            weather = random.choice(weather_conditions)
            temperature = f"{random.randint(temperature_range['min'], temperature_range['max'])}°C"

            flights.append({
                "flightId": flight_id_counter,
                "flightNumber": flight_number,
                "flightDate": flight_datetime.isoformat(),  # ISO format for easy parsing
                "origin": origin,
                "destination": destination,
                "weather": weather,
                "temperature": temperature
            })
        current_date += timedelta(days=1)
    return flights

@app.route('/get/flights/infos', methods=['POST'])
def get_flights_infos():
    """
    Endpoint to get simulated flight information based on a date range and optional city filters.
    Input: { "dateFrom": "YYYY-MM-DD", "dateTo": "YYYY-MM-DD", "origin": "CityCode", "destination": "CityCode" }
    Output: array of { "flightId": int, "flightNumber": string, "flightDate": datetime, "origin": string, "destination": string }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON input"}), 400

    date_from_str = data.get('dateFrom')
    date_to_str = data.get('dateTo')
    origin_filter = data.get('origin')  # Optional origin city filter
    destination_filter = data.get('destination')  # Optional destination city filter

    if not date_from_str or not date_to_str:
        return jsonify({"error": "Missing 'dateFrom' or 'dateTo' in request"}), 400

    try:
        # Parse dates from string (assuming YYYY-MM-DD format)
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    # Ensure dateFrom is not after dateTo
    if date_from > date_to:
        return jsonify({"error": "'dateFrom' cannot be after 'dateTo'"}), 400

    # Simulate fetching data
    flights = generate_dummy_flights(date_from, date_to)

    # Apply filters for origin and destination if provided
    if origin_filter:
        flights = [flight for flight in flights if flight['origin'].lower() == origin_filter.lower()]
    if destination_filter:
        flights = [flight for flight in flights if flight['destination'].lower() == destination_filter.lower()]

    return jsonify(flights), 200

@app.route('/get/flight/details', methods=['POST'])
def get_flight_details():
    """
    Endpoint to get specific flight details based on flight number and date or origin, destination, and date.
    Input: { "flightNumber": "SU123", "flightDate": "YYYY-MM-DD" }
           OR { "origin": "CityCode", "destination": "CityCode", "flightDate": "YYYY-MM-DD" }
    Output: { "flightId": int, "flightNumber": string, "flightDate": datetime, "origin": string, "destination": string, "weather": string, "temperature": string }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON input"}), 400

    flight_number = data.get('flightNumber')
    flight_date_str = data.get('flightDate')
    origin = data.get('origin')
    destination = data.get('destination')

    if not flight_date_str:
        return jsonify({"error": "Missing 'flightDate' in request"}), 400

    try:
        # Parse flight date from string
        flight_date = datetime.strptime(flight_date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    # Simulate fetching data
    flights = generate_dummy_flights(flight_date, flight_date)

    # Filter by flight number and date
    if flight_number:
        flights = [flight for flight in flights if flight['flightNumber'] == flight_number]

    # Filter by origin, destination, and date
    elif origin and destination:
        flights = [flight for flight in flights if flight['origin'] == origin and flight['destination'] == destination]

    else:
        return jsonify({"error": "Either 'flightNumber' or 'origin' and 'destination' must be provided"}), 400

    if not flights:
        return jsonify({"error": "No flight found matching the criteria"}), 404

    # Add simulated weather and temperature data
    for flight in flights:
        flight['weather'] = "Sunny"  # Example weather data
        flight['temperature'] = "25°C"  # Example temperature data

    # Return the first matching flight (assuming one match is sufficient)
    return jsonify(flights[0]), 200


if __name__ == '__main__':
    # Run the server on localhost:5000
    # For production, use a more robust WSGI server like Gunicorn
    app.run(host='127.0.0.1', port=5000, debug=False)
