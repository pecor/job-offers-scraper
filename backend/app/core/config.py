from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    
    API_HOST: str
    API_PORT: int
    CORS_ORIGINS: str

    # LLM (OpenAI-compatible API; default: Z.ai GLM Coding Plan endpoint-
    # use https://api.z.ai/api/paas/v4 for standard Z.ai API keys)
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.z.ai/api/coding/paas/v4"
    LLM_MODEL: str = "glm-5.3-flash"

    # Google Places API (geocoding for distance filtering)
    GOOGLE_PLACES_API_KEY: str = ""

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = str(Path("/app/../.env").resolve()) if Path("/app").exists() and Path("/app/../.env").resolve().exists() else str(Path.cwd() / ".env")
        case_sensitive = True
        extra = "ignore"


settings = Settings()
