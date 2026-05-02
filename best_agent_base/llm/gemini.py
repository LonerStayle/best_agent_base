import os

from langchain_google_genai import ChatGoogleGenerativeAI

DEFAULT_MODEL = "gemini-3-flash"


def get_gemini(
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    max_output_tokens: int = 4096,
    **kwargs,
) -> ChatGoogleGenerativeAI:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY 또는 GEMINI_API_KEY 환경 변수가 설정되어 있지 않습니다."
        )

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        google_api_key=api_key,
        **kwargs,
    )
