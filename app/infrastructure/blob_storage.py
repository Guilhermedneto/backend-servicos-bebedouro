from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContentSettings, PublicAccess

from app.core.config import get_settings

_service: BlobServiceClient | None = None


def init_blob_storage() -> None:
    global _service
    settings = get_settings()
    _service = BlobServiceClient.from_connection_string(settings.blob_connection_string)
    try:
        _service.create_container(settings.blob_container, public_access=PublicAccess.BLOB)
    except ResourceExistsError:
        pass


class AzureBlobPhotoStorage:
    @property
    def _container(self):
        if _service is None:
            raise RuntimeError("Blob Storage não inicializado. Chame init_blob_storage() no startup.")
        return _service.get_container_client(get_settings().blob_container)

    def upload(self, blob_name: str, data: bytes, content_type: str) -> str:
        blob = self._container.upload_blob(
            name=blob_name,
            data=data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return blob.url

    def delete(self, blob_name: str) -> None:
        try:
            self._container.delete_blob(blob_name)
        except ResourceNotFoundError:
            pass
