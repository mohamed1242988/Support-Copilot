import faiss
import numpy as np


class VectorStore:

    def __init__(self, dimension):
        self.index = faiss.IndexFlatIP(dimension)
        self.documents = []


    def add(self, embeddings, documents):
        self.index.add(np.array(embeddings))
        self.documents.extend(documents)


    def search(self, query_embedding, top_k=5):
        scores, indexes = self.index.search(
            np.array([query_embedding]),
            top_k
        )

        results = []

        for score, idx in zip(scores[0], indexes[0]):
            results.append(
                {
                    "document": self.documents[idx],
                    "score": float(score)
                }
            )

        return results