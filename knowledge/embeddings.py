from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-base-en-v1.5"

_model = SentenceTransformer(MODEL_NAME)


def create_embedding(text, is_query=False):
    if is_query:
        text = f"Represent this sentence for searching relevant passages: {text}"
    return _model.encode(text, normalize_embeddings=True)