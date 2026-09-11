from knowledge.embeddings import create_embedding
from knowledge.vector_store import VectorStore

documents = [
    "Invoice generation tab has a bug"
]

embeddings = [create_embedding(doc) for doc in documents]

store = VectorStore(dimension=768)
store.add(embeddings, documents)

query = "Invoce creation fails"

query_embedding = create_embedding(query, is_query=True)

results = store.search(query_embedding, top_k=1)

for result in results:
    print(result)
