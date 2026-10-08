# Evaluation

The measured run is `backend/tests/test_evaluation.py`. It uses the fake language-model provider and the deterministic embedder, so it does not call a hosted model and it does not score answers against a human rubric. The fake provider repeats the top retrieved chunk. That is enough to check which model ran and whether the cache reused the answer.

Questions are listed in `data/evaluation/questions.json`.

| Setup | What the test observed |
| --- | --- |
| Plain RAG | The short leave question uses `SMALL_MODEL`, `cache_hit` is false, and the answer cites the uploaded leave text. |
| RAG plus cache | The same question again is a cache hit, the model stays `SMALL_MODEL`, and the answer text matches the first response. |
| RAG plus routing | The compare/why question uses `LARGE_MODEL` and `cache_hit` is false. |
| RAG plus cache and routing | That compare/why question again is a cache hit and still reports `LARGE_MODEL`. |

Cost follows the price table. One million input tokens and one million output tokens cost `input_price + output_price`. Changing `SMALL_MODEL_PRICE` and `SMALL_MODEL_OUTPUT_PRICE` changes that sum without a code edit. A cache hit stores estimated cost `0` and records the first call's cost as `cost_saved`.

Latency depends on the machine, so this file does not freeze a millisecond number. The dashboard test checks that average latency and P95 are computed from the same `query_logs` rows.
