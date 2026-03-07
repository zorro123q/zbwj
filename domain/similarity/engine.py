import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any

_MODEL_CACHE = {}


def get_model(model_name: str = "moka-ai/m3e-base"):
    if model_name not in _MODEL_CACHE:
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]


class SimilarityEngine:
    def __init__(self, model_name: str = "moka-ai/m3e-base"):
        self.model_name = model_name

    def _sliding_window(self, text: str, chunk_size=300, overlap=50) -> List[Dict[str, Any]]:
        """滑动窗口切片，保留原文和位置信息"""
        if not text:
            return []
        chunks = []
        text_len = len(text)
        for i in range(0, text_len, chunk_size - overlap):
            chunk_text = text[i: i + chunk_size]
            if len(chunk_text) < 20:
                continue
            chunks.append({
                "text": chunk_text,
                "start": i,
                "end": i + len(chunk_text)
            })
        return chunks

    def compare_documents(self, text_a: str, text_b: str) -> Dict[str, Any]:
        """对比两个文档，返回相似度报告"""
        model = get_model(self.model_name)

        chunks_a = self._sliding_window(text_a)
        chunks_b = self._sliding_window(text_b)

        if not chunks_a or not chunks_b:
            return {"overall_similarity": 0.0, "duplicate_count": 0, "segments": []}

        texts_a = [c["text"] for c in chunks_a]
        texts_b = [c["text"] for c in chunks_b]

        embeddings_a = model.encode(texts_a, normalize_embeddings=True)
        embeddings_b = model.encode(texts_b, normalize_embeddings=True)

        similarity_matrix = np.inner(embeddings_a, embeddings_b)

        threshold = 0.85
        duplicate_segments = []
        covered_indices_a = set()

        for idx_a, scores in enumerate(similarity_matrix):
            max_score = np.max(scores)
            if max_score > threshold:
                idx_b = np.argmax(scores)
                if idx_a not in covered_indices_a:
                    duplicate_segments.append({
                        "doc_a_chunk": chunks_a[idx_a],
                        "doc_b_chunk": chunks_b[idx_b],
                        "score": float(max_score)
                    })
                    covered_indices_a.add(idx_a)

        # -----------------------------------------------------
        # 核心优化：区间合并算法，精确计算真实的重复字符数
        # -----------------------------------------------------
        intervals = []
        for idx in covered_indices_a:
            chunk = chunks_a[idx]
            intervals.append([chunk["start"], chunk["end"]])

        total_dup_len_a = 0
        if intervals:
            # 按起始位置排序
            intervals.sort(key=lambda x: x[0])
            merged = [intervals[0]]
            for current in intervals[1:]:
                prev = merged[-1]
                if current[0] <= prev[1]:  # 发生重叠
                    prev[1] = max(prev[1], current[1])
                else:
                    merged.append(current)
            # 累加合并后不重叠的实际字符长度
            total_dup_len_a = sum(iv[1] - iv[0] for iv in merged)

        total_len_a = len(text_a)
        overall_score = min(total_dup_len_a / total_len_a, 1.0) if total_len_a > 0 else 0.0

        # 按相似度从高到低排序，把最像的放在前面
        duplicate_segments.sort(key=lambda x: x["score"], reverse=True)

        return {
            "overall_similarity": round(overall_score, 4),
            "duplicate_count": len(duplicate_segments),
            "segments": duplicate_segments[:100]  # 返回前100个证据渲染到前端
        }