from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.feature_extraction import FeatureHasher


HASH_BINS = 32_768


def make_hasher() -> FeatureHasher:
    return FeatureHasher(n_features=HASH_BINS, input_type="dict", alternate_sign=False, dtype=np.float32)


def hashed_row(row: dict[str, Any]) -> dict[str, float]:
    """Turn categorical feature dictionaries into a bounded sparse hashing space."""
    output: dict[str, float] = {}
    for key, value in row.items():
        if value is None or value is False or value == "":
            continue
        if value is True:
            output[str(key)] = 1.0
        elif isinstance(value, (int, float)):
            output[f"{key}={value}"] = 1.0
        else:
            output[f"{key}={value}"] = 1.0
    return output
