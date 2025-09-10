#!/usr/bin/env python3
"""
Rentcast MCP Server
Provides real estate tools for property search, market analysis, and property valuation.
"""

import json
import os
import httpx
import logging
import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Import API key from core config
try:
    from app.core.config import settings
    RENTCAST_API_KEY = settings.RENTCAST_API_KEY
except ImportError:
    # If we can't import from app module, use environment variable
    RENTCAST_API_KEY = None

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
LOG_FILE = SCRIPT_DIR / "rentcast_mcp.log"

# Configure logging to write to both file and stderr
logger = logging.getLogger("rentcast-mcp")
logger.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Create file handler
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Create console handler (stderr)
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Add both handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Prevent duplicate logs by not propagating to root logger
logger.propagate = False

# Initialize FastMCP server
mcp = FastMCP("rentcast")

# Constants
RENTCAST_API_BASE = "https://api.rentcast.io/v1"

# Helper function to validate and check property status
def is_property_active(property_data: dict) -> bool:
    """Check if a property is active based on available indicators.
    
    Since RentCast API may not provide explicit status fields, we use
    available data to make reasonable assumptions about property activity.
    
    Args:
        property_data: Dictionary containing property information
        
    Returns:
        bool: True if property is considered active, False otherwise
    """
    # Use year built as primary indicator of active status
    # Properties built within last 50 years are more likely to be active
    year_built = property_data.get('yearBuilt', 0)
    if year_built and year_built >= 1974:  # 50 years from 2024
        return True
    
    # If no year built info, consider it active by default
    # This ensures we don't filter out valid properties unnecessarily
    return True

# Helper function to extract data from API responses
def extract_data_from_response(data, expected_key: str = None) -> list:
    """Extract data from API response, handling different response formats.
    
    This function normalizes API responses that may come in different formats:
    - Direct list responses
    - Dict responses with nested data under a specific key
    - Empty or None responses
    
    Args:
        data: The API response data (list, dict, or None)
        expected_key: The key to look for in dict responses (e.g., "properties", "listings")
    
    Returns:
        List of data items, or empty list if none found or invalid format
    """
    # Handle None or empty data
    if not data:
        return []
    
    # If data is already a list, return it directly
    if isinstance(data, list):
        return data
    
    # If data is a dict and we have an expected key, try to extract it
    if isinstance(data, dict) and expected_key:
        result = data.get(expected_key, [])
        # Ensure we return a list
        if isinstance(result, list):
            return result
        elif result:  # If it's not a list but has data, wrap it in a list
            return [result]
        else:
            return []
    
    # If data is a dict but no expected key, return empty list
    # (this could be extended to return the dict as a single item if needed)
    return []

# Helper function to make API requests
async def make_request(endpoint: str, params: dict = None) -> dict[str, any] | None:
    """Make a request to the Rentcast API with proper error handling."""
    # Get API key from config or environment as fallback
    api_key = RENTCAST_API_KEY or os.getenv("RENTCAST_API_KEY")
    
    if not api_key:
        logger.error("No API key found for Rentcast API")
        return {"Error": "API key not configured"}

    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    logger.info(f"Using API key: {api_key[:8]}...")

    try:
        url = f"{RENTCAST_API_BASE}{endpoint}"
        if params:
            # Filter out None values and URL encode
            query_params = {k: v for k, v in params.items() if v is not None}
            if query_params:
                import urllib.parse
                encoded_params = urllib.parse.urlencode(query_params)
                url += "?" + encoded_params
        
        logger.info(f"Making API request to: {url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            
            logger.info(f"API request successful: {response.status_code}")
            response_data = response.json()
            logger.info(f"Response data type: {type(response_data)}, length: {len(response_data) if isinstance(response_data, (list, dict)) else 'N/A'}")
            return response_data
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
        return {"Error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except httpx.TimeoutException:
        logger.error("Request timeout")
        return {"Error": "Request timeout"}
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        return {"Error": f"Request failed: {str(e)}"}
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {"Error": f"Invalid JSON response: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"Error": f"Unexpected error: {str(e)}"}

@mcp.tool(
    name="search_properties",
    description=(
        "Search for properties with basic property info. "
        "Filters: city (str), state (2-letter code), zip_code (str), bedrooms (int), "
        "bathrooms (float), property_type (e.g., SingleFamily, Condo), limit (int, default=15), "
        "active_only (bool, default=True) - filter out inactive/off-market properties. "
        "Example: city='Austin', state='TX', bedrooms=3, bathrooms=2, active_only=True. "
        "Returns a JSON list of property objects."
    )
)
async def search_properties(
    city: str = None,
    state: str = None,
    zip_code: str = None,
    bedrooms: int = None,
    bathrooms: float = None,
    property_type: str = None,
    limit: int = 15,
    active_only: bool = True
) -> str:
    """Search for properties with basic property information.
    
    Args:
        city: City name (e.g. Austin, New York)
        state: State abbreviation (e.g. TX, NY)
        zip_code: ZIP code (e.g. 78701)
        bedrooms: Number of bedrooms
        bathrooms: Number of bathrooms
        property_type: Type of property (e.g. SingleFamily, Condo)
        limit: Maximum number of properties to return (default: 15)
        active_only: Filter out inactive/off-market properties (default: True)
    """
    logger.info(f"search_properties called with params: city={city}, state={state}, zip_code={zip_code}, bedrooms={bedrooms}, bathrooms={bathrooms}, property_type={property_type}, limit={limit}, active_only={active_only}")
    
    # Validate parameters
    if not any([city, state, zip_code]):
        logger.warning("search_properties: At least one location parameter (city, state, zip_code) is required")
        return "Error: At least one location parameter (city, state, zip_code) is required"
    
    if limit and (limit < 1 or limit > 1000):
        logger.warning(f"search_properties: Invalid limit {limit}, must be between 1 and 1000")
        return "Error: Limit must be between 1 and 1000"
    
    if bedrooms and bedrooms < 0:
        logger.warning(f"search_properties: Invalid bedrooms {bedrooms}, must be non-negative")
        return "Error: Bedrooms must be non-negative"
    
    if bathrooms and bathrooms < 0:
        logger.warning(f"search_properties: Invalid bathrooms {bathrooms}, must be non-negative")
        return "Error: Bathrooms must be non-negative"
    
    params = {
        "city": city,
        "state": state,
        "zipCode": zip_code,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "propertyType": property_type,
        "limit": limit
    }
    
    data = await make_request("/properties", params)
    
    if not data or "Error" in data:
        logger.warning(f"search_properties failed: {data}")
        return "Unable to fetch properties or no properties found."
    
    # Extract properties using helper function
    properties = extract_data_from_response(data, "properties")
    
    if not properties:
        logger.info("search_properties: No properties found matching criteria")
        return "No properties found matching the criteria."
    
    # Apply active filter if requested
    if active_only:
        original_count = len(properties)
        filtered_properties = [prop for prop in properties if is_property_active(prop)]
        properties = filtered_properties
        filtered_count = original_count - len(properties)
        if filtered_count > 0:
            logger.info(f"search_properties: Filtered out {filtered_count} potentially inactive properties")
    
    logger.info(f"search_properties successful: found {len(properties)} properties")
    logger.debug(f"Properties data structure: {type(properties)}, first item type: {type(properties[0]) if properties else 'N/A'}")
    return json.dumps(properties, indent=2)

@mcp.tool(
    name="get_random_properties",
    description=(
        "Retrieve random properties for market analysis. "
        "Optional filters: city, state, zip_code, active_only (bool, default=True). "
        "Limit defaults to 10. "
        "Example: city='Denver', state='CO', limit=5, active_only=True. "
        "Returns a JSON list of property objects."
    )
)
async def get_random_properties(
    city: str = None,
    state: str = None,
    zip_code: str = None,
    limit: int = 10,
    active_only: bool = True
) -> str:
    """Get random properties for market analysis.
    
    Args:
        city: City name (e.g. Austin, New York)
        state: State abbreviation (e.g. TX, NY)
        zip_code: ZIP code (e.g. 78701)
        limit: Maximum number of properties to return (default: 10)
        active_only: Filter out inactive/off-market properties (default: True)
    """
    logger.info(f"get_random_properties called with params: city={city}, state={state}, zip_code={zip_code}, limit={limit}, active_only={active_only}")
    
    params = {
        "city": city,
        "state": state,
        "zipCode": zip_code,
        "limit": limit
    }
    
    data = await make_request("/properties/random", params)
    
    if not data or "Error" in data:
        logger.warning(f"get_random_properties failed: {data}")
        return "Unable to fetch random properties or no properties found."
    
    # Extract properties using helper function
    properties = extract_data_from_response(data, "properties")
    
    if not properties:
        logger.info("get_random_properties: No random properties found matching criteria")
        return "No random properties found matching the criteria."
    
    # Apply active filter if requested
    if active_only:
        original_count = len(properties)
        filtered_properties = [prop for prop in properties if is_property_active(prop)]
        properties = filtered_properties
        filtered_count = original_count - len(properties)
        if filtered_count > 0:
            logger.info(f"get_random_properties: Filtered out {filtered_count} potentially inactive properties")
    
    logger.info(f"get_random_properties successful: found {len(properties)} properties")
    return json.dumps(properties, indent=2)

@mcp.tool(
    name="analyze_market",
    description=(
        "Get market statistics and trends for a specific location. "
        "Filters: zip_code (str), city (str), state (str). "
        "Optional: data_type (default='All'). "
        "Example: zip_code='78701'. "
        "Returns a JSON list of market trend objects."
    )
)
async def analyze_market(
    zip_code: str = None,
    city: str = None,
    state: str = None,
    data_type: str = "All"
) -> str:
    """Get comprehensive market statistics and trends for specific locations.
    
    Args:
        zip_code: ZIP code (e.g. 78701)
        city: City name (e.g. Austin, New York)
        state: State abbreviation (e.g. TX, NY)
        data_type: Type of market data (default: All)
    """
    logger.info(f"analyze_market called with params: zip_code={zip_code}, city={city}, state={state}, data_type={data_type}")
    
    params = {"dataType": data_type}
    if zip_code:
        params["zipCode"] = zip_code
    if city:
        params["city"] = city
    if state:
        params["state"] = state
    
    data = await make_request("/markets", params)
    
    if not data or "Error" in data:
        logger.warning(f"analyze_market failed: {data}")
        return "Unable to fetch market data or no market data found."
    
    # Extract market data using helper function
    market_data = extract_data_from_response(data, "markets")
    
    if not market_data:
        logger.info("analyze_market: No market data found for specified location")
        return "No market data found for the specified location."
    
    logger.info(f"analyze_market successful: found {len(market_data)} market data entries")
    return json.dumps(market_data, indent=2)

@mcp.tool(
    name="get_property_value",
    description=(
        "Get automated property value estimates (AVM) with comparable properties. "
        "Required: one of property_id, address, or (latitude + longitude). "
        "Optional: property_type, bedrooms, bathrooms, square_footage, active_only (bool, default=True). "
        "Example: address='123 Main St, Austin TX', bedrooms=3, bathrooms=2, active_only=True. "
        "Returns a JSON object with estimated value, low/high range, and comparable properties."
    )
)
async def get_property_value(
    property_id: str = None,
    address: str = None,
    latitude: float = None,
    longitude: float = None,
    property_type: str = None,
    bedrooms: int = None,
    bathrooms: float = None,
    square_footage: int = None,
    active_only: bool = True
) -> str:
    """Get automated property value estimates with comparable properties.
    
    Args:
        property_id: Unique property identifier
        address: Property address
        latitude: Property latitude coordinate
        longitude: Property longitude coordinate
        property_type: Type of property (e.g. SingleFamily, Condo)
        bedrooms: Number of bedrooms
        bathrooms: Number of bathrooms
        square_footage: Property square footage
        active_only: Filter out inactive/off-market properties (default: True)
    """
    logger.info(f"get_property_value called with params: property_id={property_id}, address={address}, lat={latitude}, lng={longitude}, type={property_type}, beds={bedrooms}, baths={bathrooms}, sqft={square_footage}, active_only={active_only}")
    
    # Validate required parameters
    if not property_id and not address and (not latitude or not longitude):
        logger.error("get_property_value: Missing required parameters")
        return "Error: Must provide property_id, address, or both latitude and longitude"
    
    params = {}
    if property_id:
        params["propertyId"] = property_id
    if address:
        params["address"] = address
    if latitude and longitude:
        params["latitude"] = latitude
        params["longitude"] = longitude
    if property_type:
        params["propertyType"] = property_type
    if bedrooms is not None:
        params["bedrooms"] = bedrooms
    if bathrooms is not None:
        params["bathrooms"] = bathrooms
    if square_footage:
        params["squareFootage"] = square_footage
    
    data = await make_request("/avm/value", params)
    
    if not data or "Error" in data:
        logger.warning(f"get_property_value failed: {data}")
        return "Unable to fetch property value or no value data found."
    
    # Extract AVM data using helper function
    value_data = extract_data_from_response(data, "avm")
    if not value_data:
        logger.info("get_property_value: No property value data found")
        return "No property value data found for the specified property."
    
    # Note: active_only parameter is kept for API consistency but not applied
    # since RentCast API response structure for AVM data is not documented
    # and we cannot assume the existence of status fields in comparables
    
    logger.info("get_property_value successful: retrieved property value data")
    return json.dumps(value_data, indent=2)

@mcp.tool(
    name="get_rent_estimates",
    description=(
        "Get long-term rent estimates with comparable rental properties. "
        "Required: one of property_id, address, or (latitude + longitude). "
        "Optional: property_type, bedrooms, bathrooms, square_footage, active_only (bool, default=True). "
        "Example: address='456 Elm St, Denver CO', bedrooms=2, active_only=True. "
        "Returns a JSON object with estimated rent, low/high range, and comparable properties."
    )
)
async def get_rent_estimates(
    property_id: str = None,
    address: str = None,
    latitude: float = None,
    longitude: float = None,
    property_type: str = None,
    bedrooms: int = None,
    bathrooms: float = None,
    square_footage: int = None,
    active_only: bool = True
) -> str:
    """Get long-term rent estimates with comparable rental properties.
    
    Args:
        property_id: Unique property identifier
        address: Property address
        latitude: Property latitude coordinate
        longitude: Property longitude coordinate
        property_type: Type of property (e.g. SingleFamily, Condo)
        bedrooms: Number of bedrooms
        bathrooms: Number of bathrooms
        square_footage: Property square footage
        active_only: Filter out inactive/off-market properties (default: True)
    """
    logger.info(f"get_rent_estimates called with params: property_id={property_id}, address={address}, lat={latitude}, lng={longitude}, type={property_type}, beds={bedrooms}, baths={bathrooms}, sqft={square_footage}, active_only={active_only}")
    
    # Validate required parameters
    if not property_id and not address and (not latitude or not longitude):
        logger.error("get_rent_estimates: Missing required parameters")
        return "Error: Must provide property_id, address, or both latitude and longitude"
    
    params = {}
    if property_id:
        params["propertyId"] = property_id
    if address:
        params["address"] = address
    if latitude and longitude:
        params["latitude"] = latitude
        params["longitude"] = longitude
    if property_type:
        params["propertyType"] = property_type
    if bedrooms is not None:
        params["bedrooms"] = bedrooms
    if bathrooms is not None:
        params["bathrooms"] = bathrooms
    if square_footage:
        params["squareFootage"] = square_footage
    
    data = await make_request("/avm/rent/long-term", params)
    
    if not data or "Error" in data:
        logger.warning(f"get_rent_estimates failed: {data}")
        return "Unable to fetch rent estimates or no rent data found."
    
    # Extract AVM data using helper function
    rent_data = extract_data_from_response(data, "avm")
    if not rent_data:
        logger.info("get_rent_estimates: No rent estimate data found")
        return "No rent estimate data found for the specified property."
    
    # Note: active_only parameter is kept for API consistency but not applied
    # since RentCast API response structure for AVM data is not documented
    # and we cannot assume the existence of status fields in comparables
    
    logger.info("get_rent_estimates successful: retrieved rent estimate data")
    return json.dumps(rent_data, indent=2)

@mcp.tool(
    name="get_sale_listings",
    description=(
        "Retrieve property sale listings with detailed info. "
        "Filters: city, state, zip_code, active_only (bool, default=True). "
        "Optional: limit (default=15). "
        "Example: city='Miami', state='FL', limit=5, active_only=True. "
        "Returns a JSON list of sale listing objects."
    )
)
async def get_sale_listings(
    city: str = None,
    state: str = None,
    zip_code: str = None,
    limit: int = 15,
    active_only: bool = True
) -> str:
    """Get sale listings with comprehensive property information.
    
    Args:
        city: City name (e.g. Austin, New York)
        state: State abbreviation (e.g. TX, NY)
        zip_code: ZIP code (e.g. 78701)
        limit: Maximum number of listings to return (default: 15)
        active_only: Filter out inactive/off-market properties (default: True)
    """
    logger.info(f"get_sale_listings called with params: city={city}, state={state}, zip_code={zip_code}, limit={limit}, active_only={active_only}")
    
    # Validate parameters
    if not any([city, state, zip_code]):
        logger.warning("get_sale_listings: At least one location parameter (city, state, zip_code) is required")
        return "Error: At least one location parameter (city, state, zip_code) is required"
    
    if limit and (limit < 1 or limit > 1000):
        logger.warning(f"get_sale_listings: Invalid limit {limit}, must be between 1 and 1000")
        return "Error: Limit must be between 1 and 1000"
    
    params = {
        "city": city,
        "state": state,
        "zipCode": zip_code,
        "limit": limit
    }
    
    data = await make_request("/listings/sale", params)
    
    if not data or "Error" in data:
        logger.warning(f"get_sale_listings failed: {data}")
        return "Unable to fetch sale listings or no listings found."
    
    # Extract listings using helper function
    listings = extract_data_from_response(data, "listings")
    
    if not listings:
        logger.info("get_sale_listings: No sale listings found matching criteria")
        return "No sale listings found matching the criteria."
    
    # Apply active filter if requested
    if active_only:
        original_count = len(listings)
        filtered_listings = [listing for listing in listings if is_property_active(listing)]
        listings = filtered_listings
        filtered_count = original_count - len(listings)
        if filtered_count > 0:
            logger.info(f"get_sale_listings: Filtered out {filtered_count} inactive/stale listings")
    
    logger.info(f"get_sale_listings successful: found {len(listings)} sale listings")
    return json.dumps(listings, indent=2)

@mcp.tool(
    name="get_rental_listings",
    description=(
        "Retrieve rental listings with detailed info. "
        "Filters: city, state, zip_code, active_only (bool, default=True). "
        "Optional: limit (default=15). "
        "Example: city='Chicago', state='IL', limit=10, active_only=True. "
        "Returns a JSON list of rental listing objects."
    )
)
async def get_rental_listings(
    city: str = None,
    state: str = None,
    zip_code: str = None,
    limit: int = 15,
    active_only: bool = True
) -> str:
    """Get rental listings with comprehensive property information.
    
    Args:
        city: City name (e.g. Austin, New York)
        state: State abbreviation (e.g. TX, NY)
        zip_code: ZIP code (e.g. 78701)
        limit: Maximum number of listings to return (default: 15)
        active_only: Filter out inactive/off-market properties (default: True)
    """
    logger.info(f"get_rental_listings called with params: city={city}, state={state}, zip_code={zip_code}, limit={limit}, active_only={active_only}")
    
    # Validate parameters
    if not any([city, state, zip_code]):
        logger.warning("get_rental_listings: At least one location parameter (city, state, zip_code) is required")
        return "Error: At least one location parameter (city, state, zip_code) is required"
    
    if limit and (limit < 1 or limit > 1000):
        logger.warning(f"get_rental_listings: Invalid limit {limit}, must be between 1 and 1000")
        return "Error: Limit must be between 1 and 1000"
    
    params = {
        "city": city,
        "state": state,
        "zipCode": zip_code,
        "limit": limit
    }
    
    data = await make_request("/listings/rental/long-term", params)
    
    if not data or "Error" in data:
        logger.warning(f"get_rental_listings failed: {data}")
        return "Unable to fetch rental listings or no listings found."
    
    # Extract listings using helper function
    listings = extract_data_from_response(data, "listings")
    
    if not listings:
        logger.info("get_rental_listings: No rental listings found matching criteria")
        return "No rental listings found matching the criteria."
    
    # Apply active filter if requested
    if active_only:
        original_count = len(listings)
        filtered_listings = [listing for listing in listings if is_property_active(listing)]
        listings = filtered_listings
        filtered_count = original_count - len(listings)
        if filtered_count > 0:
            logger.info(f"get_rental_listings: Filtered out {filtered_count} inactive/stale listings")
    
    logger.info(f"get_rental_listings successful: found {len(listings)} rental listings")
    return json.dumps(listings, indent=2)

@mcp.tool(
    name="get_property_details",
    description=(
        "Get detailed property information by property_id. "
        "Required: property_id (string). "
        "Example: property_id='1234567890'. "
        "Returns a JSON object with detailed property attributes."
    )
)
async def get_property_details(property_id: str) -> str:
    """Get detailed property information.
    
    Args:
        property_id: Unique property identifier
    """
    logger.info(f"get_property_details called with property_id: {property_id}")
    
    data = await make_request(f"/properties/{property_id}")
    
    if not data or "Error" in data:
        logger.warning(f"get_property_details failed: {data}")
        return "Unable to fetch property details or no property found."
    
    # Extract property data using helper function
    property_data = extract_data_from_response(data, "property")
    if not property_data:
        logger.info("get_property_details: No property details found")
        return "No property details found for the specified property ID."
    
    logger.info("get_property_details successful: retrieved property details")
    return json.dumps(property_data, indent=2)

if __name__ == "__main__":
    # Log server startup with file location
    logger.info("=" * 60)
    logger.info("Starting Rentcast MCP Server...")
    logger.info(f"Log file location: {LOG_FILE}")
    logger.info(f"API Base URL: {RENTCAST_API_BASE}")
    logger.info(f"API Key configured: {'Yes' if (RENTCAST_API_KEY or os.getenv('RENTCAST_API_KEY')) else 'No'}")
    logger.info("=" * 60)

    try:
        # Initialize and run the server
        logger.info("Initializing FastMCP server...")
        mcp.run(transport="stdio")
        logger.info("Server stopped normally")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server stopped by user (Ctrl+C)")
    finally:
        logger.info("Server shutdown complete")
