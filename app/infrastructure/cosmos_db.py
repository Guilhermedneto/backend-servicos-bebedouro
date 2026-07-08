import time

from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config import get_settings

USERS = "users"
PROVIDERS = "providers"
REVIEWS = "reviews"
CATEGORIES = "categories"

_client: CosmosClient | None = None
_containers: dict = {}


def init_cosmos(retries: int = 30, delay_seconds: float = 2.0) -> None:
    global _client, _containers
    settings = get_settings()
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            _client = CosmosClient(
                settings.cosmos_endpoint,
                credential=settings.cosmos_key,
                connection_verify=settings.cosmos_endpoint.startswith("https"),
            )
            database = _client.create_database_if_not_exists(settings.cosmos_database)
            _containers[USERS] = database.create_container_if_not_exists(
                id=USERS, partition_key=PartitionKey(path="/id")
            )
            _containers[PROVIDERS] = database.create_container_if_not_exists(
                id=PROVIDERS, partition_key=PartitionKey(path="/id")
            )
            _containers[REVIEWS] = database.create_container_if_not_exists(
                id=REVIEWS,
                partition_key=PartitionKey(path="/providerId"),
                unique_key_policy={"uniqueKeys": [{"paths": ["/userId"]}]},
            )
            _containers[CATEGORIES] = database.create_container_if_not_exists(
                id=CATEGORIES, partition_key=PartitionKey(path="/id")
            )
            return
        except (exceptions.CosmosHttpResponseError, Exception) as error:  # emulator may still be starting
            last_error = error
            time.sleep(delay_seconds)
    raise RuntimeError(f"Não foi possível conectar ao Cosmos DB: {last_error}")


def get_container(name: str):
    if name not in _containers:
        raise RuntimeError("Cosmos DB não inicializado. Chame init_cosmos() no startup.")
    return _containers[name]
