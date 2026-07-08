from dataclasses import dataclass

from app.application.interfaces import AiSearchService
from app.application.queries.providers import to_card


@dataclass
class AiSearchQuery:
    question: str


class AiSearchHandler:
    def __init__(self, ai_search: AiSearchService) -> None:
        self._ai_search = ai_search

    def handle(self, query: AiSearchQuery) -> dict:
        result = self._ai_search.search(query.question.strip())
        return {
            "answer": result["answer"],
            "providers": [to_card(p) for p in result["providers"]],
        }
