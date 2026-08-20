# Architecture

AI Search Engine separates request-scoped Web evidence from persistent conversation-scoped file evidence, while exposing both through one answer and citation model.

## Components

| Layer | Responsibility |
| --- | --- |
| React / Vite | Responsive workspace, sidebar and Settings, local history, deep-link routing, source selection, and streamed rendering |
| FastAPI | Health, search, answer, SSE answer, document upload, and document-deletion APIs |
| Conversation orchestration | Bounded conversation context and deterministic follow-up search-query composition |
| Web pipeline | Tavily search, concurrent fetch/extract through Trafilatura, and chunking |
| File pipeline | Safe in-memory PDF/TXT/MD/DOCX extraction, persistent indexing, and selected-document retrieval |
| Qdrant | Scoped semantic retrieval, payload filtering, deletion, and production Cloud Inference |
| Providers | Abstract Ollama/OpenAI LLM and embedding paths; Ollama is used locally and in production |

## Retrieval lifecycle

### Web mode

```text
query → Tavily → fetch/extract → chunk → embed → request-scoped Qdrant points
      → retrieve → citation-aware answer → cleanup temporary points
```

Each Web request receives a UUID `retrieval_scope_id`. The RAG service deletes points in that scope in its finalization path after non-stream success or error, and after stream completion, error, or abort/aclose. Cleanup failures do not replace the answer error. Web points are therefore ephemeral rather than a permanently accumulating corpus.

### Files mode

```text
selected conversation documents → persistent Qdrant retrieval → citation-aware answer
```

Files mode does not call Tavily. Uploads are extracted in memory and their chunks are stored with `source_type=file`, `conversation_id`, and `document_id`. A request must provide an active conversation and selected document IDs; there is no global file retrieval. Persistent vectors are deleted when an individual document is removed or when the conversation's document scope is removed.

PDF page metadata is preserved. File sources without page metadata, including non-PDF files, do not receive synthetic page numbers. Raw browser `File`/`Blob` bytes are not saved in IndexedDB; the browser keeps local document metadata while the extracted chunks live in Qdrant.

### Web + Files mode

Hybrid mode retrieves fresh Web evidence and selected persistent file evidence, combines the chunks into one citation-aware prompt, and then cleans only the temporary Web scope. File vectors remain available until explicit deletion.

## Qdrant and providers

Qdrant maintains keyword payload indexes for `retrieval_scope_id`, `source_type`, `conversation_id`, and `document_id`, enabling strict filtering and deletion.

| Environment | Generation | Embeddings |
| --- | --- | --- |
| Local | Ollama `qwen3:4b-instruct` | Ollama `embeddinggemma`, 768 dimensions |
| Production | Ollama Cloud `gpt-oss:20b` | Qdrant Cloud Inference `intfloat/multilingual-e5-small`, 384 dimensions |

The production collection is `ai_search_engine_cloud_384`. The provider interfaces also retain optional OpenAI implementations. A local 768-dimensional setup must use a compatible local collection, not the production 384-dimensional one.

## Conversations, sources, and streaming

Conversation history is browser-local IndexedDB, with sidebar history, New Search, refresh restoration, and Vercel-supported `/c/:id` deep links. The API accepts bounded client-provided history. Follow-up search queries are composed deterministically from recent user questions; stopped/error assistant messages are excluded from later model context.

Each assistant message owns its own source list, which preserves historical citation selection. Inline citations support `[n]`, `【n】`, and grouped forms such as `[1,4]`. Web sources can link externally; file sources are URL-less and display filename and page when appropriate. The Sources workspace is a right-side desktop panel and a mobile drawer with Web/File filtering.

Answers stream through a `POST` request consumed via `fetch` and ReadableStream SSE parsing. The backend emits progress, answer deltas, sources, completion, and error events.

## Request-local observability

The backend logs request-local pipeline timing data; it does not claim a persistent telemetry platform. Web mode can include `query_preparation_ms`, `web_search_ms`, `web_retrieval_pipeline_ms`, `generation_ms`, `cleanup_ms`, and `total_ms`. Files mode includes `file_retrieval_ms` instead of Web stages; Hybrid combines relevant stages. Streaming records first-token timing on the first actual answer delta. Lifecycle status is `success`, `error`, or `aborted`.
