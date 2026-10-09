from __future__ import annotations

import json
from urllib.error import URLError

import pytest

from story_video_automation import story_generation
from story_video_automation.options import Options


def test_local_ollama_is_the_default_story_provider(monkeypatch) -> None:
    monkeypatch.delenv("TEXT_PROVIDER", raising=False)

    options = Options.from_env()

    assert options.text_provider == "ollama"
    assert options.ollama_model == "qwen3:4b"


def test_ollama_generation_requests_json_from_local_model(monkeypatch) -> None:
    observed: dict[str, object] = {}
    expected = {"title": "Village story"}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps({"response": json.dumps(expected)}).encode("utf-8")

    def fake_urlopen(request, timeout: int):
        observed["url"] = request.full_url
        observed["body"] = json.loads(request.data.decode("utf-8"))
        observed["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(story_generation, "urlopen", fake_urlopen)

    result = story_generation._generate_with_ollama(
        "Write a story", "qwen3:4b", "http://localhost:11434"
    )

    assert json.loads(result) == expected
    assert observed["url"] == "http://localhost:11434/api/generate"
    assert observed["body"]["model"] == "qwen3:4b"
    assert observed["body"]["format"] == "json"
    assert observed["body"]["think"] is False
    assert observed["timeout"] == 300


def test_ollama_connection_error_explains_how_to_install_model(monkeypatch) -> None:
    def fail_urlopen(*_args, **_kwargs):
        raise URLError("connection refused")

    monkeypatch.setattr(story_generation, "urlopen", fail_urlopen)

    with pytest.raises(RuntimeError, match="ollama pull qwen3:4b"):
        story_generation._generate_with_ollama(
            "Write a story", "qwen3:4b", "http://localhost:11434"
        )
