# Evaluation and Results

The project uses deterministic offline evaluation for engineering regression checks, complemented by backend and frontend tests. These results are not a benchmark of general model factual correctness.

## Final deterministic quality gate

| Area | Result |
| --- | --- |
| Quality gate | 29 / 29 PASS |
| File retrieval Hit@1, Hit@3, Hit@5 | 1.00, 1.00, 1.00 |
| File retrieval Recall@1, Recall@3, Recall@5 | 1.00, 1.00, 1.00 |
| File retrieval MRR | 1.00 |
| Citation presence | 0.89 |
| Citation validity | 0.78 |
| Citation coverage | 0.56 |
| Engineering hardening | PASS |

The engineering hardening checks cover upload edge cases, cleanup paths, streaming lifecycle and abort behavior, Qdrant initialization, and latency instrumentation.

## Citation metrics are structural

The citation aggregate intentionally includes fixtures for invalid citations, no citations, and partial coverage. Values are therefore not expected to be 1.0. They evaluate citation syntax, reference-range validity, and source coverage behavior; they do **not** establish that an answer is factually correct or that every cited source supports a claim.

## Test baselines

| Surface | Verified baseline |
| --- | --- |
| Backend | 285 passed; Ruff successful |
| Frontend | 68 passed; lint passes except an existing unchanged React effect warning; production build PASS |

## Run locally

```sh
cd backend
uv run python scripts/run_offline_evaluation.py
```

The offline runner is deterministic and avoids providers and the network. It verifies conversation query composition, selected-file retrieval isolation, synthetic Hybrid ownership, citation marker behavior, cleanup, streaming, Qdrant initialization, and request-local timing behavior. A separate provider-backed citation benchmark runner needs configured services and credentials.

## Production smoke verification

The final production smoke pass covered backend health, CORS, frontend API routing, Web and follow-up research, IndexedDB history and `/c/:id` restoration, file upload/retrieval, Hybrid sources, citation/source scoping, document/conversation cleanup, themes, and responsive Sources behavior. These checks validate deployed integration paths, not general factual accuracy.
