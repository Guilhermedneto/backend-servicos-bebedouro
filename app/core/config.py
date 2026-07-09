from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    cosmos_endpoint: str = "http://localhost:8081"
    cosmos_key: str = (
        "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
    )
    cosmos_database: str = "servicos-bebedouro"

    blob_connection_string: str = (
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
        "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    )
    blob_container: str = "provider-photos"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    encryption_key: str = "L2beIhpBSTjqOxJFHwWO2u8DWicaSPYY0Kmk3XhE1lM="

    sendgrid_api_key: str = ""
    email_from: str = "no-reply@servicosbebedouro.com.br"
    email_from_name: str = "Serviços Bebedouro"

    frontend_url: str = "http://localhost:4000"
    cors_origins: str = (
        "http://localhost:4000,http://127.0.0.1:4000,http://localhost:4200,http://127.0.0.1:4200"
    )

    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "servicos-bebedouro/1.0"

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-10-21"

    admin_email: str = "admin@servicosbebedouro.com.br"
    admin_password: str = ""  # obrigatório via env; sem valor o seed do admin é ignorado
    admin_name: str = "Administrador"

    reset_token_minutes: int = 60
    max_photos: int = 5
    max_photo_bytes: int = 5 * 1024 * 1024
    page_size: int = 12

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
