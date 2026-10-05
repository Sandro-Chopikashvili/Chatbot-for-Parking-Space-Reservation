# Evaluation Report

## 1. Setup

- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (local)
- **Vector DB:** Milvus Lite
- **Documents:** 10 static Markdown files — 9 public, 1 private with test data
- **Dynamic data:** SQLite for prices, working hours, and availability
- **LLM:** Groq `openai/gpt-oss-120b`, temperature `0`
- **Golden set:** 30 questions labeled with the file(s) containing the answer
- **Production configuration:** chunk size `300`, overlap `50`, `k=3` — 33 chunks

### Metrics

- **Recall@K:** Percentage of relevant files found within the top K chunks.
- **Precision@K:** Percentage of retrieved chunks that come from relevant files.
- **MRR:** Average reciprocal rank of the first relevant chunk.

## 2. Retrieval Quality

| Chunk Size | k | Recall@K | Precision@K | MRR | p50 Latency | p95 Latency |
|---|---:|---:|---:|---:|---:|---:|
| 300 | 1 | 0.644 | 0.800 | 0.800 | 14 ms | 17 ms |
| 300 | 3 | **0.839** | **0.578** | **0.828** | 15 ms | 16 ms |
| 300 | 5 | 0.872 | 0.500 | 0.834 | 15 ms | 17 ms |
| 800 | 1 | 0.544 | 0.667 | 0.667 | 14 ms | 16 ms |
| 800 | 3 | 0.806 | 0.444 | 0.744 | 14 ms | 14 ms |
| 800 | 5 | 0.872 | 0.313 | 0.753 | 14 ms | 16 ms |

The selected configuration is **chunk size 300 with k=3**. It provides a strong balance between recall, precision, and ranking quality.

Increasing `k` from 3 to 5 improves recall from **0.839 to 0.872**, while precision decreases from **0.578 to 0.500**. The 300-token chunks also provide better precision and MRR than 800-token chunks.

Retrieval latency remains around **15 ms**, making vector search a small part of the overall response time.

## 3. End-to-End Performance

20 queries were tested: 10 using vector retrieval and 10 using SQL tools.

| Run | Errors | p50 | p95 |
|---|---:|---:|---:|
| 1 — Initial | 1/20 | 2.08 s | 7.55 s |
| 2 — Updated | **0/20** | 5.35 s | 13.67 s |

The main source of latency is the **LLM call**, while vector retrieval takes approximately 15 ms.

The first run included one `tool_use_failed` case where the model answered without using the required tool. The workflow was updated to:

- Retry tool-use failures up to 3 times.
- Require tool usage through the system prompt.
- Return a safe fallback message when tool execution cannot be completed.

The second run completed all 20 queries successfully. The additional latency is accepted to ensure responses are grounded in the application's data sources.

## 4. Guardrails

The system uses multiple protection layers:

1. **Input filter** — blocks known unsafe and prompt-injection patterns.
2. **Retrieval filter** — only public document chunks are available to the retriever.
3. **Restricted tools** — the LLM can only access predefined application tools.
4. **PII redaction** — assistant responses are scanned with Presidio before being returned.
5. **Booking-data allowlist** — the user's own booking information can remain visible in their response.

| Test | Result |
|---|---:|
| Direct attacks blocked | **10/10** |
| Normal questions allowed | **10/10** |
| Private chunks returned | **0/10** |
| PII remaining after redaction | **0/3** |
| Held-out attacks blocked by input filter | **2/10** |
| Held-out attacks leaking a secret end-to-end | **0/10** |

The guardrails work as a **defense-in-depth system**. Even when an input passes the initial filter, the retrieval restrictions, fixed tools, and output redaction provide additional protection.

## 5. Booking and Application Tests

The application also includes automated tests for the main application components:

- Booking field validation
- Car plate validation and normalization
- Date and reservation-duration validation
- SQLite price and working-hour queries
- Reservation creation
- Graph node configuration
- Input blocking
- PII redaction
- Vector document retrieval
- Private-document filtering

These tests provide automated coverage for the core booking, database, retrieval, graph, and security functionality.

## 6. Final Configuration

Based on the evaluation, the application uses:

- **Chunk size:** `300`
- **Chunk overlap:** `50`
- **Retriever k:** `3`
- **Embedding model:** `all-MiniLM-L6-v2`
- **Vector database:** Milvus Lite
- **Dynamic database:** SQLite
- **LLM temperature:** `0`
- **Tool-use retry:** up to 3 attempts
- **Output PII redaction:** enabled
- **Public-only retrieval:** enabled

This configuration provides grounded retrieval, protected document access, automated validation, and reliable tool-based responses.