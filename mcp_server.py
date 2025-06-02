# mcp_server.py
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import random

app = Flask(__name__)

# Global storage for simulated flights, generated once at startup
_all_simulated_flights = []

def generate_dummy_flights(start_date: datetime, end_date: datetime):
    """Generates dummy flight data for a given date range with weather info."""
    flights = []
    current_date = start_date
    flight_id_counter = 1000

    weather_conditions = ["Clear", "Cloudy", "Rainy", "Snowy", "Foggy", "Sunny"]
    
    while current_date <= end_date:
        num_flights_per_day = random.randint(3, 7) # 3 to 7 flights per day
        for _ in range(num_flights_per_day):
            flight_id_counter += 1
            # Generate random flight number
            airline_prefix = random.choice(['SU', 'KC', 'LH', 'TK', 'BA'])
            flight_number = f"{airline_prefix}{random.randint(100, 999)}"
            
            # Generate random origin/destination
            airports = ['ALA', 'MOW', 'DXB', 'IST', 'AMS', 'FRA', 'CDG', 'DEL', 'JFK', 'LHR']
            origin = random.choice(airports)
            destination = random.choice([a for a in airports if a != origin])

            # Generate random time within the day
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            flight_datetime = current_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Generate random weather and temperature
            weather = random.choice(weather_conditions)
            temperature = f"{random.randint(-10, 35)}°C" # Example temperature range

            flights.append({
                "flightId": flight_id_counter,
                "flightNumber": flight_number,
                "flightDate": flight_datetime.isoformat(), # ISO format for easy parsing
                "origin": origin,
                "destination": destination,
                "weather": weather,
                "temperature": temperature
            })
        current_date += timedelta(days=1)
    return flights

# Generate flights for a year range at server startup
# This allows /get/flight/details to look up specific flights consistently
_all_simulated_flights = generate_dummy_flights(
    datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=180), # 6 months back
    datetime.now().replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999) + timedelta(days=180) # 6 months forward
)
print(f"Generated {len(_all_simulated_flights)} dummy flights for simulation.")


@app.route('/get/flights/infos', methods=['POST'])
def get_flights_infos():
    """
    Endpoint to get simulated flight information based on a date range.
    Input: { "dateFrom": "YYYY-MM-DD", "dateTo": "YYYY-MM-DD" }
    Output: { "flights": array, "metadata": { "source": string, "freshness": string } }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON input"}), 400

    date_from_str = data.get('dateFrom')
    date_to_str = data.get('dateTo')

    if not date_from_str or not date_to_str:
        return jsonify({"error": "Missing 'dateFrom' or 'dateTo' in request"}), 400

    try:
        # Parse dates from string (assuming YYYY-MM-DD format)
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    # Ensure dateFrom is not after dateTo
    if date_from > date_to:
        return jsonify({"error": "'dateFrom' cannot be after 'dateTo'"}), 400
    
    # Filter flights from the pre-generated list
    filtered_flights = []
    for flight in _all_simulated_flights:
        flight_date_obj = datetime.fromisoformat(flight['flightDate']).date()
        if date_from <= flight_date_obj <= date_to:
            filtered_flights.append(flight)

    response_metadata = {
        "source": "Simulated Flight Schedule Database",
        "freshness": datetime.now().isoformat() # Indicates when this data was generated/retrieved
    }

    return jsonify({"flights": filtered_flights, "metadata": response_metadata}), 200

@app.route('/get/flight/details', methods=['POST'])
def get_flight_details():
    """
    Endpoint to get specific flight details by ID or by flight number and date.
    Input: { "flightId": int } OR { "flightNumber": string, "flightDate": "YYYY-MM-DD" }
    Output: { "flight": object, "metadata": { "source": string, "freshness": string } }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON input"}), 400

    flight_id = data.get('flightId')
    flight_number = data.get('flightNumber')
    flight_date_str = data.get('flightDate')

    found_flight = None

    if flight_id is not None:
        # Search by flightId
        for flight in _all_simulated_flights:
            if flight.get('flightId') == flight_id:
                found_flight = flight
                break
    elif flight_number and flight_date_str:
        # Search by flightNumber and flightDate
        try:
            target_date = datetime.strptime(flight_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({"error": "Invalid 'flightDate' format. Use YYYY-MM-DD"}), 400

        for flight in _all_simulated_flights:
            flight_date_obj = datetime.fromisoformat(flight['flightDate']).date()
            if flight.get('flightNumber') == flight_number and flight_date_obj == target_date:
                found_flight = flight
                break
    else:
        return jsonify({"error": "Provide either 'flightId' or 'flightNumber' and 'flightDate'"}), 400

    response_metadata = {
        "source": "Simulated Flight Schedule Database",
        "freshness": datetime.now().isoformat()
    }

    if found_flight:
        return jsonify({"flight": found_flight, "metadata": response_metadata}), 200
    else:
        return jsonify({"error": "Flight not found"}), 404

if __name__ == '__main__':
    # Run the server on localhost:5000
    # For production, use a more robust WSGI server like Gunicorn
    app.run(host='127.0.0.1', port=5000, debug=True)
