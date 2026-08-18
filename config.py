from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # we would set the env file to .env , by default all env files are normally named .env but you can name it what you named your env file 
    db_user : str
    db_password : SecretStr
    db_host : str
    db_name : str


    jwt_secret_key : SecretStr 
    jwt_algorithm : str = "HS256"
    jwt_token_expiry_mins :int = 30

    max_upload_size_bytes : int = 5 * 1024 * 1024
    # setting a max upload size is a good practice and is used prevent huge file uploads, and it would be mostly be used for uploading our profile picture
    # why 5 * 1024 * 1024 though ? 

    posts_per_page : int = 10   # We set the posts that should be set in a page as a default in our settings, so we can edit in one place, 

    reset_expire_token_mins : int = 60

    # Email configuration
    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str =  "noreply@example.com"
    mail_use_tls: bool = True    # Learnt that TLS meant transport layer security, would have to check up on that later

    frontend_url: str = "http://localhost:8000"

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:"
            f"{self.db_password.get_secret_value()}@{self.db_host}/{self.db_name}"
        )


settings = Settings()  # type: ignore[call-arg] 