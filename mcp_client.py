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

    def get_flights_info(self, date_from: date, date_to: date, origin: Optional[str] = None, destination: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Calls the /get/flights/infos endpoint to retrieve flight information.
        Includes caching mechanism to avoid redundant API calls for the same parameters.

        Args:
            date_from: Start date for flight search (datetime.date object).
            date_to: End date for flight search (datetime.date object).
            origin: Optional origin city filter.
            destination: Optional destination city filter.

        Returns:
            A list of flight dictionaries on success, None on error.
            Each flight dict: { "flightNumber": string, "flightDate": string, "origin": string, "destination": string, "weather": string, "temperature": string }
        """
        endpoint_path = "/get/flights/infos"
        payload = {
            "dateFrom": date_from.isoformat(),  # Convert date object to YYYY-MM-DD string
            "dateTo": date_to.isoformat()
        }
        if origin:
            payload["origin"] = origin
        if destination:
            payload["destination"] = destination

        cache_key = self._get_cache_key(endpoint_path, payload)

        # 1. Check if the result is already in the cache
        if cache_key in self.cache:
            print(f"Cache hit for flights with params {payload}. Returning cached data.")
            return self.cache[cache_key]

        # If not in cache, proceed with API call
        full_endpoint_url = f"{self.base_url}{endpoint_path}"
        headers = {"Content-Type": "application/json"}

        try:
            print(f"Making API call to {full_endpoint_url} with params {payload}...")
            response = requests.post(full_endpoint_url, json=payload, headers=headers)
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            
            response_data = response.json()

            # Handle the case where the response is a list
            if isinstance(response_data, list):
                flights_data = response_data
            elif isinstance(response_data, dict):
                flights_data = response_data.get('flights', [])
            else:
                print(f"Unexpected response format: {response_data}")
                return None

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

    def get_flight_details(self,origin: Optional[str] = None,
                           destination: Optional[str] = None,
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
            Flight dict: { "flightNumber": string, "flightDate": string, "origin": string, "destination": string, "weather": string, "temperature": string }
        """
        endpoint_path = "/get/flight/details"
        payload = {}
        if flight_number and flight_date:
            payload['flightNumber'] = flight_number
            payload['flightDate'] = flight_date.isoformat()
        elif flight_date:
            payload['flightDate'] = flight_date.isoformat()
        
        #if  flight_date and origin and destination:
            #payload['flightNumber'] = None
            #payload['origin'] = origin
            #payload['destination'] = destination
            #payload['flightDate'] = flight_date.isoformat()

        else:
            print("Error: Either 'origin' and 'destination' and 'flightDate' or 'flightNumber' and 'flightDate' must be provided.")
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
            print(f"Response data: {response_data}")
            flight_details = response_data.get('flight') # Extract flight details from the response
            print(f"Flight details: {flight_details}")
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
    
    # Test get_flights_info with origin and destination filters
    today = date.today()
    tomorrow = today + timedelta(days=1)
    print(f"\nFetching flights from {today} to {tomorrow} with origin 'ALA' and destination 'DXB'...")
    flights = client.get_flights_info(today, tomorrow, origin="ALA", destination="DXB")
    if flights:
        print(f"Found {len(flights)} flights.")
    else:
        print("No flights found.")

