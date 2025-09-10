import pytest
import asyncio
from unittest.mock import patch, AsyncMock
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.task_executor.mcps.rentcast.main import (
    search_properties,
    get_random_properties,
    analyze_market,
    get_property_value,
    get_rent_estimates,
    get_sale_listings,
    get_rental_listings,
    get_property_details
)

class TestRentcastMCP:
    """Test cases for Rentcast MCP server functions."""
    
    @pytest.mark.asyncio
    async def test_search_properties_success(self):
        """Test successful property search."""
        mock_data = {
            "properties": [
                {
                    "id": "12345",
                    "address": "123 Main St",
                    "city": "Austin",
                    "state": "TX",
                    "bedrooms": 3,
                    "bathrooms": 2,
                    "price": 450000
                }
            ]
        }
        
        with patch('app.task_executor.mcps.rentcast.main.make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            
            result = await search_properties(city="Austin", state="TX", bedrooms=3)
            
            assert "12345" in result
            assert "Austin" in result
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_properties_no_results(self):
        """Test property search with no results."""
        mock_data = {"properties": []}
        
        with patch('app.task_executor.mcps.rentcast.main.make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            
            result = await search_properties(city="NonexistentCity")
            
            assert "No properties found" in result
    
    @pytest.mark.asyncio
    async def test_get_random_properties_success(self):
        """Test successful random properties retrieval."""
        mock_data = {
            "properties": [
                {
                    "id": "67890",
                    "address": "456 Oak Ave",
                    "city": "Denver",
                    "state": "CO"
                }
            ]
        }
        
        with patch('app.task_executor.mcps.rentcast.main.make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            
            result = await get_random_properties(city="Denver", limit=5)
            
            assert "67890" in result
            assert "Denver" in result
    
    @pytest.mark.asyncio
    async def test_analyze_market_success(self):
        """Test successful market analysis."""
        mock_data = {
            "markets": [
                {
                    "zipCode": "78701",
                    "city": "Austin",
                    "state": "TX",
                    "medianPrice": 500000,
                    "pricePerSqFt": 300
                }
            ]
        }
        
        with patch('app.task_executor.mcps.rentcast.main.make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            
            result = await analyze_market(zip_code="78701")
            
            assert "78701" in result
            assert "Austin" in result
    
    @pytest.mark.asyncio
    async def test_get_property_value_success(self):
        """Test successful property value estimation."""
        mock_data = {
            "avm": [
                {
                    "propertyId": "12345",
                    "estimatedValue": 450000,
                    "lowValue": 400000,
                    "highValue": 500000
                }
            ]
        }
        
        with patch('app.task_executor.mcps.rentcast.main.make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            
            result = await get_property_value(property_id="12345")
            
            assert "12345" in result
            assert "450000" in result
    
    @pytest.mark.asyncio
    async def test_get_property_value_missing_params(self):
        """Test property value estimation with missing required parameters."""
        result = await get_property_value()
        
        assert "Error: Must provide" in result
    
    @pytest.mark.asyncio
    async def test_get_rent_estimates_success(self):
        """Test successful rent estimates."""
        mock_data = {
            "avm": [
                {
                    "propertyId": "12345",
                    "estimatedRent": 2500,
                    "lowRent": 2000,
                    "highRent": 3000
                }
            ]
        }
        
        with patch('app.task_executor.mcps.rentcast.main.make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            
            result = await get_rent_estimates(property_id="12345")
            
            assert "12345" in result
            assert "2500" in result
    
    @pytest.mark.asyncio
    async def test_get_sale_listings_success(self):
        """Test successful sale listings retrieval."""
        mock_data = {
            "listings": [
                {
                    "id": "sale123",
                    "address": "789 Pine St",
                    "city": "Miami",
                    "state": "FL",
                    "price": 600000
                }
            ]
        }
        
        with patch('app.task_executor.mcps.rentcast.main.make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            
            result = await get_sale_listings(city="Miami", state="FL")
            
            assert "sale123" in result
            assert "Miami" in result
    
    @pytest.mark.asyncio
    async def test_get_rental_listings_success(self):
        """Test successful rental listings retrieval."""
        mock_data = {
            "listings": [
                {
                    "id": "rental123",
                    "address": "321 Elm St",
                    "city": "Chicago",
                    "state": "IL",
                    "rent": 2000
                }
            ]
        }
        
        with patch('app.task_executor.mcps.rentcast.main.make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            
            result = await get_rental_listings(city="Chicago", state="IL")
            
            assert "rental123" in result
            assert "Chicago" in result
    
    @pytest.mark.asyncio
    async def test_get_property_details_success(self):
        """Test successful property details retrieval."""
        mock_data = {
            "property": {
                "id": "12345",
                "address": "123 Main St",
                "city": "Austin",
                "state": "TX",
                "bedrooms": 3,
                "bathrooms": 2,
                "squareFootage": 2000,
                "yearBuilt": 2010
            }
        }
        
        with patch('app.task_executor.mcps.rentcast.main.make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            
            result = await get_property_details(property_id="12345")
            
            assert "12345" in result
            assert "Austin" in result
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test API error handling."""
        mock_data = {"Error": "API key not configured"}
        
        with patch('app.task_executor.mcps.rentcast.main.make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            
            result = await search_properties(city="Austin")
            
            assert "Unable to fetch properties" in result

if __name__ == "__main__":
    pytest.main([__file__])
