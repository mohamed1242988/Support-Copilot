# 🧠 Offline AI Support Engineer Copilot

> **The Problem:** Enterprise SaaS support engineers waste up to 70% of their diagnostic time manually gathering context across fragmented tools (customer chats, engineering bugs, and developer wikis) before debugging even begins. This preparation bottleneck inflates Average Handling Time (AHT), causes repeated investigation efforts, and risks exposing customer data when uploading logs to public cloud AI tools.

---

## 🚀 Overview

Support Copilot is a **local-first, secure AI assistant** designed to help SaaS support engineers by:
- Automatically retrieving and parsing Freshdesk customer ticket history.
- Fetching and organizing related Jira engineering defects.
- Generating structured troubleshooting analysis and root-cause evidence.
- Drafting client-ready replies and internal team notes.

All data processing runs entirely offline, ensuring complete data security and offline compatibility.

---

## 🏗️ Core Architectural Pillars

1. **Modular Document Chunking Interface:** Pre-architected to ingest, clean, and divide raw data streams (Freshdesk logs, Jira comments, and Help Center documentation) into semantic chunks optimized for context-window constraints.
2. **Local Vector Database & Embedding Abstraction:** Features structural abstractions ready to integrate local embedding models and vector databases (such as FAISS or ChromaDB) for semantic similarity search.
3. **Cross-System Context Assembly:** Bridges customer conversations (Freshdesk REST API) and engineering issues (Jira JQL REST API).
4. **100% Local Inference & Security:** Runs Qwen3:4b via Ollama, preserving absolute data sovereignty and eliminating cloud subscription costs.

---

## 🏗️ System Architecture & Data Flow

```
                        User Investigation
                                │
                                ▼
                     Build Investigation Context
                                │
          ┌─────────────────────┴─────────────────────┐
          │                                           │
          ▼                                           ▼
   Freshdesk SQLite                           Jira REST API
          │                                           │
  Document Chunking                           ADF Document Parser
          │                                           │
  Vector Db / SQLite index                     Jira JQL Search
          │                                           │
          └─────────────────────┬─────────────────────┘
                                ▼
                      Context Assembly Layer
                                │
                                ▼
                        Prompt Generation
                                │
                                ▼
                     Ollama (Qwen3:4b Local)
                                │
                                ▼
                        AI Investigation
```

---

## 🧰 Tech Stack

- **Language:** Python 3.11+
- **Local AI Engine:** Ollama (Qwen3:4b LLM)
- **Local Database:** SQLite
- **Ticketing API:** Freshdesk REST API
- **Engineering API:** Jira Cloud REST API
- **Environment:** Windows / VS Code

---

## 📅 Roadmap

### Phase 1: Context & Prompts (Completed)
- Modular Python architecture.
- SQLite local cache sync (initial date bisection + incremental updated_at lookup).
- Jira JQL active keyword search & Atlassian Document Format (ADF) parser.
- Hallucination-resistant prompt structure.

### Phase 2: Knowledge Base Integration (Near Future)
- **High-Efficiency Python Search Engine:** Transitioning keyword indexing to weighted scoring heuristics (relevance, date metrics, and module tagging).
- **Interactive Module-Routing Router:** A prompt-gating workflow asking, *"Is this issue related to Module A, B, C, D, E, or General?"* to apply domain-specific system instructions (e.g., separating RDLC and UA report logic).
- Syncing Product Help Centers and internal KCS documents.

### Phase 3: Semantic Retrieval (Future Plan)
- Document chunking pipeline.
- Local vector database (ChromaDB or FAISS).
- Local embedding generation.
