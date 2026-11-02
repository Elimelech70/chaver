"""OpenAI-compatible backend (analyst implementation M4), against a local fake endpoint.

No real key, no network beyond 127.0.0.1. Checks request shape, system context,
max_tokens, error handling, and that the default backend is unchanged.
"""
from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from chaver.archetype.loader import load_archetype
from chaver.language import faculty as fac

ROOT = Path(__file__).resolve().parent.parent


class _Fake(BaseHTTPRequestHandler):
    requests: list[dict] = []
    mode = "ok"

    def do_POST(self):  # noqa: N802
        body = self.rfile.read(int(self.headers["Content-Length"]))
        _Fake.requests.append({"path": self.path, "auth": self.headers.get("Authorization"),
                               "json": json.loads(body)})
        if _Fake.mode == "ok":
            code, out = 200, {"choices": [{"message": {"role": "assistant", "content": "  shalom  "}}]}
        elif _Fake.mode == "500":
            code, out = 500, {"error": "boom"}
        else:  # bad shape
            code, out = 200, {"nothing": True}
        data = json.dumps(out).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def endpoint(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _Fake.requests, _Fake.mode = [], "ok"
    monkeypatch.setenv("CHAVER_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1/")
    monkeypatch.setenv("CHAVER_API_KEY", "test-key")
    yield _Fake
    server.shutdown()


def _faculty(model="fake-model"):
    arch = load_archetype(ROOT / "CHAVER.md")
    return fac.LanguageFaculty(archetype=arch, backend_name="openai_compat", model=model)


def test_request_shape(endpoint):
    lf = _faculty()
    assert lf.backend_label == "openai_compat/fake-model"
    out = asyncio.run(lf.generate(fac.LanguageRequest(prompt="hi", max_tokens=77)))
    assert out == "shalom"
    r = endpoint.requests[-1]
    assert r["path"] == "/v1/chat/completions"
    assert r["auth"] == "Bearer test-key"
    j = r["json"]
    assert j["model"] == "fake-model" and j["max_tokens"] == 77
    assert [m["role"] for m in j["messages"]] == ["system", "user"]
    assert j["messages"][0]["content"].encode() == (ROOT / "CHAVER.md").read_bytes()
    assert j["messages"][1]["content"] == "hi"


def test_http_error(endpoint):
    endpoint.mode = "500"
    with pytest.raises(RuntimeError, match="HTTP 500"):
        asyncio.run(_faculty().generate(fac.LanguageRequest(prompt="x")))


def test_bad_shape(endpoint):
    endpoint.mode = "bad"
    with pytest.raises(RuntimeError, match="unexpected response shape"):
        asyncio.run(_faculty().generate(fac.LanguageRequest(prompt="x")))


def test_connection_refused(monkeypatch):
    monkeypatch.setenv("CHAVER_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("CHAVER_API_KEY", "secret-xyz")
    with pytest.raises(RuntimeError, match="request failed") as e:
        asyncio.run(_faculty().generate(fac.LanguageRequest(prompt="x")))
    assert "secret-xyz" not in str(e.value)  # the key is never in an error


@pytest.mark.parametrize("unset", ["CHAVER_BASE_URL", "CHAVER_API_KEY"])
def test_missing_config(monkeypatch, endpoint, unset):
    monkeypatch.delenv(unset)
    with pytest.raises(RuntimeError, match=unset):
        _faculty()


def test_missing_model(endpoint):
    with pytest.raises(RuntimeError, match="CHAVER_MODEL"):
        _faculty(model="")


def test_default_backend_unchanged(monkeypatch):
    import importlib
    monkeypatch.delenv("CHAVER_BACKEND", raising=False)
    monkeypatch.delenv("CHAVER_MODEL", raising=False)
    reloaded = importlib.reload(fac)
    try:
        assert reloaded.CHAVER_BACKEND == "anthropic"
        assert reloaded.CHAVER_MODEL == "claude-sonnet-5"
        assert set(reloaded.BACKENDS) == {"anthropic", "ollama", "openai_compat"}
    finally:
        importlib.reload(fac)
