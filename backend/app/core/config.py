from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    protocolguard_env: str = "development"
    database_url: str = "sqlite:///./protocolguard.db"
    cors_origins: str = "http://localhost:5173,http://localhost:5174"


settings = Settings()
