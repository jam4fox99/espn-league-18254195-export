from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mygm_worker.analytics.models import JsonObject, JsonValue

_ROOT_PATH = "$"
_EXPECTED_EOF = "end of file"
_EXPECTED_JSON_VALUE = "JSON value"
_EXPECTED_CLOSED_STRING = "closed string"
_EXPECTED_UNICODE_ESCAPE = "unicode escape"
_EXPECTED_VALID_ESCAPE = "valid escape"
_EXPECTED_NUMBER = "number"


class JsonShapeError(ValueError):
    def __init__(self, path: str, expected: str) -> None:
        super().__init__(f"{path} expected {expected}")


def read_json(path: Path) -> JsonValue:
    return _JsonParser(path.read_text(encoding="utf-8")).parse()


@dataclass(slots=True)
class _JsonParser:
    text: str
    index: int = 0

    def parse(self) -> JsonValue:
        value = self._value()
        self._spaces()
        if self.index != len(self.text):
            raise JsonShapeError(_ROOT_PATH, _EXPECTED_EOF)
        return value

    def _value(self) -> JsonValue:
        self._spaces()
        char = self._peek()
        if char in {'"', "[", "{"}:
            return self._structured_value(char)
        if char in {"f", "n", "t"}:
            return self._literal_value(char)
        return self._number()

    def _structured_value(self, char: str) -> JsonValue:
        if char == "{":
            return self._object()
        if char == "[":
            return self._array()
        return self._string()

    def _literal_value(self, char: str) -> JsonValue:
        if char == "t":
            self._literal("true")
            return True
        if char == "f":
            self._literal("false")
            return False
        self._literal("null")
        return None

    def _object(self) -> JsonObject:
        self._expect("{")
        result: JsonObject = {}
        self._spaces()
        if self._peek() == "}":
            self.index += 1
            return result
        while True:
            self._spaces()
            key = self._string()
            self._spaces()
            self._expect(":")
            result[key] = self._value()
            self._spaces()
            char = self._peek()
            if char == "}":
                self.index += 1
                return result
            self._expect(",")

    def _array(self) -> list[JsonValue]:
        self._expect("[")
        result: list[JsonValue] = []
        self._spaces()
        if self._peek() == "]":
            self.index += 1
            return result
        while True:
            result.append(self._value())
            self._spaces()
            char = self._peek()
            if char == "]":
                self.index += 1
                return result
            self._expect(",")

    def _string(self) -> str:
        self._expect('"')
        chars: list[str] = []
        while self.index < len(self.text):
            char = self.text[self.index]
            self.index += 1
            if char == '"':
                return "".join(chars)
            if char == "\\":
                chars.append(self._escape())
            else:
                chars.append(char)
        raise JsonShapeError(_ROOT_PATH, _EXPECTED_CLOSED_STRING)

    def _escape(self) -> str:
        char = self._take()
        escapes = {
            '"': '"',
            "\\": "\\",
            "/": "/",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
        }
        if char == "u":
            digits = self.text[self.index : self.index + 4]
            if len(digits) != 4:
                raise JsonShapeError(_ROOT_PATH, _EXPECTED_UNICODE_ESCAPE)
            self.index += 4
            return chr(int(digits, 16))
        if char in escapes:
            return escapes[char]
        raise JsonShapeError(_ROOT_PATH, _EXPECTED_VALID_ESCAPE)

    def _number(self) -> int | float:
        start = self.index
        if self._peek() == "-":
            self.index += 1
        while self._peek(default="").isdigit():
            self.index += 1
        if self._peek(default="") == ".":
            self.index += 1
            while self._peek(default="").isdigit():
                self.index += 1
        if self._peek(default="").lower() == "e":
            self.index += 1
            if self._peek(default="") in {"+", "-"}:
                self.index += 1
            while self._peek(default="").isdigit():
                self.index += 1
        number = self.text[start : self.index]
        if not number or number in {"-", "."}:
            raise JsonShapeError(_ROOT_PATH, _EXPECTED_NUMBER)
        if "." in number or "e" in number.lower():
            return float(number)
        return int(number)

    def _literal(self, literal: str) -> None:
        end = self.index + len(literal)
        if self.text[self.index : end] != literal:
            raise JsonShapeError(_ROOT_PATH, literal)
        self.index = end

    def _spaces(self) -> None:
        while self.index < len(self.text) and self.text[self.index] in " \n\r\t":
            self.index += 1

    def _expect(self, char: str) -> None:
        actual = self._take()
        if actual != char:
            raise JsonShapeError(_ROOT_PATH, char)

    def _take(self) -> str:
        char = self._peek()
        self.index += 1
        return char

    def _peek(self, *, default: str | None = None) -> str:
        if self.index < len(self.text):
            return self.text[self.index]
        if default is not None:
            return default
        raise JsonShapeError(_ROOT_PATH, _EXPECTED_JSON_VALUE)


def as_object(value: JsonValue, path: str) -> JsonObject:
    if isinstance(value, dict):
        return value
    raise JsonShapeError(path, "object")


def as_array(value: JsonValue, path: str) -> list[JsonValue]:
    if isinstance(value, list):
        return value
    raise JsonShapeError(path, "array")


def objects(value: JsonValue, path: str) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for index, item in enumerate(as_array(value, path)):
        rows.append(as_object(item, f"{path}[{index}]"))
    return rows


def object_field(source: JsonObject, key: str) -> JsonObject:
    return as_object(source.get(key), key)


def array_field(source: JsonObject, key: str) -> list[JsonObject]:
    return objects(source.get(key), key)


def string_value(value: JsonValue, default: str = "") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int | float):
        return str(value)
    return default


def int_value(value: JsonValue, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def float_value(value: JsonValue, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def sorted_counts(counts: dict[str, int]) -> dict[str, int]:
    return {key: counts[key] for key in sorted(counts)}
