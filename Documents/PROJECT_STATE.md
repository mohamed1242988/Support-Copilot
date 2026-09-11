# Offline AI Support Engineer Copilot

## Project Goal

Build a fully local AI Support Engineer Copilot that retrieves the best historical evidence from enterprise systems before asking the LLM to answer.

The LLM should NOT perform retrieval.

The retrieval pipeline should become progressively more intelligent while minimizing prompt size and inference time.

---

# Technology Stack

Language:
- Python

Database:
- SQLite

AI:
- Ollama
- Qwen3:4b
- Gemini API (current integration in progress)

---

# Current Architecture

SQLite

↓

Retriever

↓

Evidence Builder

↓

Prompt Builder

↓

Ollama

---

# Target Architecture

SQLite

↓

SQLite FTS5

↓

FAISS Semantic Search (only on FTS candidates)

↓

Evidence Builder / Hybrid Ranking

↓

Prompt Builder

↓

Ollama

---

# Supported Systems

## Freshdesk

Status:
Completed

Capabilities:

- Initial sync
- Incremental sync
- SQLite storage
- Ticket retrieval
- Conversation retrieval
- Local search
- Adapter conversion
- Customer ID/name extraction for customer-level issue consolidation

Tables:

tickets

conversations

---

## Jira

Status:
Completed

Capabilities:

- Initial sync
- Incremental sync
- Pagination
- Local storage
- On-demand comments

Tables:

jira_issues

jira_comments

sync_state

---

# Sync Strategy

Freshdesk

Current:
Incremental sync using sync_state.

Checkpoint equals the latest Freshdesk updated_at successfully processed.

This prevents missing issues during incremental synchronization.
---

Jira

Stores:

jira_<PROJECT>_last_sync

Example:

jira_UA_last_sync

Checkpoint equals the latest Jira updated_at successfully processed.

This prevents missing issues during incremental synchronization.

---

# SQLite FTS5

Status:
Completed

Virtual tables:

freshdesk_fts

jira_fts

Population is automatic whenever data is saved.

Implemented in:

save_ticket()

save_conversations()

save_jira_issue()

save_jira_comment()

One-time rebuild completed for existing data.

---

# Search

Current implementation:

search_local_tickets()

search_local_jira()

Both now use SQLite FTS5.

Freshdesk searches:

- Ticket subjects
- Ticket descriptions
- Conversations

Returns:

Freshdesk tickets.

Jira searches:

- Summary
- Description
- Comments

Returns:

Jira issues.

---

# Evidence Builder

Responsibilities:

- Deduplicate
- Deterministic scoring
- Ranking
- Return top evidence

Currently independent from retrieval implementation.

---

# Current Retrieval Flow

User Query

↓

Freshdesk FTS

↓

Jira FTS

↓

Ensure Jira Comments

↓

Documents

↓

Evidence Builder

↓

Prompt Builder

↓

Ollama

---

# Retrieval Quality Tuning

Status:
In progress — practical search evaluation using `main_test.py`.

Current flow:

User query
↓
Clean meaningful terms (small stop-word list)
↓
FTS5 corpus statistics per source
↓
Progressive FTS5 retrieval:
all_terms → anchor_three_terms → anchor_two_terms → fallback_or
↓
BM25 lexical score + FAISS semantic score
↓
Evidence Builder hybrid ranking

Implemented:

- FTS5 `AND` search is attempted before relaxed retrieval.
- Per-source document frequency and IDF diagnostics are logged.
- Search diagnostics print retrieval query, stage, anchors, and term statistics.
- Spell correction was removed because it changed valid domain terms:
  `MaryKay → mayday`, `Boomi → boom`.
- Evidence coverage is IDF-weighted rather than uniform.
- Complete meaningful-query matches receive a bounded +5 Evidence Builder bonus.
- Implemented Coverage scoring only on Tickets title and descritpion (Removed comments from being considered in scoring)

Known findings:

- Exact `all_terms` retrieval produces highly relevant results for:
  `MaryKay Boomi process issue`.
- `phrase=0` is expected unless the complete query appears consecutively.
- `lexical=0` can mean lowest relative BM25 score, not zero lexical matches.
- Current fallback expands until 50 candidates by replacing the prior stage’s result set.
  This can let broad `OR` candidates dilute strict results.
  
  

# Current Status

Completed

✔ Freshdesk Sync

✔ Jira Sync

✔ Incremental Sync

✔ SQLite Storage

✔ FTS5

✔ FTS Population

✔ Local Retrieval

✔ Evidence Builder

✔ BM25 lexical ranking

✔ BM25-informed evidence ranking

✔ FAISS Semantic Search

✔ Hybrid ranking

✔ FTS5 progressive retrieval diagnostics

✔ Per-source IDF calculation

✔ IDF-weighted evidence coverage

✔ Complete-query-match bonus

✔ Spell correction removed from retrieval

◐ Retrieval fallback quality tuning in progress

---

# Immediate Next Step




---
# Future Improvement

- Calibrate source-specific lexical relevance thresholds using real query evaluations, so weak Freshdesk or Jira candidates are excluded before prompt construction without relying onrigid token-match rules.


# Future Cleanup

- Consolidate and analyze issues by customer using Freshdesk customer ID/name metadata.
- Improve synchronization scheduling so sync is executed daily rather than on every application start.
- Build engineering prompts embedded in the project to classify between the product modules to make the AI more project customized to understand which module exactly the question/issue relates to, instead of being a general AI tool.
- Develop project-specific engineering prompts to classify queries and issues by product module, enabling the AI to understand the exact module involved rather than functioning as a general-purpose AI tool.
- Explore retrieving monthly data for specific customers, classifying their queries by product module, and generating structured insights that can support multiple use cases, such as identifying customer pain points, recommending targeted training, and potentially suggesting customized solutions for CSMs to propose.

## Recent Updates (2026-09-03)

- Added duplicate‑call detection and `seen_calls` set to prevent infinite tool‑call loops.
- Implemented `max_iterations = 3` to cap tool‑call cycles per turn.
- Initialized `conversation_history: List[Dict] = []` in the REPL to preserve context across turns.
- Added JSON‑to‑text formatter for ticket list answers (produces “Ticket {id}: {title}”).
- Created test scripts `scratch/test_run_agent.py` and `scratch/run_autodesk_query.py` to verify core functionality.
- Updated `ai_entry.py` imports and removed duplicate `json` import.
- Added comprehensive sanity‑test scripts and ensured all files compile without errors.
