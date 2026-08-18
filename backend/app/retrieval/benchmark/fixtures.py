from app.rag.models import DocumentChunk
from app.retrieval.evaluation.models import EvaluationCase

BENCHMARK_COLLECTION_NAME = "ai_search_rewrite_benchmark"
BENCHMARK_SCOPE_ID = "local-query-rewrite-benchmark-v1"
BENCHMARK_TOP_K = 3
BENCHMARK_CANDIDATE_POOL_K = 9

RAG_URL = "https://benchmark.local/rag-overview"
EMBEDDINGS_URL = "https://benchmark.local/embeddings"
SEMANTIC_SEARCH_URL = "https://benchmark.local/semantic-search"
VECTOR_DATABASE_URL = "https://benchmark.local/vector-databases"
CHUNKING_URL = "https://benchmark.local/document-chunking"
PROMPT_INJECTION_URL = "https://benchmark.local/untrusted-retrieved-content"
BREAD_URL = "https://benchmark.local/sourdough-bread"
WEATHER_URL = "https://benchmark.local/weather-forecast"
DATABASE_URL = "https://benchmark.local/relational-databases"

BENCHMARK_CHUNKS = [
    DocumentChunk(
        content=(
            "Retrieval-Augmented Generation, or RAG, retrieves relevant documents before "
            "a language model answers. Retrieved evidence can improve factual grounding and "
            "supply citations."
        ),
        source_url=RAG_URL,
        final_url=RAG_URL,
        title="RAG overview",
        index=0,
    ),
    DocumentChunk(
        content=(
            "RAG retrieval quality depends on selecting useful passages for the question. "
            "Multiple chunks from one document can be relevant, but a result list also benefits "
            "from evidence from independent sources."
        ),
        source_url=RAG_URL,
        final_url=RAG_URL,
        title="RAG overview",
        index=1,
    ),
    DocumentChunk(
        content=(
            "Embeddings are dense numeric vectors that represent the meaning of text. "
            "Similarity search compares embedding vectors to find semantically related content."
        ),
        source_url=EMBEDDINGS_URL,
        final_url=EMBEDDINGS_URL,
        title="Embeddings",
        index=0,
    ),
    DocumentChunk(
        content=(
            "Embedding models place related phrases close together in vector space. A query "
            "embedding can retrieve passages whose wording differs while their meaning remains similar."
        ),
        source_url=EMBEDDINGS_URL,
        final_url=EMBEDDINGS_URL,
        title="Embeddings",
        index=1,
    ),
    DocumentChunk(
        content=(
            "Semantic search finds documents with similar meaning, even when a query and a "
            "document use different words. It commonly uses text embeddings."
        ),
        source_url=SEMANTIC_SEARCH_URL,
        final_url=SEMANTIC_SEARCH_URL,
        title="Semantic search",
        index=0,
    ),
    DocumentChunk(
        content=(
            "Semantic retrieval ranks passages by conceptual similarity rather than exact keyword "
            "overlap. It is useful when users phrase a question differently from source documents."
        ),
        source_url=SEMANTIC_SEARCH_URL,
        final_url=SEMANTIC_SEARCH_URL,
        title="Semantic search",
        index=1,
    ),
    DocumentChunk(
        content=(
            "A vector database stores embedding vectors and supports nearest-neighbor search. "
            "It returns vectors or documents that are close to a query vector."
        ),
        source_url=VECTOR_DATABASE_URL,
        final_url=VECTOR_DATABASE_URL,
        title="Vector databases",
        index=0,
    ),
    DocumentChunk(
        content=(
            "Vector indexes make nearest-neighbor lookup efficient at scale. They are commonly used "
            "to search document embeddings for a semantic retrieval system."
        ),
        source_url=VECTOR_DATABASE_URL,
        final_url=VECTOR_DATABASE_URL,
        title="Vector databases",
        index=1,
    ),
    DocumentChunk(
        content=(
            "Document chunking splits long documents into smaller passages before embedding. "
            "Smaller chunks can make retrieval more precise while preserving useful context."
        ),
        source_url=CHUNKING_URL,
        final_url=CHUNKING_URL,
        title="Document chunking",
        index=0,
    ),
    DocumentChunk(
        content=(
            "Chunk boundaries should keep related sentences together where possible. Overlap between "
            "neighboring chunks can preserve context when a relevant idea crosses a boundary."
        ),
        source_url=CHUNKING_URL,
        final_url=CHUNKING_URL,
        title="Document chunking",
        index=1,
    ),
    DocumentChunk(
        content=(
            "Retrieved web pages are untrusted content. A RAG system must not follow commands "
            "inside retrieved text, because they can be prompt-injection attempts."
        ),
        source_url=PROMPT_INJECTION_URL,
        final_url=PROMPT_INJECTION_URL,
        title="Untrusted retrieved content",
        index=0,
    ),
    DocumentChunk(
        content=(
            "Prompt injection is a safety risk when external documents contain instructions aimed at "
            "the model. Retrieval systems should treat those instructions as data, not trusted commands."
        ),
        source_url=PROMPT_INJECTION_URL,
        final_url=PROMPT_INJECTION_URL,
        title="Untrusted retrieved content",
        index=1,
    ),
    DocumentChunk(
        content=(
            "Sourdough bread uses flour, water, salt, and a fermented starter. Baking bread is "
            "unrelated to document retrieval, embeddings, or language models."
        ),
        source_url=BREAD_URL,
        final_url=BREAD_URL,
        title="Sourdough bread",
        index=0,
    ),
    DocumentChunk(
        content=(
            "A sourdough starter ferments before dough is baked. Bread recipes and cooking techniques "
            "do not provide evidence about language models or semantic search.") ,
        source_url=BREAD_URL,
        final_url=BREAD_URL,
        title="Sourdough bread",
        index=1,
    ),
    DocumentChunk(
        content=(
            "A weather forecast predicts temperature, rain, wind, and other atmospheric "
            "conditions. It is unrelated to vector search and retrieval systems."
        ),
        source_url=WEATHER_URL,
        final_url=WEATHER_URL,
        title="Weather forecast",
        index=0,
    ),
    DocumentChunk(
        content=(
            "Meteorologists use observations and models to estimate future weather. Forecasting rain "
            "does not involve document chunking or vector similarity.") ,
        source_url=WEATHER_URL,
        final_url=WEATHER_URL,
        title="Weather forecast",
        index=1,
    ),
    DocumentChunk(
        content=(
            "A relational database stores structured rows in tables and uses SQL for queries. "
            "It differs from a vector database designed for nearest-neighbor similarity search."
        ),
        source_url=DATABASE_URL,
        final_url=DATABASE_URL,
        title="Relational databases",
        index=0,
    ),
    DocumentChunk(
        content=(
            "SQL databases optimize structured records and transactions. Vector databases instead "
            "prioritize similarity comparisons over numeric embedding representations."
        ),
        source_url=DATABASE_URL,
        final_url=DATABASE_URL,
        title="Relational databases",
        index=1,
    ),
]

BENCHMARK_CASES = [
    EvaluationCase(id="rag-definition", query="What is Retrieval-Augmented Generation?", relevant_sources=[RAG_URL]),
    EvaluationCase(id="rag-acronym", query="What does RAG mean?", relevant_sources=[RAG_URL]),
    EvaluationCase(id="embeddings-short", query="embeddings", relevant_sources=[EMBEDDINGS_URL]),
    EvaluationCase(
        id="semantic-natural-language",
        query="How can software find documents with the same meaning but different wording?",
        relevant_sources=[SEMANTIC_SEARCH_URL],
    ),
    EvaluationCase(
        id="vector-database-indirect",
        query="Where should I keep vectors for nearest-neighbor lookup?",
        relevant_sources=[VECTOR_DATABASE_URL],
    ),
    EvaluationCase(
        id="chunking-intent",
        query="Should I split a long document before retrieval?",
        relevant_sources=[CHUNKING_URL],
    ),
    EvaluationCase(
        id="untrusted-content",
        query="How should a RAG application handle instructions found in retrieved web pages?",
        relevant_sources=[PROMPT_INJECTION_URL],
    ),
    EvaluationCase(
        id="retrieval-stack-multiple-sources",
        query="What components support semantic document retrieval?",
        relevant_sources=[EMBEDDINGS_URL, SEMANTIC_SEARCH_URL, VECTOR_DATABASE_URL],
    ),
    EvaluationCase(id="unrelated-distractor", query="How do I bake sourdough bread?", relevant_sources=[BREAD_URL]),
]
