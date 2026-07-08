from app.application.interfaces import CategoryRepository


def to_category_dto(category: dict) -> dict:
    return {"id": category["id"], "name": category["name"], "active": category["active"]}


class ListActiveCategoriesHandler:
    def __init__(self, categories: CategoryRepository) -> None:
        self._categories = categories

    def handle(self) -> list[dict]:
        return [to_category_dto(c) for c in self._categories.list_active()]
