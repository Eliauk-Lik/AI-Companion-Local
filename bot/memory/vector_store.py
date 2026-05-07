"""
向量记忆存储模块

基于 ChromaDB 实现长期记忆的存储与检索
"""

import chromadb
from chromadb.config import Settings
import hashlib
from typing import List, Dict, Optional


class MemoryStore:
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="conversation_memory",
            metadata={"hnsw:space": "cosine"}
        )

    def _hash_content(self, content: str) -> str:
        """为对话内容生成唯一 ID"""
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def add_memory(self, user_input: str, assistant_reply: str, metadata: Optional[Dict] = None):
        """
        存储一轮对话作为记忆
        """
        combined = f"用户: {user_input}\n助手: {assistant_reply}"
        doc_id = self._hash_content(combined)

        # 合并元数据
        meta = metadata or {}
        meta.update({
            "user_input": user_input[:200],
            "assistant_reply": assistant_reply[:200]
        })

        self.collection.upsert(
            documents=[combined],
            metadatas=[meta],
            ids=[doc_id]
        )

    def retrieve_relevant(self, query: str, top_k: int = 5) -> List[str]:
        """
        根据当前对话查询最相关的历史记忆
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )
        if results['documents'] and results['documents'][0]:
            return results['documents'][0]
        return []

    def clear_all(self):
        """清空所有记忆（慎用）"""
        self.client.delete_collection("conversation_memory")
        self.collection = self.client.get_or_create_collection(
            name="conversation_memory",
            metadata={"hnsw:space": "cosine"}
        )


# 单例模式，全局共享
_memory_instance = None

def get_memory_store(persist_dir: str = "./chroma_db") -> MemoryStore:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = MemoryStore(persist_dir)
    return _memory_instance