# mcp_client.py
import requests
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple, Union

class MCPClient:
    def __init__(self, base_url: str = "http://127.0.0.1:5000"):
        self.base_url = base_url
        # Initialize an in-memory cache for storing flight information
        # The key will be a tuple of (endpoint, date_from_iso, date_to_iso) or (endpoint, flight_id) etc.
        self.cache: Dict[Tuple, Union[List[Dict], Dict]] = {}
        print(f"MCPClient initialized with base URL: {self.base_url}")

    def _get_cache_key(self, endpoint: str, params: Dict) -> Tuple:
        """Generates a unique cache key from the endpoint and parameters."""
        # Sort params to ensure consistent cache key regardless of dict order
        sorted_params = tuple(sorted(params.items()))
        return (endpoint, sorted_params)

    def clear_cache(self):
        """Clears the entire cache."""
        self.cache = {}
        print("MCPClient cache cleared.")

    def get_flights_info(self, date_from: date, date_to: date) -> Optional[List[Dict]]:
        """
        Calls the /get/flights/infos endpoint to retrieve flight information.
        Includes caching mechanism to avoid redundant API calls for the same date range.

        Args:
            date_from: Start date for flight search (datetime.date object).
            date_to: End date for flight search (datetime.date object).

        Returns:
            A list of flight dictionaries on success, None on error.
            Each flight dict: { "flightId": int, "flightNumber": string, "flightDate": string, "origin": string, "destination": string, "weather": string, "temperature": string }
        """
        endpoint_path = "/get/flights/infos"
        payload = {
            "dateFrom": date_from.isoformat(), # Convert date object to YYYY-MM-DD string
            "dateTo": date_to.isoformat()
        }
        cache_key = self._get_cache_key(endpoint_path, payload)

        # 1. Check if the result is already in the cache
        if cache_key in self.cache:
            print(f"Cache hit for flights from {date_from.isoformat()} to {date_to.isoformat()}. Returning cached data.")
            return self.cache[cache_key]

        # If not in cache, proceed with API call
        full_endpoint_url = f"{self.base_url}{endpoint_path}"
        headers = {"Content-Type": "application/json"}

        try:
            print(f"Making API call to {full_endpoint_url} for dates {date_from.isoformat()} to {date_to.isoformat()}...")
            response = requests.post(full_endpoint_url, json=payload, headers=headers)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            
            response_data = response.json()
            flights_data = response_data.get('flights') # Extract flights from the new response structure
            metadata = response_data.get('metadata') # Extract metadata

            if metadata:
                print(f"Metadata for /get/flights/infos: Source - {metadata.get('source')}, Freshness - {metadata.get('freshness')}")
            
            # 2. Store the successful response in the cache (store only the flights data)
            self.cache[cache_key] = flights_data
            print(f"Successfully fetched and cached {len(flights_data)} flights.")
            return flights_data
        except requests.exceptions.ConnectionError as e:
            print(f"Error: Could not connect to MCP server at {self.base_url}. Is it running? {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error calling MCP server: {e}")
            if response:
                print(f"Server response: {response.status_code} - {response.text}")
            return None

    def get_flight_details(self, flight_id: Optional[int] = None, 
                           flight_number: Optional[str] = None, 
                           flight_date: Optional[date] = None) -> Optional[Dict]:
        """
        Calls the /get/flight/details endpoint to retrieve specific flight information.
        Includes caching mechanism.

        Args:
            flight_id: The ID of the flight.
            flight_number: The flight number (e.g., "SU123").
            flight_date: The date of the flight (datetime.date object).

        Returns:
            A dictionary of flight details on success, None on error.
            Flight dict: { "flightId": int, "flightNumber": string, "flightDate": string, "origin": string, "destination": string, "weather": string, "temperature": string }
        """
        endpoint_path = "/get/flight/details"
        payload = {}
        if flight_id is not None:
            payload['flightId'] = flight_id
        elif flight_number and flight_date:
            payload['flightNumber'] = flight_number
            payload['flightDate'] = flight_date.isoformat()
        else:
            print("Error: Either 'flightId' or 'flightNumber' and 'flightDate' must be provided.")
            return None

        cache_key = self._get_cache_key(endpoint_path, payload)

        # 1. Check if the result is already in the cache
        if cache_key in self.cache:
            print(f"Cache hit for flight details with params {payload}. Returning cached data.")
            return self.cache[cache_key]

        # If not in cache, proceed with API call
        full_endpoint_url = f"{self.base_url}{endpoint_path}"
        headers = {"Content-Type": "application/json"}

        try:
            print(f"Making API call to {full_endpoint_url} for details with params {payload}...")
            response = requests.post(full_endpoint_url, json=payload, headers=headers)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            
            response_data = response.json()
            flight_details = response_data.get('flight') # Extract flight details from the new response structure
            metadata = response_data.get('metadata') # Extract metadata

            if metadata:
                print(f"Metadata for /get/flight/details: Source - {metadata.get('source')}, Freshness - {metadata.get('freshness')}")

            # 2. Store the successful response in the cache (store only the flight details)
            self.cache[cache_key] = flight_details
            print(f"Successfully fetched and cached flight details.")
            return flight_details
        except requests.exceptions.ConnectionError as e:
            print(f"Error: Could not connect to MCP server at {self.base_url}. Is it running? {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error calling MCP server for flight details: {e}")
            if response:
                print(f"Server response: {response.status_code} - {response.text}")
            return None

# Example usage (for testing the client independently)
if __name__ == "__main__":
    client = MCPClient()
    
    # --- Test get_flights_info with caching ---
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    print(f"\n--- First fetch for flights from {today} to {tomorrow} ---")
    flights_1 = client.get_flights_info(today, tomorrow)
    if flights_1:
        print(f"Found {len(flights_1)} flights in first fetch.")
    else:
        print("Failed to retrieve flights in first fetch.")

    print(f"\n--- Second fetch for flights from {today} to {tomorrow} (should be cached) ---")
    flights_2 = client.get_flights_info(today, tomorrow)
    if flights_2:
        print(f"Found {len(flights_2)} flights in second fetch (from cache).")
    else:
        print("Failed to retrieve flights in second fetch.")

    # --- Test get_flight_details with caching ---
    print("\n--- Fetching specific flight details by ID (first time) ---")
    # Assuming some flight ID exists from dummy data, e.g., 1001 for a flight today
    # You might need to run mcp_server.py first to see generated IDs
    
    # A simple way to get a sample flight ID and number/date from the dummy data
    # In a real scenario, you'd get this from a previous 'get_flights_info' call or user input
    sample_flight_id = None
    sample_flight_number = None
    sample_flight_date = None
    if flights_1 and len(flights_1) > 0:
        sample_flight_id = flights_1[0]['flightId']
        sample_flight_number = flights_1[0]['flightNumber']
        sample_flight_date = datetime.fromisoformat(flights_1[0]['flightDate']).date()
        print(f"Using sample flight: ID={sample_flight_id}, Number={sample_flight_number}, Date={sample_flight_date}")

    if sample_flight_id:
        flight_details_1_id = client.get_flight_details(flight_id=sample_flight_id)
        if flight_details_1_id:
            print(f"Found flight details by ID: {flight_details_1_id.get('flightNumber')} from {flight_details_1_id.get('origin')} to {flight_details_1_id.get('destination')} on {flight_details_1_id.get('flightDate')}")
        else:
            print("Failed to retrieve flight details by ID.")

        print("\n--- Fetching specific flight details by ID (second time, should be cached) ---")
        flight_details_2_id = client.get_flight_details(flight_id=sample_flight_id)
        if flight_details_2_id:
            print(f"Found flight details by ID (from cache): {flight_details_2_id.get('flightNumber')}")
        else:
            print("Failed to retrieve flight details by ID (from cache).")
    
    if sample_flight_number and sample_flight_date:
        print("\n--- Fetching specific flight details by Number/Date (first time) ---")
        flight_details_1_num_date = client.get_flight_details(flight_number=sample_flight_number, flight_date=sample_flight_date)
        if flight_details_1_num_date:
            print(f"Found flight details by Number/Date: {flight_details_1_num_date.get('flightNumber')} from {flight_details_1_num_date.get('origin')} to {flight_details_1_num_date.get('destination')} on {flight_details_1_num_date.get('flightDate')}")
        else:
            print("Failed to retrieve flight details by Number/Date.")

        print("\n--- Fetching specific flight details by Number/Date (second time, should be cached) ---")
        flight_details_2_num_date = client.get_flight_details(flight_number=sample_flight_number, flight_date=sample_flight_date)
        if flight_details_2_num_date:
            print(f"Found flight details by Number/Date (from cache): {flight_details_2_num_date.get('flightNumber')}")
        else:
            print("Failed to retrieve flight details by Number/Date (from cache).")

    # --- Clear cache and re-test ---
    print("\n--- Clearing cache and re-fetching to demonstrate API call after clearing ---")
    client.clear_cache()
    flights_after_clear = client.get_flights_info(today, tomorrow)
    if flights_after_clear:
        print(f"Found {len(flights_after_clear)} flights after clearing cache.")
    else:
        print("Failed to retrieve flights after clearing cache.")

