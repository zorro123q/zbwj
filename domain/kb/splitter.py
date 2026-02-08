import os
from typing import List, Dict, Any
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
from flask import current_app

# 全局缓存模型，避免每次切分都重新加载（非常耗时）
_EMBEDDING_MODEL = None


def _get_embedding_model():
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        # 使用 m3e-base，效果好且速度快，适合中文
        # 如果你已经下载了模型，可以填本地绝对路径
        model_name = "moka-ai/m3e-base"
        print(f"Loading embedding model: {model_name} ...")

        _EMBEDDING_MODEL = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={'device': 'cpu'},  # 如果有显卡改为 'cuda'
            encode_kwargs={'normalize_embeddings': True}
        )
    return _EMBEDDING_MODEL


class SemanticTextSplitter:
    @staticmethod
    def split_text(text: str) -> List[str]:
        """
        使用语义差异进行切分。
        """
        if not text or not text.strip():
            return []

        embeddings = _get_embedding_model()

        # 初始化语义切分器
        # breakpoint_threshold_type="percentile": 基于差异度的百分位来切分
        # breakpoint_threshold_amount=90: 意味着只有语义差异最大的 10% 的地方才会被切断
        # 调高这个值(如 95)会让块更大，调低(如 60)会让块更碎
        text_splitter = SemanticChunker(
            embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=85
        )

        try:
            # LangChain 的 create_documents 会返回 Document 对象列表
            docs = text_splitter.create_documents([text])
            chunks = [doc.page_content for doc in docs]

            # 兜底策略：如果语义切分失败或只切出一大块（且长度过长），
            # 可以考虑在这里加一个基于字符长度的二次切分（RecursiveCharacterTextSplitter）
            # 但目前先保持纯语义切分
            return chunks
        except Exception as e:
            print(f"Semantic split failed, fallback to simple split: {e}")
            # 降级处理：简单的按换行符切分
            return [t for t in text.split("\n\n") if t.strip()]