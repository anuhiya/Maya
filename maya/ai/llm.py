"""Groq client, retries and logging (B9, P3)."""
import hashlib
import logging
import os
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from maya.ai.replay import ReplayPlayer, save_run
from maya.ai.schemas import SCHEMAS, groq_json_schema
from maya.site import ROOT, load_config

BASE_URL = "https://api.groq.com/openai/v1"
TIMEOUT_SECONDS = 60
REASONING_EFFORT = "low"
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_DEFAULT_WAIT = 10
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"

log = logging.getLogger("maya.ai.llm")


class LLMError(RuntimeError):
    """The model could not give an answer that fits its schema."""


class MissingSettingError(LLMError):
    """A setting needed to reach a model is missing."""


@dataclass
class Reply:
    """One AI answer with everything needed to log it."""

    kind: str
    answer: Any  # instance of the schema for `kind`
    system: str
    user: str
    raw: str
    provider: str
    model: str
    replayed: bool = False
    retries: int = 0
    errors: list = field(default_factory=list)


def prompt_hash(system, user):
    return hashlib.sha256(f"{system}\n\n{user}".encode("utf-8")).hexdigest()[:16]


def _secrets(path):
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return {}


def _retry_after(err):
    """Seconds Groq asks us to wait, or the default."""
    try:
        return float(err.response.headers["retry-after"])
    except (AttributeError, KeyError, TypeError, ValueError):
        return RATE_LIMIT_DEFAULT_WAIT


class LLM:
    """Groq only, through the OpenAI-compatible API. Or a saved run, when the provider is replay."""

    def __init__(self, *, cfg=None, env=None, secrets_path=SECRETS_PATH, client=None, run_name=None):
        cfg = cfg or load_config()
        self._env = os.environ if env is None else env
        self._secrets = _secrets(secrets_path)
        self.models = {"reader": cfg["llm"]["reader_model"], "planner": cfg["llm"]["planner_model"]}
        self.replay_dir = cfg["_root"] / cfg["llm"]["replay_dir"]
        self.provider = self._setting("MAYA_LLM_PROVIDER") or "groq"
        self.run_name = run_name or self._setting("MAYA_REPLAY_RUN")
        self.records = []
        self._client = client
        self._player = None
        if self.provider == "replay":
            if not self.run_name:
                raise MissingSettingError("MAYA_LLM_PROVIDER is replay but MAYA_REPLAY_RUN (the saved run name) is not set.")
            self._player = ReplayPlayer(self.run_name, self.replay_dir)
        elif self.provider == "groq":
            if self._client is None and not self._key():
                raise MissingSettingError(
                    "GROQ_API_KEY is not set (environment variable or .streamlit/secrets.toml). "
                    "Set it, or set MAYA_LLM_PROVIDER=replay with MAYA_REPLAY_RUN to play back a saved run."
                )
        else:
            raise MissingSettingError(f"MAYA_LLM_PROVIDER must be groq or replay, not {self.provider!r}.")

    def _setting(self, name):
        return self._env.get(name) or self._secrets.get(name)

    def _key(self):
        return self._setting("GROQ_API_KEY")

    def _redact(self, text):
        key = self._key()
        return str(text).replace(key, "***") if key else str(text)

    def _groq(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._key(), base_url=BASE_URL, timeout=TIMEOUT_SECONDS)
        return self._client

    def call(self, kind, system, user, *, role="reader"):
        """Ask for one answer of type `kind`. Returns a Reply; raises LLMError if it never fits the schema."""
        schema = SCHEMAS[kind]
        digest = prompt_hash(system, user)
        if self._player is not None:
            reply = self._replay(kind, schema, system, user, digest)
        else:
            reply = self._ask(kind, schema, system, user, role)
        self.records.append({
            "kind": kind, "role": role, "prompt_hash": digest, "system": system, "user": user,
            "reply": reply.raw, "provider": reply.provider, "model": reply.model,
            "replayed": reply.replayed, "retries": reply.retries,
        })
        log.info("%s answered %s via %s%s", reply.model, kind, reply.provider, " (replayed from saved run)" if reply.replayed else "")
        return reply

    def _replay(self, kind, schema, system, user, digest):
        saved = self._player.get(kind, digest)
        try:
            answer = schema.model_validate_json(saved["reply"])
        except ValidationError as err:
            raise LLMError(f"Saved reply for {kind} no longer fits its schema: {err}") from None
        return Reply(kind, answer, system, user, saved["reply"], saved["provider"], saved["model"], replayed=True)

    def _ask(self, kind, schema, system, user, role):
        model = self.models[role]
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": kind, "strict": True, "schema": groq_json_schema(schema)},
        }
        errors = []
        for attempt in range(2):
            response = self._create(kind, model, messages, response_format)
            raw = response.choices[0].message.content or ""
            try:
                answer = schema.model_validate_json(raw)
            except ValidationError as err:
                errors.append(str(err))
                log.warning("%s reply for %s failed its schema (attempt %d)", model, kind, attempt + 1)
                messages = messages + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": f"Your reply did not fit the required JSON format:\n{err}\nReply again with corrected JSON only."},
                ]
                continue
            return Reply(kind, answer, system, user, raw, "groq", model, retries=attempt, errors=errors)
        raise LLMError(f"{model} reply for {kind} failed its schema twice: {errors[-1]}")

    def _create(self, kind, model, messages, response_format):
        """One Groq call; waits and retries on a rate-limit reply (HTTP 429)."""
        waits = 0
        while True:
            try:
                return self._groq().chat.completions.create(
                    model=model, messages=messages, temperature=0, response_format=response_format,
                    extra_body={"reasoning_effort": REASONING_EFFORT},
                )
            except Exception as err:  # network, auth, rate limit: never leak the key
                if getattr(err, "status_code", None) == 429 and waits < RATE_LIMIT_RETRIES:
                    waits += 1
                    log.warning("waiting for Groq rate limit (%ss, retry %d of %d)", _retry_after(err), waits, RATE_LIMIT_RETRIES)
                    time.sleep(_retry_after(err))
                    continue
                raise LLMError(f"Groq call for {kind} failed: {self._redact(err)}") from None

    def save_run(self, run_name):
        """Save this run's replies to <replay_dir>/<run_name>.json."""
        return save_run(run_name, self.records, self.replay_dir)
