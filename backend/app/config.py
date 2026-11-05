from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env, resolved from this file's location so the working folder does not matter
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
# Render Secret File named gemini.env. It exists only on Render, so it is ignored on your PC.
SECRET_FILE = Path("/etc/secrets/gemini.env")


class Settings(BaseSettings):
    database_url: str = ""
    jwt_secret: str = "change-me"
    jwt_expiry_hours: int = 8
    enable_llm_assist: bool = False
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    # Comma-separated list of frontend origins allowed to call the API from a browser.
    cors_origins: str = "http://127.0.0.1:5500,http://localhost:5500"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=(ENV_FILE, SECRET_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
