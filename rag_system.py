import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Any
import os
from pathlib import Path


class RAGSystem:
    def __init__(self, collection_name="study_docs"):
        self.client = chromadb.Client()
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()

        try:
            self.collection = self.client.get_collection(collection_name)
        except:
            self.collection = self.client.create_collection(
                name=collection_name,
                embedding_function=self.embedding_fn
            )

    def chunk_document(self, text: str, chunk_size: int = 500) -> List[str]:
        """
        Simple chunking by character count with overlap
        """
        chunks = []
        overlap = 50
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            if chunk.strip():
                chunks.append(chunk)
        return chunks

    def ingest_directory(self, directory_path: str) -> int:
        """
        Ingest all documents from a directory
        """
        path = Path(directory_path)
        count = 0

        for file_path in path.rglob("*"):
            if file_path.suffix.lower() in {".md", ".txt"}:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    chunks = self.chunk_document(content)

                    for idx, chunk in enumerate(chunks):
                        chunk_id = f"{file_path.name}#chunk-{idx}"
                        self.collection.add(
                            documents=[chunk],
                            metadatas=[{
                                "source": file_path.name,
                                "chunk_id": chunk_id,
                                "chunk_index": idx
                            }],
                            ids=[chunk_id]
                        )
                        count += 1

        return count

    def retrieve(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Retrieve top-k relevant chunks
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )

        citations = []
        for i in range(len(results['documents'][0])):
            citations.append({
                "source": results['metadatas'][0][i]['source'],
                "chunk_id": results['metadatas'][0][i]['chunk_id'],
                "snippet": results['documents'][0][i][:200] + "..."
            })

        return citations

    def is_ready(self) -> bool:
        return self.collection.count() > 0