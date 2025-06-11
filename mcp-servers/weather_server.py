from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="WeatherServer", stateless_http=True)


@mcp.tool(description="Tool to get a wether for today in different countries", name="weather_server")
def echo(city_name: str) -> str:
    return f"Here can be used API call to get weather in {city_name} for today. This is a mock response."




if __name__ == "__main__":
    mcp.run()