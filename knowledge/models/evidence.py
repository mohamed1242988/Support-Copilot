import dataclasses
import re
import typing

from knowledge.models.document import Document

@dataclasses.dataclass
class Evidence:
    document: Document
    score: float
    score_breakdown: dict[str, float]
    reason: str
    retrieval_method: str


class EvidenceBuilder:
    def __init__(self, max_documents: int = 3):
        self.max_documents = max_documents

    def rank(
        self,
        query: str,
        documents: typing.List[Document]
    ) -> typing.List[Evidence]:
        """
        Build a ranked evidence list from retrieved documents.
        """
        print(f"Evidence received: {len(documents)} document(s)")

        documents = self._deduplicate(documents)

        evidence = []
        for doc in documents:
            breakdown = self._score_breakdown(query, doc)
            evidence.append(
                Evidence(
                    document=doc,
                    score=breakdown["final_score"],
                    score_breakdown=breakdown,
                    reason="Hybrid (Lexical & Semantic) ranking",
                    retrieval_method="hybrid"
                )
            )

        evidence.sort(key=lambda e: e.score, reverse=True)

        return evidence

    def build(
        self,
        query: str,
        documents: typing.List[Document]
    ) -> typing.List[Evidence]:
        """Return the top-ranked evidence for the prompt."""
        return self.rank(query, documents)[:self.max_documents]

    def _deduplicate(
        self,
        documents: typing.List[Document]
    ) -> typing.List[Document]:
        seen = set()
        unique = []

        for doc in documents:
            key = (doc.source, doc.id)

            if key not in seen:
                seen.add(key)
                unique.append(doc)

        return unique

    def _tokenize(
        self,
        text: str
    ) -> typing.List[str]:
        """
        Normalize text into lowercase word tokens.
        """

        return re.findall(r"\w+", text.lower())

    def _score_breakdown(
        self,
        query: str,
        document: Document
    ) -> dict[str, float]:

        query_tokens = list(dict.fromkeys(self._tokenize(query)))

        title_tokens = self._tokenize(document.title)
        content_tokens = self._tokenize(document.content)
        primary_content_tokens = self._tokenize(
            document.get_metadata("primary_content", document.content)
        )

        lexical_score = document.get_metadata("lexical_score", 0.0)
        semantic_score = document.get_metadata("semantic_score", 0.0)

        hybrid_base = (0.5 * lexical_score) + (0.5 * semantic_score)
        hybrid_contribution = hybrid_base * 60
        phrase_bonus = self._phrase_score(
            query_tokens,
            title_tokens,
            content_tokens
        ) / 2
        title_bonus = min(5, self._title_score(
            query_tokens,
            title_tokens
        ))
        content_bonus = min(5, self._content_score(
            query_tokens,
            content_tokens
        ))
        coverage_score, has_complete_match = self._coverage_score(
            query_tokens,
            title_tokens,
            primary_content_tokens,
            document.get_metadata("term_statistics", {}),
        )
        coverage_bonus = coverage_score * 2.5
        complete_match_bonus = 5.0 if has_complete_match else 0.0
        weak_match_penalty = self._weak_match_penalty(
            query_tokens,
            title_tokens,
            content_tokens
        )
        final_score = (
            hybrid_contribution + phrase_bonus + title_bonus +
            content_bonus + coverage_bonus + complete_match_bonus +
            weak_match_penalty
        )

        return {
            "bm25_rank": document.get_metadata("bm25_rank", 0.0),
            "lexical_rank": document.get_metadata("lexical_rank", 0.0),
            "lexical_score": lexical_score,
            "semantic_score": semantic_score,
            "hybrid_base": hybrid_base,
            "hybrid_contribution": hybrid_contribution,
            "phrase_bonus": phrase_bonus,
            "title_bonus": title_bonus,
            "content_bonus": content_bonus,
            "coverage_bonus": coverage_bonus,
            "complete_match_bonus": complete_match_bonus,
            "weak_match_penalty": weak_match_penalty,
            "final_score": final_score,
        }

    def _phrase_score(
        self,
        query_tokens,
        title_tokens,
        content_tokens
    ) -> float:

        query = " ".join(query_tokens)

        title = " ".join(title_tokens)
        content = " ".join(content_tokens)

        if query in title:
            return 20

        if query in content:
            return 10

        return 0

    def _title_score(
        self,
        query_tokens,
        title_tokens
    ) -> float:

        score = 0

        title_words = set(title_tokens)

        for word in query_tokens:
            if word in title_words:
                score += 5

        return score

    def _content_score(
        self,
        query_tokens,
        content_tokens
    ) -> float:

        score = 0

        for word in query_tokens:
            score += content_tokens.count(word)

        return score

    def _coverage_score(
        self,
        query_tokens,
        title_tokens,
        content_tokens,
        term_statistics
    ) -> tuple[float, bool]:

        scored_terms = [
            word
            for word in query_tokens
            if word in term_statistics
        ] or query_tokens

        if not scored_terms:
            return 0, False

        title_words = set(title_tokens)
        content_words = set(content_tokens)
        total_weight = 0.0
        matched_weight = 0.0
        matched_terms = 0

        for word in scored_terms:
            term_idf = term_statistics.get(word, {}).get("idf", 1.0)
            total_weight += term_idf
            if word in title_words or word in content_words:
                matched_weight += term_idf
                matched_terms += 1

        coverage = matched_weight / total_weight

        return coverage * 10, matched_terms == len(scored_terms)

    def _weak_match_penalty(
        self,
        query_tokens,
        title_tokens,
        content_tokens
    ) -> float:

        if len(query_tokens) <= 1:
            return 0

        matched = 0

        title_words = set(title_tokens)
        content_words = set(content_tokens)

        for word in query_tokens:
            if word in title_words or word in content_words:
                matched += 1

        if matched <= 1:
            return -5

        return 0
