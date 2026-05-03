"""best_agent_base 단순 호출 데모.

Phase 2 GeminiClient 사용. 도메인 프로젝트는 이 패턴을 참고.
"""

from __future__ import annotations

import asyncio

from dotenv import load_dotenv

from best_agent_base.llm.gemini import GeminiClient
from best_agent_base.prompts.render import RenderContext


async def _main() -> None:
    load_dotenv()
    client = GeminiClient()
    resp = await client.generate(RenderContext())
    print(resp.text)
    print(f"\n[cache_hit={resp.cache_hit} static_hash={resp.static_hash}]")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
