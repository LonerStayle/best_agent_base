"""Phase 0~3 데모 — call_with_attachments helper + GeminiClient (Phase 2 어댑터)."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from dotenv import load_dotenv

from best_agent_base.attachments.builtins import date_change   # auto-register  # noqa: F401
from best_agent_base.attachments.builtins import todo_reminder  # auto-register  # noqa: F401
from best_agent_base.attachments.integrate import call_with_attachments
from best_agent_base.llm.gemini import GeminiClient
from best_agent_base.prompts.render import RenderContext


async def main() -> None:
    load_dotenv()
    client = GeminiClient()

    # 베이스라인 — 어태치먼트 0개 (last_emit_date None, messages 빈 튜플)
    ctx = RenderContext()
    response = await call_with_attachments(client, ctx, user_input="hello")
    print(f"[basic] {response.text}")

    # date_change 어태치먼트 활성 — yesterday 박아서 자정 감지 트리거
    yesterday = date.today() - timedelta(days=1)
    ctx_with_yesterday = RenderContext(last_emit_date=yesterday)
    response = await call_with_attachments(client, ctx_with_yesterday, user_input="hello again")
    print(f"[date_change emitted] {response.text}")


if __name__ == "__main__":
    asyncio.run(main())
