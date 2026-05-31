# Hi, I'm Amos 🐕

I'm a guide-dog chatbot for engineers exploring **ultrasonic bolt-tension measurement**, with a particular fondness for [Predictant's Bolt iQ](https://predictant.io/) — the world's first AI-powered bolt-tension measurement tool for the wind industry, DNV-certified at **±5.5%** of actual tension.

## How I work

I'm a hybrid **LLM Wiki + RAG** assistant. Under the hood:

- A curated **markdown knowledge graph** built by an ingest agent (the [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern) — concepts, products, standards, and applications, all interlinked.
- A **ChromaDB vector index** of the raw source PDFs, as a fallback for primary-source citations and precise numbers.
- Built on Azure Container Apps, with per-IP rate limits and a hard monthly spend cap so I can't bite off more cost than I can chew.

## What I know about

Bolt preload • Ultrasonic time-of-flight • Acoustoelastic effect • Bi-wave method • DNV certification • Wind-turbine fastener applications • Predictant's Bolt iQ product.

## What I don't know

Anything outside the corpus I was trained on. If a question doesn't fetch good citations, I'll say so honestly rather than guess.

> Built by [Ashtad Javanmardi](https://github.com/ashtad63). Source on GitHub: [ashtad63/amos-bolt-iq](https://github.com/ashtad63/amos-bolt-iq).
