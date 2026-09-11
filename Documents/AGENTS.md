# AI Engineering Instructions

These instructions describe how the AI should assist during development of this project.

---

# Primary Goal

Help implement a production-quality offline AI Support Engineer Copilot.

Always prioritize architecture quality over writing code quickly.

---

# General Principles

Never overengineer.

Prefer simple solutions.

Implement incrementally.

Small safe commits are preferred.

Always preserve modularity.

Avoid unnecessary abstractions.

---

# Response Style

Keep responses concise.

Minimize token usage.

Do not generate unnecessary explanations.

Only expand when discussing architecture or trade-offs.

Avoid repeating previous context.

Don't edit code directly unless explicitly you are asked to, instead provide clear guidance on what should be edited as the goal is to understand each implementation step not have
AI implement the project, it's with AI's guidance

---

# Development Philosophy

Retrieval quality is more important than LLM quality.

The LLM should receive only high-quality evidence.

The LLM is never responsible for finding information.

---

# Retrieval Principles

Prefer deterministic retrieval before semantic retrieval.

Pipeline:

SQLite

↓

FTS5

↓

Evidence Builder

↓

FAISS

↓

Hybrid Ranking

↓

LLM

Never perform semantic search over the entire Jira database.

Always reduce candidate count first.

Expected candidate count:

Approximately 50–100 lexical matches before semantic ranking.

---

# Evidence Builder

Evidence Builder should remain independent from SQLite implementation.

Responsibilities include:

- deterministic ranking

- keyword relevance

- source weighting

- recency

- status weighting

- semantic similarity

Avoid embedding database-specific logic inside Evidence Builder.

---

# Coding Guidelines

Prefer readable code.

Prefer explicit naming.

Avoid clever implementations.

Avoid premature optimization.

Keep functions focused.

Preserve existing architecture unless a significant improvement exists.

---

# SQLite

FTS5 is the primary lexical search engine.

LIKE searches should not be reintroduced.

FTS tables should remain synchronized whenever database records change.

---

# Synchronization

Incremental sync is preferred.

Sync checkpoints should represent successfully processed source data.

Avoid checkpoint strategies that may skip records.

---

# Future Semantic Search

SQLite FTS5 retrieves lexical candidates.

FAISS provides semantic similarity.

Evidence Builder combines all ranking signals.

Only final evidence reaches the LLM.

---

# Long-Term Vision

The final assistant should behave similarly to an experienced senior Technical Support Engineer.

It should:

retrieve evidence

rank evidence

identify similar incidents

explain reasoning

propose investigation steps

draft customer responses

while remaining fully offline.

---

# AI Collaboration Rules

When suggesting changes:

Explain WHY before HOW.

Prefer modifying existing code over rewriting modules.

Avoid large refactors unless requested.

Preserve compatibility with existing project structure.

Always consider future scalability.

If multiple solutions exist:

Recommend the one with the best long-term architecture while minimizing unnecessary complexity.