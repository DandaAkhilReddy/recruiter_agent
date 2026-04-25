"""Unit tests for app.services.aoai._AOAIProxy / _ParamStrippingChatCompletions.

The proxy exists to make gpt-5.x reasoning models work transparently:
  - Strip params they reject as "unsupported" (temperature/seed/top_p/...)
  - Rename max_tokens -> max_completion_tokens (10x multiplier + reasoning_effort=minimal)
  - Pass everything else through untouched

This already broke once when gpt-4o was deprecated mid-build. Losing it again
would silently kill every persona/recruiter turn (empty content from the model).
"""
from __future__ import annotations

from typing import Any

import pytest
from app.services.aoai import _ParamStrippingChatCompletions


class _FakeInnerCompletions:
    """Drop-in for openai.AsyncAzureOpenAI().chat.completions.

    `side_effects` is a list of either Exception instances (raised) or any other
    value (returned). Calls are recorded in `calls` for assertion.
    """

    def __init__(self, side_effects: list[Any]) -> None:
        self._side_effects = list(side_effects)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(dict(kwargs))
        if not self._side_effects:
            raise AssertionError("FakeInnerCompletions ran out of side effects")
        nxt = self._side_effects.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _unsupported(param: str, model: str = "gpt-5.1") -> Exception:
    """Build the AOAI-style 400 error message that mentions a parameter by name."""
    return Exception(
        f"Error code: 400 - Unsupported value: '{param}' does not support "
        f"0.5 with this model ({model}). Only the default (1) value is supported."
    )


@pytest.mark.asyncio
async def test_strips_temperature_and_retries() -> None:
    inner = _FakeInnerCompletions([_unsupported("temperature"), "OK"])
    proxy = _ParamStrippingChatCompletions(inner)

    result = await proxy.create(model="gpt-5.1", temperature=0.5, messages=[{"role": "user", "content": "hi"}])

    assert result == "OK"
    assert len(inner.calls) == 2
    assert "temperature" in inner.calls[0]
    assert "temperature" not in inner.calls[1]
    assert inner.calls[1]["model"] == "gpt-5.1"


@pytest.mark.asyncio
@pytest.mark.parametrize("param", ["seed", "top_p", "frequency_penalty", "presence_penalty"])
async def test_strips_other_unsupported_params(param: str) -> None:
    inner = _FakeInnerCompletions([_unsupported(param), {"id": "ok"}])
    proxy = _ParamStrippingChatCompletions(inner)

    result = await proxy.create(model="gpt-5.1", messages=[], **{param: 0.5})

    assert result == {"id": "ok"}
    assert param in inner.calls[0]
    assert param not in inner.calls[1]


@pytest.mark.asyncio
async def test_renames_max_tokens_with_multiplier_and_reasoning_effort() -> None:
    inner = _FakeInnerCompletions([_unsupported("max_tokens"), "OK"])
    proxy = _ParamStrippingChatCompletions(inner)

    await proxy.create(model="gpt-5.1", max_tokens=300, messages=[{"role": "user", "content": "hi"}])

    second = inner.calls[1]
    assert "max_tokens" not in second
    # 300 * 10 = 3000, above the 2000 floor
    assert second["max_completion_tokens"] == 3000
    assert second.get("extra_body", {}).get("reasoning_effort") == "minimal"


@pytest.mark.asyncio
async def test_max_tokens_rename_enforces_2000_floor() -> None:
    """If 10x the original is still below 2000, clamp to 2000."""
    inner = _FakeInnerCompletions([_unsupported("max_tokens"), "OK"])
    proxy = _ParamStrippingChatCompletions(inner)

    await proxy.create(model="gpt-5.1", max_tokens=50, messages=[])

    assert inner.calls[1]["max_completion_tokens"] == 2000


@pytest.mark.asyncio
async def test_chains_strip_then_rename() -> None:
    """First call fails on temperature, second on max_tokens, third succeeds."""
    inner = _FakeInnerCompletions([
        _unsupported("temperature"),
        _unsupported("max_tokens"),
        "OK",
    ])
    proxy = _ParamStrippingChatCompletions(inner)

    await proxy.create(
        model="gpt-5.1",
        temperature=0.7,
        max_tokens=100,
        messages=[{"role": "user", "content": "hi"}],
    )

    assert len(inner.calls) == 3
    # By call 3, both have been mutated
    assert "temperature" not in inner.calls[2]
    assert "max_tokens" not in inner.calls[2]
    assert inner.calls[2]["max_completion_tokens"] == 2000  # 100*10 < 2000 floor
    assert inner.calls[2]["extra_body"]["reasoning_effort"] == "minimal"


@pytest.mark.asyncio
async def test_passes_through_when_error_is_not_unsupported() -> None:
    """Connection / auth / 5xx errors must propagate unchanged on first call."""
    err = RuntimeError("connection reset by peer")
    inner = _FakeInnerCompletions([err])
    proxy = _ParamStrippingChatCompletions(inner)

    with pytest.raises(RuntimeError, match="connection reset"):
        await proxy.create(model="gpt-5.1", temperature=0.5, messages=[])

    assert len(inner.calls) == 1  # no retry


@pytest.mark.asyncio
async def test_unsupported_for_unknown_param_propagates() -> None:
    """If the error names a param we don't know how to strip, re-raise."""
    inner = _FakeInnerCompletions([_unsupported("logit_bias")])
    proxy = _ParamStrippingChatCompletions(inner)

    with pytest.raises(Exception, match="Unsupported value: 'logit_bias'"):
        await proxy.create(model="gpt-5.1", logit_bias={"50256": -100}, messages=[])

    assert len(inner.calls) == 1


@pytest.mark.asyncio
async def test_messages_model_response_format_preserved_across_retries() -> None:
    """Strip retries must not corrupt unrelated kwargs."""
    msgs = [{"role": "system", "content": "be helpful"}, {"role": "user", "content": "hi"}]
    inner = _FakeInnerCompletions([_unsupported("temperature"), "OK"])
    proxy = _ParamStrippingChatCompletions(inner)

    await proxy.create(
        model="gpt-5.1",
        temperature=0.5,
        messages=msgs,
        response_format={"type": "json_object"},
    )

    final = inner.calls[1]
    assert final["model"] == "gpt-5.1"
    assert final["messages"] == msgs
    assert final["response_format"] == {"type": "json_object"}
    assert "temperature" not in final


@pytest.mark.asyncio
async def test_succeeds_on_first_call_when_no_error() -> None:
    """Happy path — no retry overhead when the model accepts everything."""
    inner = _FakeInnerCompletions(["FIRST"])
    proxy = _ParamStrippingChatCompletions(inner)

    result = await proxy.create(model="gpt-4o", temperature=0.7, messages=[])

    assert result == "FIRST"
    assert len(inner.calls) == 1
    assert inner.calls[0]["temperature"] == 0.7  # untouched
