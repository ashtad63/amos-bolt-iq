# Amos 🐕

> A guide-dog chatbot for engineers exploring ultrasonic bolt-tension measurement and [Predictant's Bolt iQ](https://predictant.io/).

**Live demo (public):** [`https://ca-amos-public-eus2.wonderfulwave-798c6b35.eastus2.azurecontainerapps.io/`](https://ca-amos-public-eus2.wonderfulwave-798c6b35.eastus2.azurecontainerapps.io/)

Amos is a **hybrid LLM Wiki + RAG** chatbot. It's structured around an idea from [Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): instead of pure RAG retrieving raw fragments per query, an LLM agent maintains a curated markdown knowledge graph as documents are ingested. Sources stay immutable; the agent paraphrases, links, and flags contradictions. A ChromaDB vector index over the same documents provides a fallback for needle-in-haystack queries and primary-source citations.

## Architecture

```
                              ┌─ Wiki Layer ───────────────────────┐
                              │  wiki/                              │
   Source PDFs                │   index.md          (rebuilt        │
       │                      │   log.md             from FS)       │
       ▼                      │   contradictions.md                 │
  ingest/extract.py           │   pages/                            │
  ingest/ingest_agent.py ────►│     concepts/   ← paraphrased       │
   (gpt-4o-mini, strict JSON) │     products/      synthesis with   │
       │                      │     standards/     [src:id p.N]     │
       ▼                      │     applications/  citations        │
  rag/chunk.py                │     sources/                        │
  rag/embed.py ──────────────►│  chroma/   ← text-embedding-3-small │
                              └────────────────────┬────────────────┘
                                                   │
                                                   ▼
                              ┌─ Chat App (Chainlit) ──────────────┐
   user ──message──────────►  │  app/main.py                       │
                              │   ├─ rate_limit.py  (10/min, …)    │
                              │   ├─ budget.py      (cap $15/mo)   │
                              │   └─ agent.py  ── gpt-4o + tools:  │
                              │                  - read_wiki_index │
                              │                  - read_wiki_page  │
                              │                  - search_raw_chunks│
                              │     turn_log.py → Azure Blob       │
                              └────────────────────────────────────┘
                                                   │
                                                   ▼
                              ┌─ Azure ────────────────────────────┐
                              │  Container Apps (East US 2)        │
                              │   ca-amos-public-eus2  (open URL)  │
                              │   ca-amos-internal-eus2 (password) │
                              │  ACR · Storage · App Insights      │
                              └────────────────────────────────────┘
```

## Two deployments, one codebase

- **`amos-public`** — open URL, 7 cleared Predictant docs (marketing handouts, DNV certification, conference posters/papers, NASA patent reference). Rate-limited per IP; monthly OpenAI spend capped at $15.
- **`amos-internal`** — Chainlit password gate, full 51-doc corpus including 42 third-party academic papers. Used by Predictant team for internal research.

Each build comes from the same Dockerfile via a `VARIANT=public|full` build arg that selects which `wiki-*/` and `chroma-*/` directories to bake in.

## Why hybrid, not pure RAG?

Pure RAG re-discovers connections per query — knowledge accumulates nowhere. The Wiki layer is **compound**: each ingest enriches a persistent, interlinked graph; contradictions are flagged rather than silently overwritten. RAG is preserved as a fallback so engineers can still get verbatim primary-source citations. The two layers cover each other's failure modes — Wiki gives breadth and synthesis, RAG gives precise quotes.

## Cost controls (defense in depth)

| Layer | Mechanism | Trip point |
|---|---|---|
| OpenAI dashboard | Project-level hard cap | $20 / month |
| App-level meter | `app/budget.py`, persisted to Blob | $15 / month soft-pause |
| Per-IP limit | sliding-window counters | 10/min, 60/hour, 200/day |
| Global ceiling | shared counter across all IPs | 1,000 messages / day |

Worst case for a leaked link: even with 1,000 messages/day at ~$0.01 each = $10/day. Monthly budget meter trips at $15. Hard cap is the last line.

## Code layout

```
ingest/                  # Wiki ingestion pipeline
  extract.py             # pypdf + python-pptx → text with [page N] markers
  ingest_agent.py        # gpt-4o-mini, strict JSON schema actions
  rebuild_index.py       # Deterministic index.md from filesystem
  manifest_public.json   # Explicit list of public-cleared docs
  full_manifest.py       # Auto-generate full manifest from data/

rag/                     # RAG fallback layer
  chunk.py               # 500-token chunks, 50-token overlap, tiktoken
  embed.py               # text-embedding-3-small → ChromaDB persistent
  search.py              # k-NN retrieval with citations

app/                     # Chainlit chatbot
  main.py                # Chainlit hooks, starters, password gate
  agent.py               # OpenAI function-calling agent (max 5 iter)
  tools.py               # 3 tools wired to wiki + chroma
  rate_limit.py, budget.py, turn_log.py
  prompts/amos_system.md # Amos persona (warm, terse, cite-everything)

deploy/                  # Azure deployment
  provision.sh           # Idempotent: RG, ACR, Storage, App Insights, ACA env
  deploy.sh public|full  # Build via az acr build + create/update ACA app
  refresh.sh             # Add-a-doc → end-to-end refresh of both deployments

scripts/
  smoke_test_retrieval.py
  smoke_test_agent.py
  register-mcp-servers.sh
```

## Run locally

```bash
# 1. Create venv and install deps
py -3.11 -m venv .venv
.venv/Scripts/python -m pip install -e .

# 2. Provide secrets
cp .env.example .env  # then edit OPENAI_API_KEY

# 3. Ingest + embed the public corpus
.venv/Scripts/python -m ingest.ingest_agent --manifest ingest/manifest_public.json \
    --data-root data/predictant --wiki-out wiki-public --new-only
.venv/Scripts/python -m ingest.rebuild_index --wiki wiki-public
.venv/Scripts/python -m rag.embed --manifest ingest/manifest_public.json \
    --data-root data/predictant --chroma-out chroma-public --new-only

# 4. Run Chainlit
WIKI_PATH=wiki-public CHROMA_PATH=chroma-public chainlit run app/main.py
```

## Deploy

```bash
# One-time
bash deploy/provision.sh

# Per release (or after adding documents)
bash deploy/refresh.sh
```

## Adding new documents later

| Scenario | Where to put it | Edit `manifest_public.json`? | Updates which deploy? |
|---|---|---|---|
| Public Predictant doc | `data/predictant/` | yes, add doc ID | public + internal |
| Internal-only Predictant doc | `data/predictant/` | no | internal only |
| Academic / third-party | `data/academic/` | no | internal only |

Then `bash deploy/refresh.sh`.

## Stack

- **Inference**: OpenAI `gpt-4o-mini` (ingestion) and `gpt-4o` (chat)
- **Embeddings**: OpenAI `text-embedding-3-small` (1536-dim)
- **Vector store**: ChromaDB persistent (baked into the container image)
- **Chat framework**: Chainlit 1.3
- **Hosting**: Azure Container Apps, East US 2
- **Observability**: Application Insights, OpenTelemetry auto-instrumentation
- **Logging**: Per-turn JSONL append blob in Azure Storage

## License

Code is MIT. Source PDFs are not committed — each document remains under its own copyright.

---

Built as a weekend portfolio project, May 2026, by [Ashtad Javanmardi](https://github.com/ashtad63). Inspired by Andrej Karpathy's [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) idea.
