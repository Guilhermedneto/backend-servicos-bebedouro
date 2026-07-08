"""Busca conversacional com LangGraph + Azure OpenAI.

Grafo em três etapas:
  1. interpret — a LLM extrai a intenção da pergunta (termos de busca, categorias, ordenação);
  2. retrieve  — busca prestadores ativos no Cosmos com os filtros extraídos;
  3. answer    — resposta fixa: confirma o achado ou informa que nada foi encontrado.
"""

import logging
from typing import Literal, TypedDict

from pydantic import BaseModel, Field

from app.application.interfaces import CategoryRepository, ProviderRepository
from app.core.config import get_settings
from app.core.errors import AppError
from app.domain.validators import normalize_text

logger = logging.getLogger("servicos-bebedouro.ai-search")

MAX_RESULTS = 6


class AiSearchUnavailableError(AppError):
    status_code = 503
    code = "AI_SEARCH_UNAVAILABLE"


class SearchIntent(BaseModel):
    """Intenção estruturada extraída da pergunta do usuário."""

    search_terms: list[str] = Field(
        default_factory=list,
        description="Palavras-chave curtas para busca textual (serviço, nome do prestador ou bairro). Ex.: ['chuveiro', 'eletricista', 'centro']",
    )
    category_names: list[str] = Field(
        default_factory=list,
        description="Nomes de categorias/ramos de atuação relacionados ao que o usuário precisa. Ex.: ['Eletricista', 'Encanador']",
    )
    sort: Literal["rating", "reviews", "recent"] = Field(
        default="rating",
        description="Ordenação preferida: 'rating' (melhor avaliação, padrão), 'reviews' (mais avaliados) ou 'recent' (mais recentes)",
    )


class GraphState(TypedDict):
    question: str
    intent: SearchIntent | None
    providers: list[dict]
    answer: str


class LangGraphAiSearchService:
    def __init__(
        self,
        providers: ProviderRepository,
        categories: CategoryRepository,
        llm=None,
    ) -> None:
        self._providers = providers
        self._categories = categories
        self._llm = llm
        self._graph = self._build_graph()

    @staticmethod
    def _build_llm():
        settings = get_settings()
        if not (
            settings.azure_openai_endpoint
            and settings.azure_openai_api_key
            and settings.azure_openai_deployment
        ):
            raise AiSearchUnavailableError(
                "A busca com IA ainda não está configurada. "
                "Defina AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY e AZURE_OPENAI_DEPLOYMENT."
            )
        from langchain_openai import AzureChatOpenAI

        # Sem temperature customizada: modelos de raciocínio (família gpt-5) só aceitam o padrão.
        return AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
            timeout=60,
        )

    def _build_graph(self):
        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(GraphState)
        graph.add_node("interpret", self._interpret)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("answer", self._answer)
        graph.add_edge(START, "interpret")
        graph.add_edge("interpret", "retrieve")
        graph.add_edge("retrieve", "answer")
        graph.add_edge("answer", END)
        return graph.compile()

    def search(self, question: str) -> dict:
        if self._llm is None:
            self._llm = self._build_llm()
        result = self._graph.invoke(
            {"question": question, "intent": None, "providers": [], "answer": ""}
        )
        return {"answer": result["answer"], "providers": result["providers"]}

    # ---------- nós do grafo ----------

    def _interpret(self, state: GraphState) -> dict:
        category_names = [c["name"] for c in self._categories.list_active()]
        prompt = (
            "Você interpreta perguntas de moradores de Bebedouro/SP que procuram prestadores de "
            "serviços e comerciantes em uma plataforma local. Extraia a intenção de busca da pergunta.\n"
            f"Categorias disponíveis na plataforma: {', '.join(category_names)}.\n"
            "Use somente categorias dessa lista em category_names (as mais relevantes, no máximo 3). "
            "Em search_terms coloque poucas palavras-chave úteis para busca textual (sem artigos ou "
            "preposições), como o tipo de serviço, um bairro citado ou um nome próprio.\n\n"
            f"Pergunta: {state['question']}"
        )
        try:
            intent = self._llm.with_structured_output(SearchIntent).invoke(prompt)
        except Exception as error:
            logger.warning("Falha ao interpretar a pergunta, usando a pergunta como termo: %s", error)
            intent = SearchIntent(search_terms=[state["question"]])
        return {"intent": intent}

    def _retrieve(self, state: GraphState) -> dict:
        intent = state["intent"] or SearchIntent()
        found: dict[str, dict] = {}

        active = self._categories.list_active()
        category_ids = []
        for wanted in intent.category_names:
            wanted_norm = normalize_text(wanted)
            for category in active:
                if wanted_norm in category["nameSearch"] or category["nameSearch"] in wanted_norm:
                    category_ids.append(category["id"])
                    break

        for category_id in category_ids:
            items, _ = self._providers.list_public(
                search=None, category_id=category_id, sort=intent.sort, offset=0, limit=MAX_RESULTS
            )
            for item in items:
                found.setdefault(item["id"], item)

        for term in intent.search_terms[:4]:
            items, _ = self._providers.list_public(
                search=normalize_text(term), category_id=None, sort=intent.sort, offset=0, limit=MAX_RESULTS
            )
            for item in items:
                found.setdefault(item["id"], item)

        return {"providers": list(found.values())[:MAX_RESULTS]}

    def _answer(self, state: GraphState) -> dict:
        if state["providers"]:
            return {"answer": "Olha o que eu encontrei pra você"}
        intent = state["intent"] or SearchIntent()
        subject = next(iter(intent.category_names), None) or next(
            iter(intent.search_terms), None
        ) or "prestador"
        return {"answer": f"Não encontrei nenhum(a) {subject.lower()} cadastrado(a)"}
