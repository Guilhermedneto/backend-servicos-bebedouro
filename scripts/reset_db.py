"""Apaga o banco local (emulador) para recriação limpa no próximo startup do backend."""

from azure.cosmos import CosmosClient, exceptions

from app.core.config import get_settings

settings = get_settings()
client = CosmosClient(
    settings.cosmos_endpoint,
    credential=settings.cosmos_key,
    connection_verify=settings.cosmos_endpoint.startswith("https"),
)
try:
    client.delete_database(settings.cosmos_database)
    print(f"Banco '{settings.cosmos_database}' apagado.")
except exceptions.CosmosResourceNotFoundError:
    print("Banco não existia.")
