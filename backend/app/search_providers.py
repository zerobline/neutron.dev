from dataclasses import dataclass

from app.models import SearchProviderName


@dataclass(frozen=True)
class SearchProviderDefinition:
    id: SearchProviderName
    label: str
    env_key: str
    description: str
    docs_url: str


SEARCH_PROVIDERS: dict[SearchProviderName, SearchProviderDefinition] = {
    "brave": SearchProviderDefinition(
        "brave",
        "Brave Search",
        "BRAVE_API_KEY",
        "Independent web, news, image, and LLM-ready search results.",
        "https://api-dashboard.search.brave.com/documentation/quickstart",
    ),
    "serper": SearchProviderDefinition(
        "serper",
        "Serper",
        "SERPER_API_KEY",
        "Google search results through a simple API built for agents.",
        "https://serper.dev/",
    ),
    "tavily": SearchProviderDefinition(
        "tavily",
        "Tavily",
        "TAVILY_API_KEY",
        "Search and extracted web content optimized for AI applications.",
        "https://docs.tavily.com/",
    ),
    "exa": SearchProviderDefinition(
        "exa",
        "Exa",
        "EXA_API_KEY",
        "Semantic and neural web search with content retrieval.",
        "https://docs.exa.ai/",
    ),
}


def get_search_provider(provider: SearchProviderName) -> SearchProviderDefinition:
    return SEARCH_PROVIDERS[provider]
