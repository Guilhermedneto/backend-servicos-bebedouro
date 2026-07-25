from app.application.interfaces import CategoryRepository


def to_category_dto(category: dict) -> dict:
    return {
        "id": category["id"],
        "name": category["name"],
        "businessType": category.get("businessType"),
        "active": category["active"],
    }


class ListActiveCategoriesHandler:
    def __init__(self, categories: CategoryRepository) -> None:
        self._categories = categories

    def handle(self, business_type: str | None = None) -> list[dict]:
        return [to_category_dto(c) for c in self._categories.list_active(business_type)]
