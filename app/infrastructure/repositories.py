from concurrent.futures import ThreadPoolExecutor

from azure.cosmos import exceptions

from app.application.interfaces import DuplicateReviewError
from app.infrastructure import cosmos_db


def _query(container, query: str, parameters: list[dict] | None = None) -> list[dict]:
    return list(
        container.query_items(
            query=query, parameters=parameters or [], enable_cross_partition_query=True
        )
    )


def _scalar(container, query: str, parameters: list[dict] | None = None):
    results = _query(container, query, parameters)
    return results[0] if results else None


class CosmosUserRepository:
    @property
    def _container(self):
        return cosmos_db.get_container(cosmos_db.USERS)

    def get(self, user_id: str) -> dict | None:
        try:
            return self._container.read_item(item=user_id, partition_key=user_id)
        except exceptions.CosmosResourceNotFoundError:
            return None

    def find_by_email(self, email: str) -> dict | None:
        return _scalar(
            self._container,
            "SELECT * FROM c WHERE c.email = @email",
            [{"name": "@email", "value": email.lower()}],
        )

    def find_by_reset_token_hash(self, token_hash: str) -> dict | None:
        return _scalar(
            self._container,
            "SELECT * FROM c WHERE c.resetTokenHash = @hash",
            [{"name": "@hash", "value": token_hash}],
        )

    def create(self, doc: dict) -> dict:
        return self._container.create_item(doc)

    def update(self, doc: dict) -> dict:
        return self._container.replace_item(item=doc["id"], body=doc)

    def delete(self, user_id: str) -> None:
        try:
            self._container.delete_item(item=user_id, partition_key=user_id)
        except exceptions.CosmosResourceNotFoundError:
            pass

    def list_by_role(self, role: str) -> list[dict]:
        return _query(
            self._container,
            "SELECT * FROM c WHERE c.role = @role ORDER BY c.createdAt DESC",
            [{"name": "@role", "value": role}],
        )

    def count_by_role(self, role: str) -> int:
        return _scalar(
            self._container,
            "SELECT VALUE COUNT(1) FROM c WHERE c.role = @role",
            [{"name": "@role", "value": role}],
        ) or 0


class CosmosProviderRepository:
    @property
    def _container(self):
        return cosmos_db.get_container(cosmos_db.PROVIDERS)

    def get(self, provider_id: str) -> dict | None:
        try:
            return self._container.read_item(item=provider_id, partition_key=provider_id)
        except exceptions.CosmosResourceNotFoundError:
            return None

    def find_by_user_id(self, user_id: str) -> dict | None:
        return _scalar(
            self._container,
            "SELECT * FROM c WHERE c.userId = @userId",
            [{"name": "@userId", "value": user_id}],
        )

    def create(self, doc: dict) -> dict:
        return self._container.create_item(doc)

    def update(self, doc: dict) -> dict:
        return self._container.replace_item(item=doc["id"], body=doc)

    def delete(self, provider_id: str) -> None:
        try:
            self._container.delete_item(item=provider_id, partition_key=provider_id)
        except exceptions.CosmosResourceNotFoundError:
            pass

    def list_public(
        self, search: str | None, category_id: str | None, sort: str, offset: int, limit: int
    ) -> tuple[list[dict], int]:
        where = "c.status = 'active'"
        parameters: list[dict] = []
        if category_id:
            where += " AND ARRAY_CONTAINS(c.categoryIds, @categoryId)"
            parameters.append({"name": "@categoryId", "value": category_id})
        if search:
            where += (
                " AND (CONTAINS(c.nameSearch, @search)"
                " OR CONTAINS(c.categorySearch, @search)"
                " OR CONTAINS(c.bairroSearch, @search))"
            )
            parameters.append({"name": "@search", "value": search})
        order = {
            "rating": "c.ratingAvg DESC",
            "reviews": "c.ratingCount DESC",
            "recent": "c.approvedAt DESC",
        }[sort]
        with ThreadPoolExecutor(max_workers=2) as pool:
            items_future = pool.submit(
                _query,
                self._container,
                f"SELECT * FROM c WHERE {where} ORDER BY {order} OFFSET @offset LIMIT @limit",
                parameters
                + [{"name": "@offset", "value": offset}, {"name": "@limit", "value": limit}],
            )
            total_future = pool.submit(
                _scalar, self._container, f"SELECT VALUE COUNT(1) FROM c WHERE {where}", parameters
            )
        return items_future.result(), total_future.result() or 0

    def list_admin(self, status: str | None) -> list[dict]:
        if status:
            return _query(
                self._container,
                "SELECT * FROM c WHERE c.status = @status ORDER BY c.createdAt DESC",
                [{"name": "@status", "value": status}],
            )
        return _query(self._container, "SELECT * FROM c ORDER BY c.createdAt DESC")

    def count_by_status(self, status: str) -> int:
        return _scalar(
            self._container,
            "SELECT VALUE COUNT(1) FROM c WHERE c.status = @status",
            [{"name": "@status", "value": status}],
        ) or 0

    def count_by_category(self, category_id: str) -> int:
        return _scalar(
            self._container,
            "SELECT VALUE COUNT(1) FROM c WHERE ARRAY_CONTAINS(c.categoryIds, @categoryId)",
            [{"name": "@categoryId", "value": category_id}],
        ) or 0

    def category_usage_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for ids in _query(self._container, "SELECT VALUE c.categoryIds FROM c"):
            for category_id in ids or []:
                counts[category_id] = counts.get(category_id, 0) + 1
        return counts


class CosmosReviewRepository:
    @property
    def _container(self):
        return cosmos_db.get_container(cosmos_db.REVIEWS)

    def get(self, review_id: str, provider_id: str) -> dict | None:
        try:
            return self._container.read_item(item=review_id, partition_key=provider_id)
        except exceptions.CosmosResourceNotFoundError:
            return None

    def find_by_user_and_provider(self, user_id: str, provider_id: str) -> dict | None:
        return _scalar(
            self._container,
            "SELECT * FROM c WHERE c.providerId = @providerId AND c.userId = @userId",
            [
                {"name": "@providerId", "value": provider_id},
                {"name": "@userId", "value": user_id},
            ],
        )

    def create(self, doc: dict) -> dict:
        try:
            return self._container.create_item(doc)
        except exceptions.CosmosHttpResponseError as error:
            if error.status_code == 409:
                raise DuplicateReviewError() from error
            raise

    def update(self, doc: dict) -> dict:
        return self._container.replace_item(item=doc["id"], body=doc)

    def delete(self, review_id: str, provider_id: str) -> None:
        try:
            self._container.delete_item(item=review_id, partition_key=provider_id)
        except exceptions.CosmosResourceNotFoundError:
            pass

    def list_by_provider(self, provider_id: str) -> list[dict]:
        return _query(
            self._container,
            "SELECT * FROM c WHERE c.providerId = @providerId ORDER BY c.createdAt DESC",
            [{"name": "@providerId", "value": provider_id}],
        )

    def list_by_user(self, user_id: str) -> list[dict]:
        return _query(
            self._container,
            "SELECT * FROM c WHERE c.userId = @userId",
            [{"name": "@userId", "value": user_id}],
        )

    def list_all(self) -> list[dict]:
        return _query(self._container, "SELECT * FROM c ORDER BY c.createdAt DESC")

    def delete_by_provider(self, provider_id: str) -> None:
        for review in self.list_by_provider(provider_id):
            self.delete(review["id"], provider_id)

    def aggregate_for_provider(self, provider_id: str) -> tuple[int, float]:
        result = _scalar(
            self._container,
            "SELECT VALUE {'count': COUNT(1), 'avg': AVG(c.rating)} FROM c "
            "WHERE c.providerId = @providerId",
            [{"name": "@providerId", "value": provider_id}],
        )
        if not result or not result.get("count"):
            return 0, 0.0
        return result["count"], float(result["avg"])

    def count_all(self) -> int:
        return _scalar(self._container, "SELECT VALUE COUNT(1) FROM c") or 0


class CosmosCategoryRepository:
    @property
    def _container(self):
        return cosmos_db.get_container(cosmos_db.CATEGORIES)

    def get(self, category_id: str) -> dict | None:
        try:
            return self._container.read_item(item=category_id, partition_key=category_id)
        except exceptions.CosmosResourceNotFoundError:
            return None

    def create(self, doc: dict) -> dict:
        return self._container.create_item(doc)

    def update(self, doc: dict) -> dict:
        return self._container.replace_item(item=doc["id"], body=doc)

    def delete(self, category_id: str) -> None:
        try:
            self._container.delete_item(item=category_id, partition_key=category_id)
        except exceptions.CosmosResourceNotFoundError:
            pass

    def list_active(self) -> list[dict]:
        return _query(
            self._container, "SELECT * FROM c WHERE c.active = true ORDER BY c.nameSearch ASC"
        )

    def list_all(self) -> list[dict]:
        return _query(self._container, "SELECT * FROM c ORDER BY c.nameSearch ASC")
