from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://transact_user:transact_password@localhost:5432/transact_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    GEMINI_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
