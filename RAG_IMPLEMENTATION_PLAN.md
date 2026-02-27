# Cell Avenue RAG Implementation Plan
## LangChain + FAISS + GPT-4o mini

## 1. Goal

Build a bilingual (English + Arabic) e-commerce RAG assistant for `https://cellavenuestore.com` using:

- LangChain for orchestration
- OpenAI embeddings
- FAISS for vector storage
- `gpt-4o-mini` for answer generation

Pipeline order (exactly as requested):

1. Load data (agreed scope)
2. Clean text
3. Chunk documents
4. Embed chunks
5. Save to FAISS
6. Chat with GPT-4o mini using retrieved context

---

## 2. Agreed Crawl Scope

## 2.1 Include (Priority 1 + Priority 2 + Arabic)

- Product pages:
  - `/product/*`
  - `/ar/product/*`
- Support/policy pages:
  - `/shipping-policy`
  - `/returns-replacements`
  - `/terms-and-conditions`
  - `/privacy-policy`
  - `/contact-us`
  - `/about-us`
- Brand/home/campaign/category enrichment:
  - `/home-05`
  - `/honor`
  - `/ar/honor`
  - `/ar/الرئيسية`
  - `/product-category/*`
  - `/ar/product-category/*`
  - `/blackfriday-2025`
  - `/valentine-2025`
  - `/huawei-gt-6-series`
  - `/honor-400-series`

## 2.2 Exclude

- Transaction/account pages:
  - `/cart*`, `/checkout*`, `/my-account*`, `/login*`, `/logout*`
  - `/register*`, `/password-reset*`, `/wishlist*`, `/compare*`, `/profile-*`
  - `/thank-you*`, `/thanks*`
- Low-value taxonomy/utility pages:
  - `/color-1/*`, `/kind/*`, `/product-tag/*`, `/capacity-gb/*`, `/author/*`
  - `/mobile_banners/*`, `/mobile_promotions/*`, `/screen_splashes/*`
- Pagination/sort/search params:
  - `/page/*`
  - `?per_page=`, `?orderby=`, `?add-to-cart=`, `?s=`, `?filter`
- Trap links:
  - any URL with `blackhole=`

---

## 3. Tech Stack

- Python 3.11+
- LangChain packages:
  - `langchain`
  - `langchain-openai`
  - `langchain-community`
  - `langchain-text-splitters`
- Vector store:
  - `faiss-cpu`
- API:
  - `fastapi`, `uvicorn`
- Utilities:
  - `pydantic`, `python-dotenv`, `orjson`, `tqdm`, `regex`
- Data loading:
  - Firecrawl (or your current crawler)

---

## 4. Project Structure

```text
e-commerce-rag/
  .env
  requirements.txt
  RAG_IMPLEMENTATION_PLAN.md
  app/
    config.py
    ingest/
      collect_urls.py
      load_pages.py
      clean_text.py
      chunk_docs.py
      build_faiss.py
    rag/
      retriever.py
      prompt.py
      chain.py
    api/
      main.py
    data/
      raw/
      cleaned/
      chunks/
      manifests/
    vectorstore/
      faiss_index/
```

---

## 5. Implementation Phases

## Phase 0: Environment Setup

1. Create `requirements.txt`.
2. Set `.env`:
   - `OPENAI_API_KEY=...`
   - `OPENAI_CHAT_MODEL=gpt-4o-mini`
   - `OPENAI_EMBEDDING_MODEL=text-embedding-3-large` (or `text-embedding-3-small` for lower cost)
   - crawler keys if needed
3. Validate keys with a small smoke test.

---

## Phase 1: Load Data (Agreed Scope)

Output: `app/data/raw/*.jsonl`

Each JSONL row:

```json
{
  "url": "https://cellavenuestore.com/product/honor-x9c/",
  "language": "en",
  "page_type": "product",
  "title": "HONOR X9c",
  "markdown": "...raw content...",
  "crawled_at": "2026-02-27T18:00:00Z"
}
```

Implementation notes:

- Start from sitemap + include paths.
- Apply exclude rules before scraping.
- Deduplicate URLs by canonical form.
- Keep `language` and `page_type` metadata from the beginning.

---

## Phase 2: Clean Text

Output: `app/data/cleaned/*.jsonl`

For this site, cleaning is critical. Remove:

- Repeated announcement/banner blocks
- Navigation/footer boilerplate (`Close`, `Scroll Up`, cart/search chrome)
- Shortcode artifacts (`[vc_row ...]`, `[contact-form-7 ...]`, `[wpum_login_form ...]`)
- reCAPTCHA/privacy boilerplate
- image-only and base64 placeholders
- repeated wishlist/quick-view CTA noise

Preserve:

- Product name, variants, specification rows, dimensions, battery/network details
- Policy clauses and contact information
- Arabic text as-is (no transliteration)

Add cleaning metadata:

- `cleaned_at`
- `cleaning_version`
- `content_hash`

---

## Phase 3: Chunking

Output: `app/data/chunks/chunks.jsonl`

Use LangChain splitters with different profiles by page type.

Recommended splitter:

- `RecursiveCharacterTextSplitter`

Recommended settings:

- Product pages:
  - `chunk_size=1200`
  - `chunk_overlap=180`
- Policy/support pages:
  - `chunk_size=1400`
  - `chunk_overlap=220`
- Category/brand/campaign pages:
  - `chunk_size=1000`
  - `chunk_overlap=150`

Separators (include Arabic punctuation):

- `["\n\n", "\n", ".", "?", "!", "،", "؛", " "]`

Chunk metadata per record:

- `doc_id`
- `url`
- `language`
- `page_type`
- `priority` (`P1` or `P2`)
- `chunk_id`
- `chunk_index`
- `source_title`
- `crawled_at`

---

## Phase 4: Embeddings + FAISS

Output: `app/vectorstore/faiss_index/`

1. Create `Document` objects from chunk JSONL.
2. Embed with `OpenAIEmbeddings`.
3. Build FAISS index:
   - `FAISS.from_documents(docs, embeddings)`
4. Save locally:
   - `vectorstore.save_local("app/vectorstore/faiss_index")`
5. Save manifest:
   - indexing timestamp
   - number of docs/chunks
   - embedding model
   - cleaning/chunking version

MVP indexing policy:

- Full rebuild daily (simplest and reliable for early stage).
- Move to incremental updates after baseline is stable.

---

## Phase 5: Retrieval + GPT-4o mini

Use LangChain retrieval chain.

Retriever config:

- `search_type="mmr"`
- `k=8`
- `fetch_k=40`
- optional metadata preference:
  - rank product and policy pages above category/campaign pages

LLM:

- `ChatOpenAI(model="gpt-4o-mini", temperature=0.1)`

Prompt policy:

- Answer only from retrieved context.
- If unknown, explicitly say not found.
- Return citations (URLs) for key claims.
- Keep language aligned with user query (`ar` or `en`).

Response schema:

```json
{
  "answer": "...",
  "citations": [
    "https://cellavenuestore.com/product/...",
    "https://cellavenuestore.com/shipping-policy/"
  ],
  "language": "en",
  "as_of": "2026-02-27T18:00:00Z"
}
```

---

## Phase 6: API Layer

Build FastAPI endpoints:

- `POST /chat`
  - input: `question`, optional `chat_history`
  - output: answer + citations + metadata
- `POST /reindex`
  - runs load -> clean -> chunk -> embed -> FAISS rebuild
- `GET /health`

Optional:

- `GET /index-info` to expose current index manifest

---

## Phase 7: Evaluation

Create an eval set (minimum 100 Q/A):

- 50 product questions
- 25 policy/support questions
- 25 Arabic questions

Track:

- Retrieval recall@k
- Citation correctness
- Faithfulness (groundedness)
- Arabic quality
- Latency (P50/P95)

Launch targets:

- Citation correctness >= 95%
- Hallucination <= 3%
- Recall@5 >= 85%
- P95 latency <= 4s

---

## Phase 8: Scheduling and Operations

Recrawl/index schedule:

- Product pages: every 6-24 hours
- Campaign pages: daily
- Policy pages: weekly

Operational controls:

- index version manifest
- rollback to previous FAISS snapshot
- structured logs with request IDs

---

## 6. Implementation Checklist

## 6.1 Data Pipeline

- [ ] Implement URL collector with include/exclude rules
- [ ] Implement raw loader to JSONL
- [ ] Implement cleaner with site-specific regex/normalization
- [ ] Implement chunker with page-type profiles
- [ ] Implement FAISS builder and manifest writer

## 6.2 RAG Runtime

- [ ] Implement retriever config (MMR + metadata-aware ranking)
- [ ] Implement GPT-4o mini chain with citation prompt
- [ ] Implement bilingual response behavior
- [ ] Implement `/chat` endpoint

## 6.3 Quality/Ops

- [ ] Build evaluation dataset
- [ ] Add latency and citation metrics
- [ ] Add scheduled `/reindex`
- [ ] Add backup/restore for FAISS index

---

## 7. Build Order (Strict)

Use this exact order to avoid rework:

1. **Load**
2. **Clean**
3. **Chunk**
4. **Embed**
5. **Save to FAISS**
6. **Wire retriever + GPT-4o mini**
7. **Expose API**
8. **Evaluate and tune**

---

## 8. Practical 7-Day Plan

Day 1:
- Project setup, env, dependencies
- URL policy and data loader

Day 2:
- Raw crawl run (English + Arabic)
- Validate include/exclude quality

Day 3:
- Cleaning pipeline with boilerplate removal
- Content sanity checks

Day 4:
- Chunking + metadata
- Build first FAISS index

Day 5:
- Retrieval chain + GPT-4o mini prompting
- FastAPI `/chat`

Day 6:
- Evaluation set + metrics
- Tune retriever/chunking/prompt

Day 7:
- Scheduled reindex job
- Hardening and handoff docs

---

## 9. Definition of Done

The implementation is done when:

- Agreed English + Arabic scope is indexed
- Retrieval returns relevant chunks with source URLs
- GPT-4o mini answers are grounded and cited
- FAISS index can be rebuilt and loaded reliably
- Evaluation thresholds are met

