from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

# Attempt loading environment variables from .env files safely
try:
    from dotenv import load_dotenv
    load_dotenv()
    _root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
    if os.path.exists(_root_env):
        load_dotenv(_root_env)
    _backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if os.path.exists(_backend_env):
        load_dotenv(_backend_env)
except ImportError:
    pass

from backend.app.interface.nl_extractor import (
    ExtractedPlanningContext,
    ExtractedTaskSpec,
    NaturalLanguageExtractor,
)

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Abstract contract for natural-language planning extraction providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider implementation."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if required environment keys or endpoints are configured."""

    @abstractmethod
    def extract_planning_context(
        self, prompt: str, reference_time: Optional[datetime] = None
    ) -> Optional[ExtractedPlanningContext]:
        """Extract structured planning context, or None if unavailable/unsupported."""


class ConfiguredLLMProvider(BaseLLMProvider):
    """
    Configurable external LLM provider integration.
    Supports OpenAI, Gemini, Anthropic, Groq, Ollama, and generic OpenAI-compatible HTTP endpoints.
    Validates all structured output against existing schemas and rejects untrusted attributes.
    Enforces privacy by masking API keys in logs and never logging full prompts.
    """

    def __init__(
        self,
        *,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        raw_provider = (provider if provider is not None else os.getenv("HELIOX_LLM_PROVIDER", "")).strip().lower()
        raw_key = (api_key if api_key is not None else os.getenv("HELIOX_LLM_API_KEY", "")).strip()
        raw_endpoint = (endpoint if endpoint is not None else os.getenv("HELIOX_LLM_ENDPOINT", "")).strip()
        raw_model = (model if model is not None else os.getenv("HELIOX_LLM_MODEL", "")).strip()

        # Check standard environment variables for OpenAI only if explicit key/provider is not empty
        openai_key = os.getenv("OPENAI_API_KEY", "").strip() if api_key is None else ""
        openai_model = os.getenv("OPENAI_MODEL", "").strip()
        openai_base = os.getenv("OPENAI_BASE_URL", os.getenv("OPENAI_API_BASE", "")).strip()
        openai_timeout = os.getenv("OPENAI_TIMEOUT", "").strip()

        # Auto-detect provider and key from standard environment variables if not explicitly provided
        if not raw_provider and provider is None:
            if openai_key and api_key is None:
                raw_provider = "openai"
                raw_key = raw_key or openai_key
            elif os.getenv("GEMINI_API_KEY") and api_key is None:
                raw_provider = "gemini"
                raw_key = raw_key or os.getenv("GEMINI_API_KEY", "").strip()
            elif os.getenv("ANTHROPIC_API_KEY") and api_key is None:
                raw_provider = "anthropic"
                raw_key = raw_key or os.getenv("ANTHROPIC_API_KEY", "").strip()
            elif os.getenv("GROQ_API_KEY") and api_key is None:
                raw_provider = "groq"
                raw_key = raw_key or os.getenv("GROQ_API_KEY", "").strip()
            elif os.getenv("OLLAMA_HOST") and provider is None:
                raw_provider = "ollama"

        if raw_provider == "openai":
            if not raw_key and openai_key and api_key is None:
                raw_key = openai_key
            if not raw_model:
                raw_model = openai_model or "gpt-4o-mini"
            if not raw_endpoint:
                raw_endpoint = f"{openai_base.rstrip('/')}/chat/completions" if openai_base else "https://api.openai.com/v1/chat/completions"
        elif not raw_model:
            if raw_provider == "gemini":
                raw_model = "gemini-1.5-flash"
            elif raw_provider == "anthropic":
                raw_model = "claude-3-5-sonnet-20241022"
            elif raw_provider == "groq":
                raw_model = "llama-3.1-70b-versatile"
            elif raw_provider == "ollama":
                raw_model = "llama3"
            else:
                raw_model = "gpt-4o-mini"

        if not raw_endpoint:
            if raw_provider == "openai":
                raw_endpoint = "https://api.openai.com/v1/chat/completions"
            elif raw_provider == "gemini":
                raw_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{raw_model}:generateContent"
            elif raw_provider == "anthropic":
                raw_endpoint = "https://api.anthropic.com/v1/messages"
            elif raw_provider == "groq":
                raw_endpoint = "https://api.groq.com/openai/v1/chat/completions"
            elif raw_provider == "ollama":
                host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
                raw_endpoint = f"{host}/v1/chat/completions"

        default_timeout = 10.0 if raw_provider == "openai" else 5.0
        if timeout_seconds is not None:
            effective_timeout = float(timeout_seconds)
        elif raw_provider == "openai" and openai_timeout:
            try:
                effective_timeout = float(openai_timeout)
            except ValueError:
                effective_timeout = default_timeout
        elif os.getenv("HELIOX_LLM_TIMEOUT"):
            try:
                effective_timeout = float(os.getenv("HELIOX_LLM_TIMEOUT", "10.0"))
            except ValueError:
                effective_timeout = default_timeout
        else:
            effective_timeout = default_timeout

        self._provider = raw_provider
        self._api_key = raw_key
        self._endpoint = raw_endpoint
        self._model = raw_model
        self._timeout_seconds = effective_timeout
        self._fallback_extractor = NaturalLanguageExtractor()

        # Live status tracking
        if self.is_configured():
            self._last_status = f"{self._provider}_configured"
        else:
            self._last_status = f"{self._provider or 'openai'}_unconfigured"
        self._last_error: Optional[str] = None
        self._error_category: Optional[str] = None

    @staticmethod
    def _mask_key(key: str) -> str:
        """Mask API key for secure logging without credential leakage."""
        if not key:
            return "<none>"
        if len(key) <= 8:
            return "***"
        return f"{key[:3]}...{key[-3:]}"

    @property
    def provider_name(self) -> str:
        return self._provider or "unconfigured"

    @property
    def model_name(self) -> str:
        return self._model or "default"

    def is_configured(self) -> bool:
        """Return True if the provider has necessary configuration."""
        if self._provider in ("ollama", "local"):
            return bool(self._endpoint)
        return bool(self._provider and self._api_key and (self._endpoint or self._provider == "openai"))

    def get_status(self) -> Dict[str, Any]:
        """Return safe, non-sensitive provider configuration and availability status."""
        configured = self.is_configured()
        status = self._last_status
        provider_name = self._provider or "openai"

        if not configured:
            status = f"{provider_name}_unconfigured"
            status_label = f"Deterministic Parser Active ({provider_name.capitalize()} Unconfigured)"
            fallback_active = True
        elif status == f"{provider_name}_configured_and_available":
            status_label = f"{provider_name.upper()} ({self._model}) Active"
            fallback_active = False
        elif "rate_limited" in status:
            status_label = f"{provider_name.upper()} Rate Limited (Deterministic Fallback Active)"
            fallback_active = True
        elif "authentication_failed" in status or "auth_failed" in status:
            status_label = f"{provider_name.upper()} Auth Failed (Deterministic Fallback Active)"
            fallback_active = True
        elif "timeout" in status:
            status_label = f"{provider_name.upper()} Timeout (Deterministic Fallback Active)"
            fallback_active = True
        elif "temporarily_unavailable" in status or "error" in status or "failed" in status:
            status_label = f"{provider_name.capitalize()} Unavailable (Deterministic Fallback Active)"
            fallback_active = True
        else:
            status_label = f"{provider_name.capitalize()} Configured ({self._model})"
            fallback_active = False

        return {
            "provider": provider_name,
            "model": self._model,
            "is_configured": configured,
            "configured": configured,
            "has_api_key": bool(self._api_key),
            "masked_key": self._mask_key(self._api_key),
            "endpoint": self._endpoint,
            "status": status,
            "status_label": status_label,
            "fallback_active": fallback_active,
            "timeout_seconds": self._timeout_seconds,
            "supported_models": ["gpt-4o-mini", "gpt-4o"] if provider_name == "openai" else [self._model],
            "last_error": self._last_error,
            "error_category": getattr(self, "_error_category", None),
        }

    def extract_planning_context(
        self, prompt: str, reference_time: Optional[datetime] = None
    ) -> Optional[ExtractedPlanningContext]:
        if not self.is_configured():
            return None

        # Build schema instructions
        system_prompt = (
            "You are a structured planning extractor for HELIOX AI. "
            "Extract task titles, estimated durations in hours, priorities (1-5), deadlines, "
            "available time in hours, requested actions, dependencies, and whether clarification is needed. "
            "Respond ONLY with a valid JSON object matching this schema: "
            "{"
            "  \"tasks\": [{\"title\": str, \"priority\": int, \"estimated_duration\": float, \"deadline_expression\": str, \"dependencies\": [str]}], "
            "  \"available_hours\": float, "
            "  \"use_existing_tasks\": bool, "
            "  \"task_count\": int, "
            "  \"requested_actions\": [str], "
            "  \"clarification_needed\": bool, "
            "  \"clarification_question\": str"
            "}"
        )

        ref_dt = reference_time or self._fallback_extractor.get_reference_time()

        try:
            parsed = self._execute_provider_call(system_prompt, prompt)
            if not isinstance(parsed, dict):
                logger.warning("LLM provider returned non-dict JSON structure; falling back to deterministic parser.")
                return None

            # Strict schema validation and sanitization
            raw_tasks = parsed.get("tasks", [])
            validated_tasks: List[ExtractedTaskSpec] = []
            for t in raw_tasks:
                if not isinstance(t, dict):
                    continue
                raw_title = str(t.get("title", "")).strip()
                # Strip potential script, style, or HTML tags for safe display
                clean = re.sub(r"<script.*?>.*?</script>", "", raw_title, flags=re.DOTALL | re.IGNORECASE)
                clean = re.sub(r"<style.*?>.*?</style>", "", clean, flags=re.DOTALL | re.IGNORECASE)
                title = re.sub(r"<[^>]*>", "", clean).strip()
                if not title:
                    continue
                prio = int(t.get("priority", 3))
                prio = max(1, min(5, prio))
                dur = float(t.get("estimated_duration", 1.0))
                dur = max(0.25, min(24.0, dur))
                
                deadline_expr = str(t.get("deadline_expression", "")).strip() or None
                deadline_dt = None
                precision = None
                if deadline_expr:
                    _, deadline_dt, precision = self._fallback_extractor.parse_deadline(deadline_expr, ref_dt)
                
                raw_deps = t.get("dependencies", [])
                deps = [str(d).strip() for d in raw_deps if str(d).strip()] if isinstance(raw_deps, list) else []

                validated_tasks.append(
                    ExtractedTaskSpec(
                        title=title,
                        task_type=self._fallback_extractor._infer_task_type(title),
                        priority=prio,
                        estimated_duration=dur,
                        estimated_duration_unit="hours",
                        estimated_duration_source="conversational_input",
                        deadline_expression=deadline_expr,
                        deadline_dt=deadline_dt,
                        deadline_precision=precision,
                        dependencies=deps,
                        origin="proposed",
                    )
                )

            avail_h = parsed.get("available_hours")
            if avail_h is not None:
                try:
                    avail_h = max(0.25, min(24.0, float(avail_h)))
                except (ValueError, TypeError):
                    avail_h = None

            context = ExtractedPlanningContext(
                command=prompt,
                available_hours=avail_h,
                extracted_tasks=validated_tasks,
                clarification_needed=bool(parsed.get("clarification_needed", False)),
                clarification_question=parsed.get("clarification_question"),
                use_existing_tasks=bool(parsed.get("use_existing_tasks", False)),
                task_count=int(parsed["task_count"]) if parsed.get("task_count") is not None else None,
                parser_provenance=f"llm_{self._provider}",
            )
            return context

        except Exception as exc:
            if not getattr(self, "_error_category", None):
                self._last_status = f"{self._provider}_temporarily_unavailable"
                self._error_category = "PROVIDER_ERROR"
            if not self._last_error:
                self._last_error = str(exc)
            logger.warning(
                "LLM extraction via %s (key: %s) failed: %s; falling back to deterministic parser.",
                self._provider,
                self._mask_key(self._api_key),
                exc,
            )
            return None

    def parse_refinement(
        self,
        command: str,
        current_schedule: Optional[List[Dict[str, Any]]] = None,
        existing_schedule: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Use LLM structured output to interpret conversational refinement follow-ups.
        Returns a structured refinement dict, or None if extraction fails.
        """
        if not self.is_configured():
            return None

        system_prompt = (
            "You are a conversational planning refinement extractor for HELIOX AI. "
            "Analyze the user's follow-up request regarding their schedule or tasks. "
            "Identify the intended refinement action and target tasks/values. "
            "Valid actions are: 'move_first', 'reprioritize', 'alternative_schedule', "
            "'add_buffer', 'reduce_available_hours', 'reorder', 'accept_plan', 'reject_plan', "
            "'clarification_needed'. "
            "Respond ONLY with a valid JSON object matching this schema: "
            "{"
            "  \"action\": str, "
            "  \"task\": str, "
            "  \"second_task\": str, "
            "  \"new_priority\": int, "
            "  \"buffer_minutes\": float, "
            "  \"new_available_hours\": float, "
            "  \"clarification_question\": str, "
            "  \"description\": str"
            "}"
        )

        try:
            parsed = self._execute_provider_call(system_prompt, command)
            if isinstance(parsed, dict) and "action" in parsed:
                action = str(parsed["action"]).strip().lower()
                valid_actions = {
                    "move_first", "reprioritize", "alternative_schedule",
                    "add_buffer", "reduce_available_hours", "reorder",
                    "accept_plan", "reject_plan", "clarification_needed"
                }
                if action not in valid_actions:
                    return None

                result: Dict[str, Any] = {"action": action}
                if parsed.get("task"):
                    clean_task = re.sub(r"<[^>]*>", "", str(parsed["task"])).strip()
                    result["task"] = clean_task
                    result["first_task"] = clean_task
                if parsed.get("second_task"):
                    result["second_task"] = re.sub(r"<[^>]*>", "", str(parsed["second_task"])).strip()
                if parsed.get("new_priority") is not None:
                    try:
                        result["new_priority"] = max(1, min(5, int(parsed["new_priority"])))
                    except (ValueError, TypeError):
                        pass
                if parsed.get("buffer_minutes") is not None:
                    try:
                        result["buffer_minutes"] = max(5.0, min(240.0, float(parsed["buffer_minutes"])))
                        result["buffer_label"] = "buffer"
                    except (ValueError, TypeError):
                        pass
                if parsed.get("new_available_hours") is not None:
                    try:
                        result["new_available_hours"] = max(0.5, min(24.0, float(parsed["new_available_hours"])))
                    except (ValueError, TypeError):
                        pass
                if parsed.get("clarification_question"):
                    result["clarification_question"] = str(parsed["clarification_question"]).strip()
                if parsed.get("description"):
                    result["description"] = str(parsed["description"]).strip()
                else:
                    result["description"] = f"Conversational refinement: {action}"
                return result
        except Exception as exc:
            logger.warning("LLM refinement extraction failed: %s; falling back to deterministic parser.", exc)
            return None
        return None

    def generate_conversational_response(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_context: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate an open-ended conversational completion from the configured LLM.
        Returns a concise, helpful assistant response or None if LLM is unconfigured / fails.
        """
        if not self.is_configured():
            return None

        system_prompt = (
            "You are JAM (Just Autonomous Management), the personal AI companion for HELIOX AI. "
            "You help the user manage tasks, organize daily plans, optimize productivity, and answer questions. "
            "Be concise, conversational, friendly, and helpful. "
            "Never fabricate tasks, schedules, or capabilities that are not in the context. "
            "If the user asks to perform an action (like planning, task creation, or scheduling), "
            "confirm what you understand and guide them clearly."
        )
        if system_context:
            system_prompt += f"\n\nActive User Context:\n{system_context}"

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            for turn in conversation_history[-8:]:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": prompt})

        try:
            if self._provider == "gemini":
                endpoint = self._endpoint
                if "?key=" not in endpoint and self._api_key:
                    endpoint = f"{endpoint}?key={self._api_key}"
                headers = {"Content-Type": "application/json"}
                contents = []
                for m in messages:
                    contents.append({
                        "role": "user" if m["role"] in ("user", "system") else "model",
                        "parts": [{"text": m["content"]}],
                    })
                payload = {"contents": contents}
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self._last_status = "gemini_configured_and_available"
                    self._last_error = None
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()

            elif self._provider == "anthropic":
                headers = {
                    "Content-Type": "application/json",
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                }
                anthropic_messages = [
                    {"role": m["role"], "content": m["content"]}
                    for m in messages if m["role"] in ("user", "assistant")
                ]
                payload = {
                    "model": self._model,
                    "max_tokens": 800,
                    "system": system_prompt,
                    "messages": anthropic_messages,
                }
                req = urllib.request.Request(
                    self._endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self._last_status = "anthropic_configured_and_available"
                    self._last_error = None
                    return data["content"][0]["text"].strip()

            else:
                # OpenAI-compatible
                endpoint = self._endpoint or "https://api.openai.com/v1/chat/completions"
                headers = {"Content-Type": "application/json"}
                if self._api_key:
                    headers["Authorization"] = f"Bearer {self._api_key}"
                payload = {
                    "model": self._model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 800,
                }
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                data = self._execute_http_request(req)
                self._last_status = f"{self._provider}_configured_and_available"
                self._last_error = None
                self._error_category = None
                return str(data["choices"][0]["message"]["content"]).strip()

        except urllib.error.HTTPError as http_err:
            if http_err.code == 401:
                self._last_status = f"{self._provider}_authentication_failed"
                self._last_error = f"{self._provider.upper()} authentication failed: invalid or expired API key (HTTP 401)"
                self._error_category = "AUTHENTICATION_ERROR"
            elif http_err.code == 429:
                self._last_status = f"{self._provider}_rate_limited"
                self._last_error = f"{self._provider.upper()} rate limit or quota exceeded (HTTP 429)"
                self._error_category = "RATE_LIMIT_EXCEEDED"
            elif http_err.code in (408, 504):
                self._last_status = f"{self._provider}_timeout"
                self._last_error = f"{self._provider.upper()} request timeout (HTTP {http_err.code})"
                self._error_category = "TIMEOUT"
            else:
                self._last_status = f"{self._provider}_temporarily_unavailable"
                self._last_error = f"{self._provider.upper()} HTTP error: {http_err.code}"
                self._error_category = "HTTP_ERROR"
            logger.warning("Conversational call via %s failed: %s", self._provider, self._last_error)
            return None
        except Exception as exc:
            self._last_status = f"{self._provider}_temporarily_unavailable"
            self._last_error = f"Conversational call failed: {exc}"
            self._error_category = "PROVIDER_ERROR"
            logger.warning("Conversational call via %s failed: %s", self._provider, exc)
            return None

    def _execute_http_request(self, req: urllib.request.Request) -> Dict[str, Any]:
        """Execute underlying HTTP request and return parsed JSON response."""
        with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
            resp_data = resp.read().decode("utf-8")
            return json.loads(resp_data)

    def _execute_provider_call(self, system_prompt: str, prompt: str) -> Dict[str, Any]:
        """Execute HTTP request formatted according to the configured LLM provider."""
        if self._provider == "gemini":
            endpoint = self._endpoint
            if "?key=" not in endpoint and self._api_key:
                endpoint = f"{endpoint}?key={self._api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{system_prompt}\n\nUser Planning Request:\n{prompt}"}
                        ]
                    }
                ],
                "generationConfig": {"response_mime_type": "application/json"},
            }
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self._last_status = "gemini_configured_and_available"
                self._last_error = None
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)

        elif self._provider == "anthropic":
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            }
            payload = {
                "model": self._model,
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": [{"role": "user", "content": prompt}],
            }
            req = urllib.request.Request(
                self._endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self._last_status = "anthropic_configured_and_available"
                self._last_error = None
                text = data["content"][0]["text"]
                cleaned_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
                return json.loads(cleaned_text)

        else:
            # Standard OpenAI-compatible format (OpenAI, Groq, Ollama, Local HTTP)
            endpoint = self._endpoint or "https://api.openai.com/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            payload = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
            }
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                data = self._execute_http_request(req)
                self._last_status = f"{self._provider}_configured_and_available"
                self._last_error = None
                self._error_category = None
                content = data["choices"][0]["message"]["content"]
                if isinstance(content, dict):
                    return content
                return json.loads(content)
            except urllib.error.HTTPError as http_err:
                if http_err.code == 401:
                    self._last_status = "openai_authentication_failed"
                    self._last_error = "OpenAI authentication failed: invalid or expired API key (HTTP 401)"
                    self._error_category = "AUTHENTICATION_ERROR"
                elif http_err.code == 429:
                    self._last_status = "openai_rate_limited"
                    self._last_error = "OpenAI rate limit or quota exceeded (HTTP 429)"
                    self._error_category = "RATE_LIMIT_EXCEEDED"
                elif http_err.code in (408, 504):
                    self._last_status = "openai_timeout"
                    self._last_error = f"OpenAI request timeout (HTTP {http_err.code})"
                    self._error_category = "TIMEOUT"
                elif http_err.code in (500, 502, 503):
                    self._last_status = "openai_temporarily_unavailable"
                    self._last_error = f"OpenAI service unavailable or outage (HTTP {http_err.code})"
                    self._error_category = "SERVICE_UNAVAILABLE"
                else:
                    self._last_status = "openai_temporarily_unavailable"
                    self._last_error = f"OpenAI HTTP error: {http_err.code}"
                    self._error_category = "HTTP_ERROR"
                logger.warning(
                    "OpenAI call failed via %s [key: %s]: %s; falling back to deterministic parser.",
                    self._provider,
                    self._mask_key(self._api_key),
                    self._last_error,
                )
                raise
            except TimeoutError as timeout_err:
                self._last_status = "openai_timeout"
                self._last_error = f"OpenAI request timed out: {timeout_err}"
                self._error_category = "TIMEOUT"
                logger.warning(
                    "OpenAI timeout via %s [key: %s]: %s; falling back to deterministic parser.",
                    self._provider,
                    self._mask_key(self._api_key),
                    self._last_error,
                )
                raise
            except urllib.error.URLError as net_err:
                self._last_status = "openai_network_error"
                self._last_error = f"OpenAI network error: {net_err.reason}"
                self._error_category = "NETWORK_ERROR"
                logger.warning(
                    "OpenAI network error via %s [key: %s]: %s; falling back to deterministic parser.",
                    self._provider,
                    self._mask_key(self._api_key),
                    self._last_error,
                )
                raise
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as malformed_err:
                self._last_status = "openai_malformed_output"
                self._last_error = f"Malformed payload from {self._provider}: {malformed_err}"
                self._error_category = "INVALID_PAYLOAD"
                logger.warning(
                    "Malformed response from %s: %s; falling back to deterministic parser.",
                    self._provider,
                    malformed_err,
                )
                raise


class OpenAIProvider(ConfiguredLLMProvider):
    """
    Dedicated OpenAI LLM provider integration for HELIOX AI.
    Conforms to official OpenAI chat completions API with JSON mode structured output.
    Reads credentials strictly from OPENAI_API_KEY and model from OPENAI_MODEL.
    Handles rate limits, auth errors, timeouts, outages, and malformed responses.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        raw_key = api_key.strip() if api_key is not None else (os.getenv("OPENAI_API_KEY", "").strip() or os.getenv("HELIOX_LLM_API_KEY", "").strip())
        raw_model = model or os.getenv("OPENAI_MODEL", "").strip() or os.getenv("HELIOX_LLM_MODEL", "gpt-4o-mini").strip()
        openai_base = os.getenv("OPENAI_BASE_URL", os.getenv("OPENAI_API_BASE", "")).strip()
        raw_endpoint = endpoint or os.getenv("HELIOX_LLM_ENDPOINT", "").strip()
        if not raw_endpoint:
            raw_endpoint = f"{openai_base.rstrip('/')}/chat/completions" if openai_base else "https://api.openai.com/v1/chat/completions"

        openai_timeout = os.getenv("OPENAI_TIMEOUT", "").strip()
        if timeout_seconds is not None:
            effective_timeout = float(timeout_seconds)
        elif openai_timeout:
            try:
                effective_timeout = float(openai_timeout)
            except ValueError:
                effective_timeout = 10.0
        elif os.getenv("HELIOX_LLM_TIMEOUT"):
            try:
                effective_timeout = float(os.getenv("HELIOX_LLM_TIMEOUT", "10.0"))
            except ValueError:
                effective_timeout = 10.0
        else:
            effective_timeout = 10.0

        super().__init__(
            provider="openai",
            api_key=raw_key,
            endpoint=raw_endpoint,
            model=raw_model,
            timeout_seconds=effective_timeout,
        )

    def test_connection(self) -> Tuple[bool, str]:
        """
        Perform a live lightweight ping test to verify connectivity with OpenAI.
        Distinguishes missing configuration, invalid credentials, rate limit / quota,
        network errors, timeouts, and successful connectivity.
        """
        if not self.is_configured():
            return False, "OpenAI provider is unconfigured (OPENAI_API_KEY missing)."
        try:
            res = self._execute_provider_call(
                "You are HELIOX AI health checker. Respond ONLY with valid JSON: {\"status\": \"ok\"}",
                "ping",
            )
            if isinstance(res, dict) and res.get("status") == "ok":
                self._last_status = "openai_configured_and_available"
                self._last_error = None
                self._error_category = None
                return True, f"Connection to OpenAI ({self._model}) succeeded."
            return False, "Unexpected response format received from OpenAI."
        except urllib.error.HTTPError as http_err:
            if http_err.code == 401:
                return False, "Invalid API key (HTTP 401 Unauthorized). Please check your OPENAI_API_KEY."
            elif http_err.code == 429:
                return False, "OpenAI API quota or rate limit exceeded (HTTP 429). Please check your OpenAI account billing/usage."
            elif http_err.code in (408, 504):
                return False, f"OpenAI request timed out (HTTP {http_err.code})."
            elif http_err.code in (500, 502, 503):
                return False, f"OpenAI server error or temporary outage (HTTP {http_err.code})."
            return False, f"OpenAI HTTP error: {http_err.code} ({http_err.reason})"
        except TimeoutError:
            return False, f"Connection to OpenAI timed out after {self._timeout_seconds}s."
        except urllib.error.URLError as url_err:
            return False, f"Network connection failed: {url_err.reason}"
        except Exception as exc:
            return False, f"OpenAI connection error: {exc}"


class DeterministicFallbackProvider(BaseLLMProvider):
    """
    Deterministic rule-based extractor using regex, grammar heuristics, and controllable clocks.
    Provides robust, offline, zero-dependency baseline for all planning requests.
    """

    def __init__(self, clock: Optional[Callable[[], datetime]] = None) -> None:
        self.extractor = NaturalLanguageExtractor(clock=clock)

    @property
    def provider_name(self) -> str:
        return "deterministic_rule_based"

    def is_configured(self) -> bool:
        return True

    def extract_planning_context(
        self, prompt: str, reference_time: Optional[datetime] = None
    ) -> ExtractedPlanningContext:
        ctx = self.extractor.extract_planning_context(prompt, reference_time=reference_time)
        ctx.parser_provenance = "deterministic_fallback"
        return ctx

    def parse_refinement(
        self,
        command: str,
        current_schedule: Optional[List[Dict[str, Any]]] = None,
        existing_schedule: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        schedule = current_schedule or existing_schedule
        return self.extractor.parse_refinement(command, current_schedule=schedule)

    def generate_conversational_response(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_context: Optional[str] = None,
    ) -> str:
        """Deterministic conversational responses for greetings, help, and guided workflows."""
        lowered = prompt.strip().lower()
        if any(g in lowered for g in ("hello", "hi", "hey", "good morning", "good afternoon", "good evening")):
            return (
                "Hello! I am JAM, your personal AI companion in HELIOX. "
                "I can help organize your day, create and prioritize tasks, optimize your schedule, "
                "and analyze your productivity.\n\n"
                "What would you like to focus on today?"
            )
        if any(h in lowered for h in ("what can you do", "help", "how do you work", "commands", "features", "capabilities")):
            return (
                "Here are the core workflows I can handle for you:\n\n"
                "• **Plan your day**: 'Plan my day with 4 hours available'\n"
                "• **Create tasks**: 'Create task: Review project requirements with priority 4'\n"
                "• **List tasks**: 'Show my tasks' or 'What are my pending tasks?'\n"
                "• **Prioritize**: 'Which task should I do first?'\n"
                "• **Optimize**: 'Optimize my schedule'\n"
                "• **Insights**: 'Analyze my productivity trends'\n\n"
                "How can I help you get started?"
            )
        if "thank" in lowered:
            return "You're very welcome! Let me know whenever you're ready to plan or review your tasks."

        context_suffix = f"\n\nActive workspace context: {system_context}" if system_context else ""
        return (
            f"I hear you. As your HELIOX AI assistant, I can help schedule your day, manage your tasks, "
            f"or optimize your workflow.{context_suffix}\n\n"
            f"To get started, try asking me to plan your day (e.g. 'Plan my day with 4 hours available') "
            f"or add a new task (e.g. 'Create task: {prompt[:30]}')."
        )


class HybridPlanningParser:
    """
    Unified entry point for natural-language planning queries.
    Uses ConfiguredLLMProvider/OpenAIProvider if configured and valid; falls back gracefully to
    DeterministicFallbackProvider without failing or pretending rule-based logic is an LLM.
    """

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        fallback_provider: Optional[BaseLLMProvider] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.llm_provider = llm_provider or OpenAIProvider()
        self.fallback_provider = fallback_provider or DeterministicFallbackProvider(clock=clock)
        self.clock = clock

    def parse(
        self, prompt: str, reference_time: Optional[datetime] = None
    ) -> ExtractedPlanningContext:
        """Parse natural language planning prompt with graceful fallback."""
        if self.llm_provider and self.llm_provider.is_configured():
            try:
                res = self.llm_provider.extract_planning_context(prompt, reference_time=reference_time)
                if res is not None:
                    return res
            except Exception as e:
                logger.warning("LLM provider error: %s; falling back to deterministic parser.", e)

        # Fallback to deterministic parser
        return self.fallback_provider.extract_planning_context(prompt, reference_time=reference_time)

    extract_planning_context = parse

    def parse_refinement(
        self,
        command: str,
        current_schedule: Optional[List[Dict[str, Any]]] = None,
        existing_schedule: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Parse conversational plan refinement with LLM or fallback."""
        schedule = current_schedule or existing_schedule
        if self.llm_provider and self.llm_provider.is_configured():
            if hasattr(self.llm_provider, "parse_refinement"):
                try:
                    res = self.llm_provider.parse_refinement(
                        command,
                        current_schedule=schedule,
                        existing_schedule=schedule,
                    )
                    if res and isinstance(res, dict) and "action" in res:
                        return res
                except Exception as e:
                    logger.warning("LLM refinement extraction error: %s; using deterministic extractor.", e)
        # Deterministic rule-based extraction
        from backend.app.interface.nl_extractor import NaturalLanguageExtractor
        extractor = NaturalLanguageExtractor(clock=self.clock)
        return extractor.parse_refinement(command, current_schedule=schedule)

    def generate_chat_response(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_context: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Generate conversational response, trying the configured LLM first and falling back
        deterministically if unconfigured or unavailable. Returns (response_text, provenance).
        """
        if self.llm_provider and self.llm_provider.is_configured():
            if hasattr(self.llm_provider, "generate_conversational_response"):
                try:
                    llm_text = self.llm_provider.generate_conversational_response(
                        prompt,
                        conversation_history=conversation_history,
                        system_context=system_context,
                    )
                    if llm_text:
                        return llm_text, f"llm_{self.llm_provider.provider_name}"
                except Exception as exc:
                    logger.warning("LLM conversational generation failed: %s; falling back.", exc)

        # Grounded deterministic fallback
        if hasattr(self.fallback_provider, "generate_conversational_response"):
            fb_text = self.fallback_provider.generate_conversational_response(
                prompt,
                conversation_history=conversation_history,
                system_context=system_context,
            )
            return fb_text, "deterministic_fallback"

        return (
            "I am ready to help organize your tasks and daily schedule. "
            "Try asking me to plan your day or show your tasks!",
            "deterministic_fallback",
        )

    extract_planning_context = parse

    def parse_refinement(
        self,
        command: str,
        current_schedule: Optional[List[Dict[str, Any]]] = None,
        existing_schedule: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Parse conversational plan refinement with LLM or fallback."""
        schedule = current_schedule or existing_schedule
        if self.llm_provider and self.llm_provider.is_configured():
            if hasattr(self.llm_provider, "parse_refinement"):
                try:
                    res = self.llm_provider.parse_refinement(
                        command,
                        current_schedule=schedule,
                        existing_schedule=schedule,
                    )
                    if res and isinstance(res, dict) and "action" in res:
                        return res
                except Exception as e:
                    logger.warning("LLM refinement extraction error: %s; using deterministic extractor.", e)
        # Deterministic rule-based extraction
        from backend.app.interface.nl_extractor import NaturalLanguageExtractor
        extractor = NaturalLanguageExtractor(clock=self.clock)
        return extractor.parse_refinement(command, current_schedule=schedule)

    def get_provider_status(self) -> Dict[str, Any]:
        """Return provider configuration status safely."""
        if hasattr(self.llm_provider, "get_status"):
            return self.llm_provider.get_status()
        return {
            "provider": getattr(self.llm_provider, "provider_name", "unconfigured"),
            "is_configured": getattr(self.llm_provider, "is_configured", lambda: False)(),
            "fallback_active": True,
        }
