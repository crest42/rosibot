from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Pydantic-settings class used to control signal specific settings"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    signal_service: str
    phone_number: str
    signal_group_id: str