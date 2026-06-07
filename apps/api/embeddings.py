from __future__ import annotations

import hashlib
import math
import re


EMBEDDING_DIMENSION = 96

SEMANTIC_ALIASES = {
    "保守": ["藏", "隐瞒", "不公开", "秘密"],
    "秘密": ["暗号", "旧信", "真相", "藏"],
    "亲人": ["父亲", "母亲", "家人"],
    "线索": ["旧信", "暗号", "证据", "真相", "钟楼"],
    "公开": ["真相", "说出", "揭开"],
    "危险": ["逼近", "追", "发现"],
}

SEMANTIC_CONCEPTS = {
    "concept_secret_family_clue": ["保守", "秘密", "亲人", "父亲", "母亲", "旧信", "暗号", "线索", "藏", "真相"],
    "concept_public_truth": ["公开", "真相", "揭开", "说出", "决定"],
    "concept_pursuit_danger": ["危险", "逼近", "追", "发现", "寻找", "钟楼"],
}


def embed_text(text: str, dimensions: int = EMBEDDING_DIMENSION) -> list[float]:
    vector = [0.0] * dimensions
    for token, weight in _weighted_tokens(text):
        bucket = _bucket(token, dimensions)
        sign = 1.0 if _bucket(f"{token}:sign", 2) == 0 else -1.0
        vector[bucket] += sign * weight
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(size))


def _weighted_tokens(text: str) -> list[tuple[str, float]]:
    tokens: list[tuple[str, float]] = []
    cleaned = re.sub(r"\s+", " ", text)
    for concept, terms in SEMANTIC_CONCEPTS.items():
        hits = sum(1 for term in terms if term in cleaned)
        if hits:
            tokens.append((concept, min(3.0, 1.2 + hits * 0.45)))
    for token in re.findall(r"[\u4e00-\u9fa5]{2,8}|[A-Za-z][A-Za-z0-9_'-]{2,}", cleaned):
        tokens.append((token, 1.0))
        aliases = SEMANTIC_ALIASES.get(token, [])
        tokens.extend((alias, 0.75) for alias in aliases)
        if any("\u4e00" <= char <= "\u9fff" for char in token):
            for index in range(max(0, len(token) - 1)):
                bigram = token[index : index + 2]
                tokens.append((bigram, 0.55))
                tokens.extend((alias, 0.35) for alias in SEMANTIC_ALIASES.get(bigram, []))
    return tokens


def _bucket(token: str, dimensions: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dimensions
