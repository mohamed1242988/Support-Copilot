# PSA AI — Enterprise Support Intelligence & Knowledge Copilot

> **Transform siloed support tickets and engineering issues into actionable, grounded intelligence.**

PSA AI is an enterprise-grade AI knowledge and operational assistant. It bridges the gap between **Customer Support (Freshdesk)** and **Engineering/Product (Jira)**, enabling support engineers, technical leads, and operations teams to investigate root causes, find historical resolution playbooks, and analyze operational trends in seconds.

---

## 💼 Business Value & Impact

* ⚡ **Drastic MTTR Reduction:** Surface exact historical root causes and resolution steps from years of past tickets in sub-seconds.
* 🔄 **Break Support & Engineering Silos:** Automatically link customer-facing Freshdesk conversations to backend Jira engineering bugs.
* 🛡️ **Zero-Hallucination Guarantee:** Grounded on strict **evidence-first retrieval**—the LLM reasons exclusively over retrieved factual records.
* 💰 **Zero Heavy Infrastructure Overhead:** Built on an embedded high-performance hybrid vector engine (SQLite + FTS5 + Dense Embeddings) without expensive SaaS vector DB subscriptions.

---

## 🚀 Key Capabilities

* 🔍 **Hybrid Multi-Stage Retrieval:** Combines lexical search (**SQLite FTS5 / BM25**) with dense semantic vector embeddings and reciprocal rank fusion (RRF) for high recall and precision.
* 💬 **Agentic Tool Calling & Reasoning:** Dynamically executes targeted database lookups, keyword searches, and semantic exploration based on user intent.
* 🧵 **Full Thread Conversation Stitching:** Ingests and indexes entire multi-turn ticket threads and internal private notes, bypassing third-party API truncation limits.
* 📈 **CSAT & Operational Tracking:** Correlates customer sentiment, satisfaction ratings, and agent resolution metrics with problem domains.
* 🔌 **Model Agnostic:** Seamlessly switch between **AWS Bedrock**, **Google Gemini**, **Groq (Llama 3)**, and **local Ollama models**.

---

## 💡 Real-World Use Cases & Queries

### 🔧 Deep Technical Investigation
> **User:** *"Why did SSO authentication fail for Customer X, and how was it resolved?"*  
> **PSA AI Action:** Performs hybrid search $\rightarrow$ identifies Freshdesk Ticket `#10452` $\rightarrow$ traverses link to Jira Bug `PSA-892`.  
> **Output:** Grounded explanation of the root cause (token expiration bug), the immediate workaround used, and the permanent Jira patch deployed.

### 📊 Management & Operational Insights
> **User:** *"What issues did Customer Acme Corp report over the last month?"*  
> **PSA AI Action:** Executes deterministic SQL query filtered by customer ID and date window $\rightarrow$ aggregates ticket status and categories.  
> **Output:** Structured breakdown of opened vs. resolved tickets, primary complaint areas, and average response times.

> **User:** *"What are the top categories of escalated tickets in the last two weeks?"*  
> **PSA AI Action:** Queries structured database fields (`relates_to`, `resolution_category`, `internal_status`) $\rightarrow$ generates grouped distribution.  
> **Output:** Summarized breakdown highlighting trend spikes (e.g., 45% Billing Integration, 30% API Timeouts) for leadership review.



## 🏗️ Architecture

```text
┌─────────────────┐      ┌──────────────┐
│ Freshdesk API   │      │   Jira API   │
└────────┬────────┘      └───────┬──────┘
         │                       │
         └───────────┬───────────┘
                     ▼
          [ Resilient Data Sync ]
          (Rate Limiting & Window Splitting)
                     │
                     ▼
       ┌───────────────────────────┐
       │   SQLite Storage Engine   │
       │ ───────────────────────── │
       │ • Structured Tables       │
       │ • FTS5 Full-Text Index    │
       │ • Dense Vector Embeddings │
       └─────────────┬─────────────┘
                     │
                     ▼
          [ Hybrid Retriever ]
       (Lexical BM25 + Vector Search + RRF)
                     │
                     ▼
         [ Grounded Evidence Pack ]
                     │
                     ▼
       [ LLM Agent / Tool Execution ]
         (Bedrock / Gemini / Groq / Ollama)
                     │
                     ▼
             [ PSA AI Web UI ]
