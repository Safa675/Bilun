"""Small lexical reader for the audit's supported TSX source forms.

Strings, templates and comments are opaque: their contents cannot prove JSX
usage. This is deliberately not a TypeScript parser or runtime interpreter.
"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Token:
    value: str
    kind: str = "symbol"


def fail(detail: str) -> ValueError:
    return ValueError(f"patient UI source: {detail}")


def _quoted_end(source: str, start: int) -> int:
    quote = source[start]
    index = start + 1
    while index < len(source):
        if source[index] == "\\":
            index += 2
        elif source[index] == quote:
            return index + 1
        elif quote == "`" and source.startswith("${", index):
            index = _interpolation_end(source, index + 2)
        else:
            index += 1
    raise fail("unterminated string or template")


def _interpolation_end(source: str, index: int) -> int:
    depth = 1
    while index < len(source):
        if source[index] in "\"'`":
            index = _quoted_end(source, index)
            continue
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if not depth:
                return index + 1
        index += 1
    raise fail("unterminated template interpolation")


_WORD = re.compile(r"[A-Za-z_$][\w$]*")


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
        elif source.startswith("//", index):
            end = source.find("\n", index + 2)
            index = len(source) if end < 0 else end + 1
        elif source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                raise fail("unterminated comment")
            index = end + 2
        elif char in "\"'`":
            end = _quoted_end(source, index)
            value = source[index + 1 : end - 1]
            # Audited names/IDs are literal ASCII. Do not guess escaped values.
            kind = "template" if char == "`" else "string"
            if "\\" in value:
                kind = "escaped_string"
            tokens.append(Token(value, kind))
            index = end
        elif match := _WORD.match(source, index):
            tokens.append(Token(match.group(), "word"))
            index = match.end()
        elif source.startswith("=>", index):
            tokens.append(Token("=>"))
            index += 2
        else:
            tokens.append(Token(char))
            index += 1
    return tokens


def group_end(tokens: list[Token], start: int) -> int:
    """Return the index after a balanced (), [] or {} group."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = [pairs[tokens[start].value]]
    for index in range(start + 1, len(tokens)):
        token = tokens[index]
        if token.kind != "symbol":
            continue
        if token.value in pairs:
            stack.append(pairs[token.value])
        elif token.value in pairs.values():
            if token.value != stack.pop():
                raise fail("unbalanced delimiters in supported source")
            if not stack:
                return index + 1
    raise fail("unterminated delimiter group")


def expression_end(tokens: list[Token], start: int) -> int:
    index = start
    while index < len(tokens):
        if tokens[index].value in {";", "}"}:
            break
        if tokens[index].value in {"(", "[", "{"} and tokens[index].kind == "symbol":
            index = group_end(tokens, index)
        else:
            index += 1
    return index
