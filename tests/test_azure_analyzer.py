from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import yunshang.analyzers as analyzers
from yunshang.models import MeetingAnalysis, MindMapNode
from yunshang.session import load_jsonl

ROOT = Path(__file__).resolve().parents[1]


class FakeResponses:
    def __init__(self, analysis: MeetingAnalysis) -> None:
        self.analysis = analysis
        self.request: dict[str, Any] = {}

    def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        return SimpleNamespace(output_parsed=self.analysis)


class FakeOpenAI:
    analysis = MeetingAnalysis(
        title="Structured result",
        summary="Generated from the supplied event evidence.",
        mind_map=MindMapNode(label="Structured result"),
    )
    instances: list["FakeOpenAI"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.configuration = kwargs
        self.responses = FakeResponses(self.analysis)
        self.instances.append(self)


def test_uses_official_v1_entra_path_and_non_stored_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_provider = lambda: "token"  # noqa: E731
    captured_scope: list[str] = []
    FakeOpenAI.instances.clear()
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "meeting-model")
    monkeypatch.setattr(analyzers, "DefaultAzureCredential", object)
    monkeypatch.setattr(
        analyzers,
        "get_bearer_token_provider",
        lambda credential, scope: captured_scope.append(scope) or token_provider,
    )
    monkeypatch.setattr(analyzers, "OpenAI", FakeOpenAI)

    analyzer = analyzers.AzureOpenAIAnalyzer()
    result = analyzer.analyze(load_jsonl(ROOT / "examples" / "product-planning.jsonl"))

    client = FakeOpenAI.instances[0]
    assert client.configuration == {
        "base_url": "https://example.openai.azure.com/openai/v1/",
        "api_key": token_provider,
    }
    assert captured_scope == ["https://ai.azure.com/.default"]
    assert client.responses.request["model"] == "meeting-model"
    assert client.responses.request["text_format"] is MeetingAnalysis
    assert client.responses.request["store"] is False
    assert "untrusted data" in client.responses.request["input"][0]["content"]
    assert result == FakeOpenAI.analysis


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (
            "https://example.openai.azure.com/",
            "https://example.openai.azure.com/openai/v1/",
        ),
        (
            "https://example.openai.azure.com/openai/v1/",
            "https://example.openai.azure.com/openai/v1/",
        ),
    ],
)
def test_normalizes_azure_v1_base_url(endpoint: str, expected: str) -> None:
    assert analyzers._azure_v1_base_url(endpoint) == expected


def test_rejects_non_https_endpoint() -> None:
    with pytest.raises(ValueError, match="must use HTTPS"):
        analyzers._azure_v1_base_url("http://example.openai.azure.com")


def test_wraps_external_analysis_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingResponses:
        def parse(self, **kwargs: Any) -> None:
            raise ConnectionError("network unavailable")

    analyzer = object.__new__(analyzers.AzureOpenAIAnalyzer)
    analyzer._deployment = "meeting-model"
    analyzer._client = SimpleNamespace(responses=FailingResponses())

    with pytest.raises(RuntimeError, match="Azure OpenAI analysis failed"):
        analyzer.analyze(load_jsonl(ROOT / "examples" / "product-planning.jsonl"))