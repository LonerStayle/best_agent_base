"""LLMClient 어댑터 자동 model 주입 — Gemini / Anthropic (FR-5, D3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from best_agent_base.prompts.render import RenderContext


@pytest.mark.asyncio
async def test_gemini_auto_injects_model_when_none(monkeypatch):
    """GeminiClient.generate(ctx with model=None) → 어댑터가 self._profile.model.value 자동 주입."""
    from best_agent_base.llm import gemini as gemini_mod

    fake_sdk = MagicMock()
    fake_result = MagicMock()
    fake_result.text = "ok"
    fake_result.usage_metadata = MagicMock(
        prompt_token_count=1, candidates_token_count=1, cached_content_token_count=0
    )
    fake_sdk.aio.models.generate_content = AsyncMock(return_value=fake_result)
    fake_sdk.aio.caches.create = AsyncMock(side_effect=Exception("no cache for this test"))

    monkeypatch.setattr(gemini_mod, "_build_genai_client", lambda: fake_sdk)
    client = gemini_mod.GeminiClient()
    expected_model = client._profile.model.value

    captured_ctx: list[RenderContext] = []
    orig_split = gemini_mod.split_at_boundary

    def spy_split(ctx):
        captured_ctx.append(ctx)
        return orig_split(ctx)

    monkeypatch.setattr(gemini_mod, "split_at_boundary", spy_split)
    await client.generate(RenderContext())  # ctx.model=None
    assert captured_ctx[0].model == expected_model


@pytest.mark.asyncio
async def test_gemini_respects_explicit_model(monkeypatch):
    """ctx.model 명시 시 어댑터 자동 주입 우회 (도메인 우선, D3)."""
    from best_agent_base.llm import gemini as gemini_mod

    fake_sdk = MagicMock()
    fake_result = MagicMock()
    fake_result.text = "ok"
    fake_result.usage_metadata = MagicMock(
        prompt_token_count=1, candidates_token_count=1, cached_content_token_count=0
    )
    fake_sdk.aio.models.generate_content = AsyncMock(return_value=fake_result)
    fake_sdk.aio.caches.create = AsyncMock(side_effect=Exception("no cache"))

    monkeypatch.setattr(gemini_mod, "_build_genai_client", lambda: fake_sdk)
    client = gemini_mod.GeminiClient()

    captured_ctx: list[RenderContext] = []
    orig_split = gemini_mod.split_at_boundary

    def spy_split(ctx):
        captured_ctx.append(ctx)
        return orig_split(ctx)

    monkeypatch.setattr(gemini_mod, "split_at_boundary", spy_split)
    await client.generate(RenderContext(model="my-custom-model"))
    assert captured_ctx[0].model == "my-custom-model"
