import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any

# 使用单例模式或全局变量缓存模型，避免每次请求都重新加载（非常耗时）
_MODEL_CACHE = {}


def get_model(model_name: str = "moka-ai/m3e-base"):
    if model_name not in _MODEL_CACHE:
        # 第一次调用时加载模型，建议下载模型到本地某个目录
        # 如果是内网环境，请手动下载模型并填写绝对路径
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]


class SimilarityEngine:
    def __init__(self, model_name: str = "moka-ai/m3e-base"):
        self.model_name = model_name

    def _sliding_window(self, text: str, chunk_size=300, overlap=50) -> List[Dict[str, Any]]:
        """
        滑动窗口切片，保留原文和位置信息
        """
        if not text:
            return []

        chunks = []
        text_len = len(text)
        for i in range(0, text_len, chunk_size - overlap):
            chunk_text = text[i: i + chunk_size]
            if len(chunk_text) < 20:  # 忽略过短的碎片
                continue
            chunks.append({
                "text": chunk_text,
                "start": i,
                "end": i + len(chunk_text)
            })
        return chunks

    def compare_documents(self, text_a: str, text_b: str) -> Dict[str, Any]:
        """
        对比两个文档，返回相似度报告
        """
        model = get_model(self.model_name)

        # 1. 切片
        chunks_a = self._sliding_window(text_a)
        chunks_b = self._sliding_window(text_b)

        if not chunks_a or not chunks_b:
            return {"score": 0.0, "details": []}

        # 2. 提取纯文本列表用于向量化
        texts_a = [c["text"] for c in chunks_a]
        texts_b = [c["text"] for c in chunks_b]

        # 3. 向量化 (Encode)
        embeddings_a = model.encode(texts_a, normalize_embeddings=True)
        embeddings_b = model.encode(texts_b, normalize_embeddings=True)

        # 4. 计算相似度矩阵 (Cosine Similarity)
        # matrix[i][j] 表示 A中第i段 与 B中第j段 的相似度
        similarity_matrix = np.inner(embeddings_a, embeddings_b)

        # 5. 提取高相似片段
        threshold = 0.85  # 判定为重复的阈值
        duplicate_segments = []
        total_dup_len_a = 0

        # 记录A中已经判定为重复的索引，防止重复计算
        covered_indices_a = set()

        for idx_a, scores in enumerate(similarity_matrix):
            max_score = np.max(scores)
            if max_score > threshold:
                idx_b = np.argmax(scores)

                # 简单记录（实际生产中可能需要做区间合并）
                if idx_a not in covered_indices_a:
                    duplicate_segments.append({
                        "doc_a_chunk": chunks_a[idx_a],
                        "doc_b_chunk": chunks_b[idx_b],
                        "score": float(max_score)
                    })
                    total_dup_len_a += len(chunks_a[idx_a]["text"])
                    covered_indices_a.add(idx_a)

        # 6. 计算整体相似度 (基于A文档的重复覆盖率)
        total_len_a = len(text_a)
        overall_score = 0.0
        if total_len_a > 0:
            # 注意：简单的长度累加可能会因为滑动窗口重叠而偏大，这里做个简化
            # 更严谨的做法是合并区间后再计算长度
            overall_score = min(total_dup_len_a / total_len_a, 1.0)

        return {
            "overall_similarity": round(overall_score, 4),
            "duplicate_count": len(duplicate_segments),
            "segments": duplicate_segments[:50]  # 只返回前50个证据，避免JSON过大
        }