from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # we would set the env file to .env , by default all env files are normally named .env but you can name it what you named your env file 
    db_url : str

    jwt_secret_key : SecretStr 
    jwt_algorithm : str = "HS256"
    jwt_token_expiry_mins :int = 30

    max_upload_size_bytes : int = 5 * 1024 * 1024
    # setting a max upload size is a good practice and is used prevent huge file uploads, and it would be mostly be used for uploading our profile picture
    # why 5 * 1024 * 1024 though ? 


settings = Settings()  # type: ignore[call-arg] 