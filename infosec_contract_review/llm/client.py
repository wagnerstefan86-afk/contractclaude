"""Provider-agnostic LLM client. Initial implementation: OpenAI."""
from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ):
        self.provider = provider or os.getenv("LLM_PROVIDER", "openai")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")

    def call(
        self,
        developer_prompt: str,
        user_prompt: str,
        json_schema: dict,
        timeout: int = 60,
    ) -> dict:
        if self.provider == "openai":
            return self._call_openai(developer_prompt, user_prompt, json_schema, timeout)
        raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _call_openai(
        self,
        developer_prompt: str,
        user_prompt: str,
        json_schema: dict,
        timeout: int,
    ) -> dict:
        if not self._api_key:
            raise ValueError(
                "OPENAI_API_KEY not set. Set the environment variable or pass api_key to LLMClient."
            )

        import openai

        client = openai.OpenAI(api_key=self._api_key, timeout=timeout)

        last_err = None
        for attempt in range(3):
            try:
                start = time.time()
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "developer", "content": developer_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": json_schema,
                    },
                    temperature=0.1,
                )
                duration = time.time() - start

                usage = response.usage
                result_text = response.choices[0].message.content

                import json
                parsed = json.loads(result_text)

                token_info = {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                    "duration_seconds": round(duration, 2),
                }
                logger.info(
                    "LLM call: %d prompt + %d completion tokens in %.1fs",
                    token_info["prompt_tokens"],
                    token_info["completion_tokens"],
                    duration,
                )

                return {"data": parsed, "token_usage": token_info}

            except (openai.RateLimitError, openai.APITimeoutError) as e:
                last_err = e
                wait = 2 ** (attempt + 1)
                logger.warning("LLM call attempt %d failed (%s), retrying in %ds", attempt + 1, e, wait)
                time.sleep(wait)
            except openai.APIError as e:
                last_err = e
                logger.error("LLM API error: %s", e)
                break
            except Exception as e:
                last_err = e
                logger.error("Unexpected LLM error: %s", e)
                break

        raise RuntimeError(f"LLM call failed after retries: {last_err}")
