"""Tests for _parse_json edge cases."""
import json

import pytest

from app.services.llm import _parse_json


class TestParseJson:

    def test_raw_json_object(self):
        assert _parse_json('{"a": 1}') == {"a": 1}

    def test_raw_json_array(self):
        assert _parse_json('[1, 2]') == [1, 2]

    def test_markdown_code_block(self):
        text = '```json\n{"a": 1}\n```'
        assert _parse_json(text) == {"a": 1}

    def test_markdown_json_tag(self):
        text = '```JSON\n{"key": "value"}\n```'
        assert _parse_json(text) == {"key": "value"}

    def test_json_surrounded_by_prose(self):
        text = 'Here is the result: {"a": 1} hope that helps'
        assert _parse_json(text) == {"a": 1}

    def test_nested_json(self):
        text = '{"a": {"b": 1}}'
        assert _parse_json(text) == {"a": {"b": 1}}

    def test_json_with_leading_text(self):
        text = 'Sure! {"action": "ask", "message": "hi"}'
        result = _parse_json(text)
        assert result["action"] == "ask"

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_json("not json at all")

    def test_empty_string_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_json("")

    def test_array_before_object(self):
        text = '[1, 2] then {"a": 1}'
        assert _parse_json(text) == [1, 2]

    def test_multiple_code_blocks(self):
        """When first code block has valid JSON, it's returned."""
        text = '```json\n{"first": true}\n```\n\n```json\n{"second": true}\n```'
        result = _parse_json(text)
        assert result == {"first": True}
