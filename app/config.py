"""Application configuration.

All values are loaded from environment variables (and a local ``.env`` file)
via pydantic-settings, then exported as a single ``settings`` singleton used
by the rest of the application.
"""

from typing import Annotated

from pydantic import SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    NoDecode,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    db_user: str
    db_password: SecretStr
    db_host: str
    db_name: str

    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_pre_ping: bool = True
    database_pool_timeout_seconds: int = 30
    database_pool_recycle_seconds: int = 1800

    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_token_expiry_mins: int = 30

    cookie_name: str = "access_token"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    csrf_header: str = "x-csrf-protected"
    csrf_header_value: str = "1"

    max_upload_size_bytes: int = 5 * 1024 * 1024
    posts_per_page: int = 10
    reset_expire_token_mins: int = 60

    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_use_tls: bool = True

    frontend_url: str = "http://localhost:8000"

    aws_bucket_name: str
    aws_default_region: str
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_endpoint_url: str | None = None
    aws_presign_expiry_seconds: int = 900

    log_level: str = "INFO"
    allowed_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1"]
    rate_limit_login_per_minute: int = 5
    rate_limit_reset_per_minute: int = 3

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def split_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return [host.strip() for host in value.split(",") if host.strip()]
        return value

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:"
            f"{self.db_password.get_secret_value()}@{self.db_host}/{self.db_name}"
        )


settings = Settings()