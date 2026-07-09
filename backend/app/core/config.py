from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # API Configurations
    PROJECT_NAME: str = "FIFA Nexus AI"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = Field(default="production")

    # PostgreSQL Configuration
    POSTGRES_USER: str = Field(default="admin")
    POSTGRES_PASSWORD: str = Field(default="")  # Set via POSTGRES_PASSWORD env var
    POSTGRES_DB: str = Field(default="fifanexus")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)

    # Redis Configuration
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)

    # Qdrant Configuration
    QDRANT_HOST: str = Field(default="localhost")
    QDRANT_PORT: int = Field(default=6333)

    # ML Inference Service Configuration
    ML_SERVICE_URL: str = Field(default="http://localhost:8001/predict")

    # LLM Provider Configuration
    # Supports OpenAI, Groq, and Featherless — all OpenAI-compatible.
    # Priority: OPENAI_API_KEY > GROQ_API_KEY > FEATHERLESS_API_KEY > heuristic fallback.
    OPENAI_API_KEY: str = Field(default="")       # Set via OPENAI_API_KEY env var
    GROQ_API_KEY: str = Field(default="")         # Set via GROQ_API_KEY env var
    GROQ_BASE_URL: str = Field(default="https://api.groq.com/openai/v1")
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile")
    FEATHERLESS_API_KEY: str = Field(default="")  # Set via FEATHERLESS_API_KEY env var
    FEATHERLESS_BASE_URL: str = Field(default="https://api.featherless.ai/v1")
    FEATHERLESS_MODEL: str = Field(default="meta-llama/Llama-3.3-70B-Instruct")

    # Security Configuration
    # Security Configuration
    API_KEY: str = Field(default="")  # Set via API_KEY env var for API protection

    @property
    def is_llm_configured(self) -> bool:
        """
        Determines if any of the OpenAI-compatible LLM provider API keys are active.
        """
        def is_valid(key: str) -> bool:
            return bool(key) and "mock" not in key.lower()
        return is_valid(self.OPENAI_API_KEY) or is_valid(self.GROQ_API_KEY) or is_valid(self.FEATHERLESS_API_KEY)

    # Optional: full DATABASE_URL override (Render, Railway, Heroku inject this directly)
    DATABASE_URL_OVERRIDE: str = Field(default="", alias="DATABASE_URL")

    @property
    def DATABASE_URL(self) -> str:
        # Render injects DATABASE_URL as postgres://... — convert to asyncpg dialect
        if self.DATABASE_URL_OVERRIDE:
            url = self.DATABASE_URL_OVERRIDE
            # Render uses postgres://, asyncpg requires postgresql+asyncpg://
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and "+asyncpg" not in url:
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        # Local dev: build from individual POSTGRES_* env vars
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        populate_by_name=True   # allows alias DATABASE_URL to populate DATABASE_URL_OVERRIDE
    )

settings = Settings()
