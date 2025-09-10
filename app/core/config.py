import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum
from pydantic import Field

class Settings(BaseSettings):
    DATABASE_URL: str = Field(default="DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/mydb")
    MONGO_URI: str = Field(default="mongodb://username:password@localhost:27017/mydatabase?authSource=admin")
    MONGO_DB: str = Field(default="mcp_rentcast")

    LLM_API_KEY: str = Field(default="OPENAI_API_KEY")
    LLM_MODEL_ID_FAST: str = Field(default="gpt-4o-mini")
    LLM_MODEL_ID_SMART: str = Field(default="gpt-4o")
    LLM_MODEL_ID_CODE: str = Field(default="gpt-4.1")
    LLM_BASE_URL: str = Field(default="https://openrouter.ai/api")
    LLM_MODEL_PROVIDER: str = Field(default="openai-compatible")

    # Rentcast API configuration
    RENTCAST_API_KEY: str = Field(default="38e5835f110b46029d721d28679f68e6", description="The API key for the Rentcast API")
    RENTCAST_BASE_URL: str = Field(default="https://api.rentcast.io/v1", description="The base URL for the Rentcast API")
    
    # MCP Server configuration
    MCP_SERVER_NAME: str = Field(default="rentcast-mcp")
    MCP_SERVER_VERSION: str = Field(default="1.0.0")
    MCP_TRANSPORT: str = Field(default="stdio")
    
    # Rate limiting configuration
    MAX_API_CALLS_PER_SESSION: int = Field(default=40)
    TIMEOUT_SECONDS: int = Field(default=30)
    ENABLE_RATE_LIMITING: bool = Field(default=True)
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    
    # Logging configuration
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")
    
    WORKDIR: str = Field(default="./implementations")
    UPLOAD_DIR: str = Field(default="./resources/download")
    
    model_config = SettingsConfigDict(env_file=os.getenv("ENVPATH") if os.getenv("ENVPATH") else ".env", extra="allow")
    
settings = Settings()
try:
    os.makedirs(settings.WORKDIR, exist_ok=True)
except Exception as e: pass
