# 🏠 MCP Rentcast Organized

A well-organized Model Context Protocol (MCP) server that provides access to Rentcast Real Estate API data through a standardized interface. This project is structured following the ai-native-todo-task-agent pattern for better maintainability and debugging.

## 📁 Project Structure

```
mcp-rentcast-organized/
├── app/
│   ├── core/                    # Shared libraries and configuration
│   │   └── config.py           # Application settings and environment variables
│   ├── models/                 # Database models (if needed)
│   ├── task_executor/          # MCP server implementation
│   │   ├── mcps/
│   │   │   └── rentcast/       # Rentcast MCP implementation
│   │   │       ├── main.py     # Python MCP server
│   │   │       ├── index.ts    # TypeScript MCP server
│   │   │       ├── services/   # API services
│   │   │       └── types/      # TypeScript type definitions
│   │   └── Dockerfile          # Docker configuration
│   ├── task_manager/           # Task management (if needed)
│   ├── tests/                  # Test files
│   └── thirdparty/             # Third-party integrations
├── envs/                       # Environment configurations
│   └── .env.example           # Environment variables template
├── resources/                  # Static resources
├── docker-compose.yml         # Docker Compose configuration
├── Makefile                   # Build and run commands
├── requirements.txt           # Python dependencies
├── package.json               # Node.js dependencies
└── tsconfig.json             # TypeScript configuration
```

## ✨ Features

- **🔍 Property Search**: Search properties with filters (city, state, bedrooms, bathrooms, etc.)
- **🎲 Random Properties**: Get random properties for market analysis
- **📊 Market Analysis**: Comprehensive market statistics and trends
- **💰 Property Valuation**: Automated property value estimates with comparables
- **🏠 Rent Estimates**: Long-term rent estimates with comparable properties
- **🏘️ Sale Listings**: Current properties for sale
- **🏘️ Rental Listings**: Current properties for rent
- **🏠 Property Details**: Detailed property information and parameters

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (optional)
- Rentcast API key ([Get one here](https://rentcast.io/))

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd mcp-rentcast-organized

# Install Python dependencies
make install-deps

# Copy environment file
cp envs/.env.example .env

# Edit .env with your Rentcast API key
RENTCAST_API_KEY=your_api_key_here
```

### Running the Server

#### Option 1: Python MCP Server
```bash
# Start Python MCP server
make start-server
```

#### Option 2: TypeScript MCP Server
```bash
# Build TypeScript files
make build-typescript

# Start TypeScript MCP server
make start-typescript
```

#### Option 3: Docker
```bash
# Start with Docker
make start
```

### Using with MCP Inspector

```bash
# For Python server
npx @modelcontextprotocol/inspector python app/task_executor/mcps/rentcast/main.py

# For TypeScript server
npx @modelcontextprotocol/inspector node dist/index.js

# Open browser at http://localhost:6274
# Use the provided auth token to access the interface
```

## 🛠️ Available Tools

### 1. **search_properties**
Search for properties with comprehensive information.

**Parameters:**
- `city` (optional): City name (e.g., "Austin", "New York")
- `state` (optional): State abbreviation (e.g., "TX", "CA")
- `zipCode` (optional): ZIP code (e.g., "78705")
- `bedrooms` (optional): Number of bedrooms (1-10)
- `bathrooms` (optional): Number of bathrooms (1-10)
- `propertyType` (optional): Type of property (e.g., "SingleFamily", "Condo")
- `limit` (optional): Maximum results (default: 15, max: 50)

### 2. **get_random_properties**
Get random properties for market analysis.

**Parameters:**
- `city` (optional): City name
- `state` (optional): State abbreviation
- `zipCode` (optional): ZIP code
- `limit` (optional): Maximum results (default: 10)

### 3. **analyze_market**
Get comprehensive market statistics and trends.

**Parameters:**
- `zipCode` (optional): ZIP code
- `city` (optional): City name
- `state` (optional): State abbreviation
- `dataType` (optional): Type of market data (default: "All")

### 4. **get_property_value**
Get automated property value estimates (AVM) with comparables.

**Parameters:**
- `propertyId` (optional): Property ID
- `address` (optional): Property address
- `latitude` (optional): Property latitude
- `longitude` (optional): Property longitude
- `propertyType` (optional): Type of property
- `bedrooms` (optional): Number of bedrooms
- `bathrooms` (optional): Number of bathrooms
- `squareFootage` (optional): Property square footage

### 5. **get_rent_estimates**
Get long-term rent estimates with comparable properties.

**Parameters:**
- `propertyId` (optional): Property ID
- `address` (optional): Property address
- `latitude` (optional): Property latitude
- `longitude` (optional): Property longitude
- `propertyType` (optional): Type of property
- `bedrooms` (optional): Number of bedrooms
- `bathrooms` (optional): Number of bathrooms
- `squareFootage` (optional): Property square footage

### 6. **get_sale_listings**
Get current properties for sale.

**Parameters:**
- `city` (optional): City name
- `state` (optional): State abbreviation
- `zipCode` (optional): ZIP code
- `limit` (optional): Maximum results (default: 15, max: 50)

### 7. **get_rental_listings**
Get current properties for rent.

**Parameters:**
- `city` (optional): City name
- `state` (optional): State abbreviation
- `zipCode` (optional): ZIP code
- `limit` (optional): Maximum results (default: 15, max: 50)

### 8. **get_property_details**
Get detailed property information.

**Parameters:**
- `id` (required): Property or listing ID

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `RENTCAST_API_KEY` | Your Rentcast API key | - | ✅ |
| `RENTCAST_BASE_URL` | Rentcast API base URL | `https://api.rentcast.io/v1` | ❌ |
| `MAX_API_CALLS_PER_SESSION` | Maximum API calls per session | `40` | ❌ |
| `TIMEOUT_SECONDS` | API call timeout | `30` | ❌ |
| `ENABLE_RATE_LIMITING` | Enable rate limiting | `true` | ❌ |
| `RATE_LIMIT_PER_MINUTE` | Rate limit per minute | `60` | ❌ |
| `DEBUG` | Enable debug mode | `false` | ❌ |
| `LOG_LEVEL` | Log level | `INFO` | ❌ |

### API Limits

- **Free Tier**: 45 API calls per month
- **Default Session Limit**: 40 calls per session
- **Rate Limiting**: 60 calls per minute (configurable)

## 🧪 Testing

```bash
# Run tests
make test

# Run specific test file
pytest app/tests/test_rentcast.py -v
```

## 🐳 Docker Support

```bash
# Build and start with Docker
make start

# Stop Docker containers
make stop

# Clean up Docker resources
make clean
```

## 📝 Development

### Adding New Tools

1. Add the tool function in `app/task_executor/mcps/rentcast/main.py` (Python) or `app/task_executor/mcps/rentcast/index.ts` (TypeScript)
2. Update the tool registration
3. Add tests in `app/tests/`
4. Update documentation

### Debugging

- Check logs in `app/task_executor/mcps/rentcast/rentcast_mcp.log`
- Use `DEBUG=true` in environment variables for verbose logging
- Use MCP Inspector for interactive testing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
