"""Provider-agnostic LLM client.

Signature is stable: ``LLMClient().call(developer_prompt, user_prompt,
json_schema, timeout)`` returns ``{"data": <parsed dict>,
"token_usage": {...}}``. The call sites in the extraction pipeline
(obligation_extractor, relation_detector, cross_theme_checker) don't
change.

Provider selection priority:
1. Explicit constructor args (tests).
2. ``ai_settings`` singleton row in the DB (Phase 4 settings UI).
3. Legacy env vars ``LLM_PROVIDER`` / ``LLM_MODEL`` / ``OPENAI_API_KEY``
   so existing deployments keep working even before the first DB
   migration run.

Exactly one active provider per instance. Supported providers:
``openai``, ``local`` (OpenAI-compatible custom base_url — vLLM /
Ollama OpenAI layer / LM Studio), ``gemini``, ``anthropic``.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings loader
# ---------------------------------------------------------------------------


def _load_active_settings() -> dict[str, Any] | None:
    """Load the ai_settings singleton as a dict. Returns None on any
    failure (missing migration, no DB, etc.) so the env-var path below
    still works."""
    try:
        from infosec_contract_review.core.database import SessionLocal
        from infosec_contract_review.models.ai_settings import AiSettings
    except Exception:
        return None
    try:
        db = SessionLocal()
        try:
            row = db.get(AiSettings, 1)
            if row is None:
                return None
            return {
                "active_provider": row.active_provider or "openai",
                "local_base_url": row.local_base_url,
                "local_model": row.local_model,
                "local_api_key": row.local_api_key,
                "openai_api_key": row.openai_api_key,
                "openai_model": row.openai_model,
                "openai_base_url": row.openai_base_url,
                "gemini_api_key": row.gemini_api_key,
                "gemini_model": row.gemini_model,
                "anthropic_api_key": row.anthropic_api_key,
                "anthropic_model": row.anthropic_model,
            }
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("ai_settings load failed: %s; falling back to env", exc)
        return None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LLMClient:
    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        settings = _load_active_settings()

        if provider:
            self.provider = provider
        elif settings:
            self.provider = settings["active_provider"]
        else:
            self.provider = os.getenv("LLM_PROVIDER", "openai")

        # Per-provider model + credentials. Constructor args trump the
        # singleton; singleton trumps env.
        self.model, self._api_key, self.base_url = self._resolve_provider_config(
            provider_name=self.provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            settings=settings,
        )

    # ------------------------------------------------------------------
    # Config resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_provider_config(
        *,
        provider_name: str,
        model: str | None,
        api_key: str | None,
        base_url: str | None,
        settings: dict[str, Any] | None,
    ) -> tuple[str, str, str | None]:
        def _from_settings(*keys: str) -> str | None:
            if not settings:
                return None
            for k in keys:
                v = settings.get(k)
                if v:
                    return v
            return None

        if provider_name == "openai":
            m = model or _from_settings("openai_model") or os.getenv("LLM_MODEL", "gpt-4o")
            k = api_key or _from_settings("openai_api_key") or os.getenv("OPENAI_API_KEY", "") or None
            b = base_url or _from_settings("openai_base_url") or os.getenv("OPENAI_BASE_URL") or None
            return m, (k or ""), b
        if provider_name == "local":
            m = model or _from_settings("local_model") or os.getenv("LOCAL_LLM_MODEL", "")
            k = api_key or _from_settings("local_api_key") or os.getenv("LOCAL_LLM_API_KEY", "") or None
            b = base_url or _from_settings("local_base_url") or os.getenv("LOCAL_LLM_BASE_URL") or None
            return (m or ""), (k or ""), b
        if provider_name == "gemini":
            m = model or _from_settings("gemini_model") or os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
            k = api_key or _from_settings("gemini_api_key") or os.getenv("GEMINI_API_KEY", "") or None
            return m, (k or ""), None
        if provider_name == "anthropic":
            m = model or _from_settings("anthropic_model") or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
            k = api_key or _from_settings("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY", "") or None
            return m, (k or ""), None
        # Unknown provider — keep object constructible but dispatch will raise.
        return (model or ""), (api_key or ""), base_url

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def call(
        self,
        developer_prompt: str,
        user_prompt: str,
        json_schema: dict,
        timeout: int = 60,
    ) -> dict:
        if self.provider in ("openai", "local"):
            return self._call_openai_compatible(
                developer_prompt, user_prompt, json_schema, timeout
            )
        if self.provider == "anthropic":
            return self._call_anthropic(
                developer_prompt, user_prompt, json_schema, timeout
            )
        if self.provider == "gemini":
            return self._call_gemini(
                developer_prompt, user_prompt, json_schema, timeout
            )
        raise ValueError(f"Unsupported LLM provider: {self.provider}")

    # ------------------------------------------------------------------
    # OpenAI + OpenAI-compatible local servers
    # ------------------------------------------------------------------

    def _call_openai_compatible(
        self,
        developer_prompt: str,
        user_prompt: str,
        json_schema: dict,
        timeout: int,
    ) -> dict:
        import openai

        if self.provider == "openai" and not self._api_key:
            raise ValueError(
                "OpenAI API key not set. Configure it under /ui/settings/ai "
                "or via the OPENAI_API_KEY env var."
            )
        if self.provider == "local" and not self.base_url:
            raise ValueError(
                "Local LLM base URL not set. Configure it under /ui/settings/ai."
            )
        if self.provider == "local" and not self.model:
            raise ValueError(
                "Local LLM model name not set. Configure it under /ui/settings/ai."
            )

        kwargs: dict[str, Any] = {"timeout": timeout}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        # openai SDK requires a non-empty api_key even for local servers.
        kwargs["api_key"] = self._api_key or "local-no-auth"
        client = openai.OpenAI(**kwargs)

        last_err: Exception | None = None
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
                parsed = json.loads(result_text)
                token_info = {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                    "duration_seconds": round(duration, 2),
                }
                logger.info(
                    "LLM call [%s/%s]: %d + %d tokens in %.1fs",
                    self.provider, self.model,
                    token_info["prompt_tokens"], token_info["completion_tokens"],
                    duration,
                )
                return {"data": parsed, "token_usage": token_info}
            except (openai.RateLimitError, openai.APITimeoutError) as e:
                last_err = e
                wait = 2 ** (attempt + 1)
                logger.warning("LLM attempt %d failed (%s), retrying in %ds", attempt + 1, e, wait)
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

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------

    def _call_anthropic(
        self,
        developer_prompt: str,
        user_prompt: str,
        json_schema: dict,
        timeout: int,
    ) -> dict:
        try:
            import anthropic  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "anthropic SDK not installed. pip install anthropic"
            ) from e
        if not self._api_key:
            raise ValueError(
                "Anthropic API key not set. Configure it under /ui/settings/ai."
            )

        # Anthropic doesn't speak OpenAI-style json_schema. We ship the
        # schema as a tool and force its invocation; the tool arguments
        # come back as structured JSON.
        schema_obj = json_schema.get("schema", json_schema) if isinstance(json_schema, dict) else json_schema
        tool_name = json_schema.get("name", "structured_output") if isinstance(json_schema, dict) else "structured_output"
        tool = {
            "name": tool_name,
            "description": "Return the structured output in this schema.",
            "input_schema": schema_obj,
        }

        client = anthropic.Anthropic(api_key=self._api_key, timeout=timeout)

        last_err: Exception | None = None
        for attempt in range(3):
            try:
                start = time.time()
                resp = client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=developer_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    tools=[tool],
                    tool_choice={"type": "tool", "name": tool_name},
                    temperature=0.1,
                )
                duration = time.time() - start
                parsed: dict[str, Any] | None = None
                for block in resp.content or []:
                    if getattr(block, "type", None) == "tool_use":
                        parsed = getattr(block, "input", None)
                        break
                if parsed is None:
                    raise RuntimeError("Anthropic returned no tool_use block")
                usage = getattr(resp, "usage", None)
                token_info = {
                    "prompt_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
                    "completion_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
                    "total_tokens": (
                        getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)
                    ) if usage else 0,
                    "duration_seconds": round(duration, 2),
                }
                logger.info(
                    "LLM call [%s/%s]: %d + %d tokens in %.1fs",
                    self.provider, self.model,
                    token_info["prompt_tokens"], token_info["completion_tokens"],
                    duration,
                )
                return {"data": parsed, "token_usage": token_info}
            except Exception as e:
                last_err = e
                logger.error("Anthropic error: %s", e)
                break
        raise RuntimeError(f"LLM call failed: {last_err}")

    # ------------------------------------------------------------------
    # Gemini (google-genai)
    # ------------------------------------------------------------------

    def _call_gemini(
        self,
        developer_prompt: str,
        user_prompt: str,
        json_schema: dict,
        timeout: int,
    ) -> dict:
        try:
            from google import genai  # type: ignore
            from google.genai import types as genai_types  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "google-genai SDK not installed. pip install google-genai"
            ) from e
        if not self._api_key:
            raise ValueError(
                "Gemini API key not set. Configure it under /ui/settings/ai."
            )

        schema_obj = json_schema.get("schema", json_schema) if isinstance(json_schema, dict) else json_schema

        client = genai.Client(api_key=self._api_key)

        try:
            start = time.time()
            resp = client.models.generate_content(
                model=self.model,
                contents=[
                    {"role": "user", "parts": [{"text": user_prompt}]},
                ],
                config=genai_types.GenerateContentConfig(
                    system_instruction=developer_prompt,
                    response_mime_type="application/json",
                    response_schema=schema_obj,
                    temperature=0.1,
                ),
            )
            duration = time.time() - start
            result_text = resp.text
            parsed = json.loads(result_text)
            usage = getattr(resp, "usage_metadata", None)
            token_info = {
                "prompt_tokens": getattr(usage, "prompt_token_count", 0) if usage else 0,
                "completion_tokens": getattr(usage, "candidates_token_count", 0) if usage else 0,
                "total_tokens": getattr(usage, "total_token_count", 0) if usage else 0,
                "duration_seconds": round(duration, 2),
            }
            logger.info(
                "LLM call [%s/%s]: %d + %d tokens in %.1fs",
                self.provider, self.model,
                token_info["prompt_tokens"], token_info["completion_tokens"],
                duration,
            )
            return {"data": parsed, "token_usage": token_info}
        except Exception as e:
            logger.error("Gemini error: %s", e)
            raise RuntimeError(f"LLM call failed: {e}") from e

    # ------------------------------------------------------------------
    # Simple ping — used by the /ui/settings/ai/test route
    # ------------------------------------------------------------------

    def ping(self) -> dict:
        """Lightweight connectivity check. Returns
        ``{"ok": True|False, "detail": str, "provider": ..., "model": ...}``.
        """
        try:
            if self.provider in ("openai", "local"):
                import openai

                kwargs: dict[str, Any] = {"timeout": 15}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                kwargs["api_key"] = self._api_key or "local-no-auth"
                client = openai.OpenAI(**kwargs)
                # A minimal 1-token completion is the most portable ping.
                resp = client.chat.completions.create(
                    model=self.model or "gpt-4o-mini",
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                    temperature=0,
                )
                return {
                    "ok": True,
                    "detail": "reply received",
                    "provider": self.provider,
                    "model": self.model,
                }
            if self.provider == "anthropic":
                import anthropic  # type: ignore
                client = anthropic.Anthropic(api_key=self._api_key, timeout=15)
                client.messages.create(
                    model=self.model,
                    max_tokens=1,
                    messages=[{"role": "user", "content": "ping"}],
                )
                return {
                    "ok": True,
                    "detail": "reply received",
                    "provider": self.provider,
                    "model": self.model,
                }
            if self.provider == "gemini":
                from google import genai  # type: ignore
                client = genai.Client(api_key=self._api_key)
                client.models.generate_content(
                    model=self.model,
                    contents="ping",
                )
                return {
                    "ok": True,
                    "detail": "reply received",
                    "provider": self.provider,
                    "model": self.model,
                }
            return {"ok": False, "detail": f"unsupported provider {self.provider!r}",
                    "provider": self.provider, "model": self.model}
        except Exception as e:  # pragma: no cover — exercised via UI
            return {
                "ok": False,
                "detail": str(e)[:200] or e.__class__.__name__,
                "provider": self.provider,
                "model": self.model,
            }
