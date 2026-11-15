from __future__ import annotations

import re
from dataclasses import dataclass


TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)*|[^\W\d_]+(?:['’\-][^\W\d_]+)*|[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    sentence_id: int


def tokenize(text: str) -> list[Token]:
    """Deterministic Unicode tokenizer retaining offsets into the untouched input string."""
    matches = list(TOKEN_RE.finditer(text))
    result: list[Token] = []
    sentence = 0
    previous: re.Match[str] | None = None
    for match in matches:
        if previous is not None:
            gap = text[previous.end():match.start()]
            initial_period = (previous.group() == "." and len(result) >= 2
                              and result[-2].text.isalpha() and len(result[-2].text) == 1)
            if previous.group() in {"?", "!"} or (previous.group() == "." and not initial_period) or "\n" in gap:
                sentence += 1
        result.append(Token(match.group(), match.start(), match.end(), sentence))
        previous = match
    return result


def sentence_bounds(text: str, tokens: list[Token], token_index: int) -> tuple[int, int, str]:
    if token_index < 0 or token_index >= len(tokens):
        raise IndexError("token index out of range")
    sid = tokens[token_index].sentence_id
    first = token_index
    last = token_index
    while first > 0 and tokens[first - 1].sentence_id == sid:
        first -= 1
    while last + 1 < len(tokens) and tokens[last + 1].sentence_id == sid:
        last += 1
    start, end = tokens[first].start, tokens[last].end
    return start, end, text[start:end]


def char_shape(token: str) -> str:
    chars = []
    for char in token:
        if char.isupper():
            shape = "X"
        elif char.islower():
            shape = "x"
        elif char.isdigit():
            shape = "d"
        else:
            shape = char
        if not chars or chars[-1] != shape:
            chars.append(shape)
    return "".join(chars)[:20]


def _sentence_ranges(tokens: list[Token]) -> dict[int, tuple[int, int]]:
    ranges: dict[int, tuple[int, int]] = {}
    for index, token in enumerate(tokens):
        if token.sentence_id not in ranges:
            ranges[token.sentence_id] = (index, index)
        else:
            ranges[token.sentence_id] = (ranges[token.sentence_id][0], index)
    return ranges


def token_feature_rows(tokens: list[Token]) -> list[dict[str, str | bool | int]]:
    ranges = _sentence_ranges(tokens)
    return [token_features(tokens, i, ranges) for i in range(len(tokens))]


def token_features(tokens: list[Token], index: int,
                   sentence_ranges: dict[int, tuple[int, int]] | None = None) -> dict[str, str | bool | int]:
    token = tokens[index]
    word = token.text
    ranges = sentence_ranges if sentence_ranges is not None else _sentence_ranges(tokens)
    sentence_start, sentence_end = ranges[token.sentence_id]
    lower = word.casefold()
    features: dict[str, str | bool | int] = {
        "bias": "1", "word": word, "lower": lower,
        "prefix2": lower[:2], "prefix3": lower[:3], "prefix4": lower[:4],
        "suffix2": lower[-2:], "suffix3": lower[-3:], "suffix4": lower[-4:],
        "shape": char_shape(word), "is_title": word.istitle(), "is_upper": word.isupper(),
        "has_digit": any(c.isdigit() for c in word), "is_digit": word.isdigit(),
        "sentence_start": index == sentence_start, "sentence_end": index == sentence_end,
        "sentence_length_bucket": min(sentence_end - sentence_start + 1, 40) // 5,
        "position_bucket": min(index - sentence_start, sentence_end - index, 10),
        "sentence_first_word": tokens[sentence_start].text.casefold(),
        "sentence_second_word": tokens[min(sentence_start + 1, sentence_end)].text.casefold(),
        "sentence_last_word": tokens[sentence_end].text.casefold(),
    }
    for offset in (-2, -1, 1, 2):
        neighbour = index + offset
        if sentence_start <= neighbour <= sentence_end:
            features[f"word{offset}"] = tokens[neighbour].text.casefold()
            features[f"shape{offset}"] = char_shape(tokens[neighbour].text)
        else:
            features[f"word{offset}"] = "<BOUNDARY>"
    for offset in (-3, 3):
        neighbour = index + offset
        features[f"word{offset}"] = tokens[neighbour].text.casefold() if sentence_start <= neighbour <= sentence_end else "<BOUNDARY>"
    return features


def char_span_to_token_range(text: str, tokens: list[Token], start: int, end: int) -> tuple[int, int]:
    if start < 0 or end <= start or end > len(text) or text[start:end] == "":
        raise ValueError("invalid character span")
    selected = [i for i, token in enumerate(tokens) if token.start >= start and token.end <= end]
    if not selected or tokens[selected[0]].start != start or tokens[selected[-1]].end != end:
        raise ValueError("entity boundaries must align exactly to token boundaries")
    if any(text[tokens[i].end:tokens[i+1].start].strip() for i in range(selected[0], selected[-1])):
        raise ValueError("entity span contains un-tokenized non-whitespace gaps")
    if any(tokens[i].sentence_id != tokens[selected[0]].sentence_id for i in selected):
        raise ValueError("entity spans cannot cross sentence boundaries")
    return selected[0], selected[-1]
