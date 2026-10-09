"""Fixed channel identity and search terms for this story-series project."""

CHANNEL_NICHE = (
    "Peaceful Telugu village stories set in the 1980s, with traditional village life, "
    "vintage details, calm and pleasant narration, family and community values, and "
    "gentle moral lessons. Every reel belongs to one connected serial with recurring "
    "characters, continuing events, and an ending hook for the next episode."
)

CHANNEL_SEARCH_QUERIES_EN = (
    "Telugu 1980s village stories vintage",
    "Telugu vintage VHS style village stories",
    "Telugu traditional village cooking old style",
    "Telugu village traditions festivals rural life",
    "Telugu old village moral stories family values",
)
CHANNEL_SEARCH_QUERIES_TE = (
    "1980ల తెలుగు గ్రామ జీవిత కథలు",
    "పాతకాలపు తెలుగు గ్రామ కథలు",
    "పాతకాలపు తెలుగు పల్లెటూరి వంటలు",
    "తెలుగు గ్రామ సంప్రదాయాలు పండుగలు",
    "తెలుగు పాత నీతి కథలు కుటుంబ విలువలు",
)

CHANNEL_SEARCH_QUERIES = CHANNEL_SEARCH_QUERIES_EN

# Retain a concise query for clients that still consume the single-query config field.
CHANNEL_SEARCH_QUERY = CHANNEL_SEARCH_QUERIES[0]


def build_search_queries(topic: str = "", language: str = "te") -> tuple[str, ...]:
    """Build broad niche searches and optionally add one episode-idea search."""
    extra = " ".join(topic.split())
    if language == "te":
        queries = [f"తెలుగు గ్రామ కథ {extra}"] if extra else []
        queries.extend(CHANNEL_SEARCH_QUERIES_TE)
    else:
        queries = [f"Telugu village story {extra}"] if extra else []
        queries.extend(CHANNEL_SEARCH_QUERIES_EN)
    return tuple(dict.fromkeys(queries))
