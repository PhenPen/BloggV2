from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # we would set the env file to .env , by default all env files are normally named .env but you can name it what you named your env file 
    db_url : str

    jwt_secret_key : SecretStr 
    jwt_algorithm : str = "HS256"
    jwt_token_expiry_mins :int = 30


settings = Settings()  # type: ignore[call-arg] 