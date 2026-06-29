"""
retrieve.py
Retrieval + generation using the free Hugging Face Inference API.
Needs a free HF_TOKEN (set as a Streamlit secret when deployed).
"""

import os
from sentence_transformers import SentenceTransformer
import chromadb
from huggingface_hub import InferenceClient

from ingest import DB_PATH, COLLECTION_NAME, EMBEDDING_MODEL

LLM_MODEL = "google/gemma-2-2b-it"
_embedding_model = None
_db_client = None
_hf_client = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def _get_collection():
    global _db_client
    if _db_client is None:
        _db_client = chromadb.PersistentClient(path=DB_PATH)
    return _db_client.get_collection(COLLECTION_NAME)


def _get_hf_client():
    global _hf_client
    if _hf_client is None:
        token = os.environ.get("HF_TOKEN")
        _hf_client = InferenceClient(model=LLM_MODEL, token=token, provider="hf-inference")
    return _hf_client


def retrieve_chunks(question, top_k=4):
    model = _get_embedding_model()
    collection = _get_collection()
    query_embedding = model.encode(question).tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k)
    chunks = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        chunks.append({"text": doc, **meta})
    return chunks


def answer_with_rag(question, top_k=4):
    chunks = retrieve_chunks(question, top_k=top_k)
    if not chunks:
        return "No indexed articles yet — click 'Refresh news index' in the sidebar first.", []

    context = "\n\n".join(
        f"[{i + 1}] ({c['source']}) {c['text']}" for i, c in enumerate(chunks)
    )
    prompt = (
        "Answer the question using ONLY the numbered context below. "
        "If the context doesn't contain the answer, say so plainly instead of guessing. "
        "Cite sources inline using their bracket numbers, e.g. [1].\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )

    client = _get_hf_client()
    response = client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
    )
    return response.choices[0].message.content, chunks


def answer_without_rag(question):
    client = _get_hf_client()
    response = client.chat_completion(
        messages=[{"role": "user", "content": question}],
        max_tokens=400,
    )
    return response.choices[0].message.content
