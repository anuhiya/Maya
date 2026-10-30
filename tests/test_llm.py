"""Tests for maya/ai/llm.py, prompts.py and replay.py with a fake client only (B9, A2)."""
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from maya.ai import prompts
from maya.ai.llm import LLM, LLMError, MissingSettingError
from maya.ai.replay import ReplayError
from maya.models import Section

KEY = "gsk_test_secret_value_123"
CFG = {
    "_root": None,
    "llm": {"reader_model": "openai/gpt-oss-120b", "planner_model": "openai/gpt-oss-20b", "replay_dir": "data/replays"},
}
COMPARE = {"change_type": "substantive", "facts_changed": ["value"], "reason": "Wage rose from 16.00 to 17.25."}
SECTION = Section(number="3.1", title="Minimum wage", text="The minimum wage shall be $17.25 per hour.")


class FakeClient:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=item))])


@pytest.fixture
def cfg(tmp_path):
    return {**CFG, "_root": tmp_path}


def make(cfg, tmp_path, client=None, env=None, **kw):
    env = {"GROQ_API_KEY": KEY} if env is None else env
    return LLM(cfg=cfg, env=env, secrets_path=tmp_path / "none.toml", client=client, **kw)


def ask(llm):
    system, user = prompts.compare_section(SECTION, SECTION)
    return llm.call("compare_section", system, user)


def test_valid_reply_uses_config_model_and_settings(cfg, tmp_path):
    client = FakeClient(json.dumps(COMPARE))
    reply = ask(make(cfg, tmp_path, client))
    call = client.calls[0]
    assert reply.answer.change_type == "substantive" and not reply.replayed and reply.retries == 0
    assert call["model"] == "openai/gpt-oss-120b" and call["temperature"] == 0
    assert call["extra_body"] == {"reasoning_effort": "low"}
    assert call["response_format"]["json_schema"]["strict"] is True


def test_planner_role_uses_planner_model(cfg, tmp_path):
    client = FakeClient(json.dumps(COMPARE))
    make(cfg, tmp_path, client).call("compare_section", "s", "u", role="planner")
    assert client.calls[0]["model"] == "openai/gpt-oss-20b"


def test_bad_json_is_retried_once_with_the_error(cfg, tmp_path):
    client = FakeClient("not json at all", json.dumps(COMPARE))
    reply = ask(make(cfg, tmp_path, client))
    assert reply.retries == 1 and len(reply.errors) == 1
    retry_messages = client.calls[1]["messages"]
    assert retry_messages[-2] == {"role": "assistant", "content": "not json at all"}
    assert "did not fit" in retry_messages[-1]["content"] and "Invalid JSON" in retry_messages[-1]["content"]


def test_second_failure_raises(cfg, tmp_path):
    client = FakeClient("nope", '{"change_type": "other"}')
    with pytest.raises(LLMError, match="failed its schema twice"):
        ask(make(cfg, tmp_path, client))
    assert len(client.calls) == 2


def test_replay_returns_saved_replies_marked_replayed(cfg, tmp_path):
    live = make(cfg, tmp_path, FakeClient(json.dumps(COMPARE)))
    ask(live)
    live.save_run("demo")
    saved = json.loads((tmp_path / "data/replays/demo.json").read_text())["records"][0]
    assert saved["provider"] == "groq" and saved["model"] == "openai/gpt-oss-120b"
    replay = make(cfg, tmp_path, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "demo"})
    reply = ask(replay)
    assert reply.replayed and reply.answer.reason == COMPARE["reason"]
    assert reply.model == "openai/gpt-oss-120b" and replay.records[0]["replayed"] is True


def test_replay_without_matching_prompt_raises(cfg, tmp_path):
    live = make(cfg, tmp_path, FakeClient(json.dumps(COMPARE)))
    ask(live)
    live.save_run("demo")
    replay = make(cfg, tmp_path, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "demo"})
    with pytest.raises(ReplayError, match="no reply"):
        replay.call("compare_section", "other", "prompt")


def test_replay_missing_run_names_the_setting(cfg, tmp_path):
    with pytest.raises(ReplayError, match="MAYA_REPLAY_RUN"):
        make(cfg, tmp_path, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "gone"})
    with pytest.raises(MissingSettingError, match="MAYA_REPLAY_RUN"):
        make(cfg, tmp_path, env={"MAYA_LLM_PROVIDER": "replay"})


def test_missing_key_and_no_replay_names_the_setting(cfg, tmp_path):
    with pytest.raises(MissingSettingError, match="GROQ_API_KEY"):
        make(cfg, tmp_path, env={})


def test_key_is_read_from_secrets_file(cfg, tmp_path):
    secrets = tmp_path / "secrets.toml"
    secrets.write_text(f'GROQ_API_KEY = "{KEY}"\n')
    llm = LLM(cfg=cfg, env={}, secrets_path=secrets, client=None)
    assert llm._key() == KEY


def test_key_never_appears_in_logs_errors_or_records(cfg, tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    ok = make(cfg, tmp_path, FakeClient("bad", json.dumps(COMPARE)))
    ask(ok)
    failing = make(cfg, tmp_path, FakeClient(RuntimeError(f"401 bad key {KEY}")))
    with pytest.raises(LLMError) as err:
        ask(failing)
    assert KEY not in str(err.value) and "***" in str(err.value)
    ok.save_run("demo")
    saved = (tmp_path / "data/replays/demo.json").read_text()
    assert KEY not in caplog.text and KEY not in saved and KEY not in json.dumps(ok.records)


def test_prompts_carry_the_definitions_word_for_word():
    plan = Path(__file__).resolve().parent.parent / "docs" / "plan.md"
    text = " ".join(plan.read_text(encoding="utf-8").split())
    assert " ".join(prompts.CATEGORY_DEFINITIONS.split()) in text
    for line in prompts.CHANGE_TYPE_DEFINITIONS.splitlines():
        assert " ".join(line[2:].split()) in text
    system, user = prompts.read_section(SECTION)
    assert prompts.CATEGORY_DEFINITIONS in system and "copied exactly" in system and SECTION.text in user
    system, user = prompts.compare_section(None, SECTION)
    assert prompts.CHANGE_TYPE_DEFINITIONS in system and "does not exist" in user


class RateLimited(Exception):
    status_code = 429

    def __init__(self, retry_after=None):
        super().__init__("429 rate limit")
        self.response = SimpleNamespace(headers={} if retry_after is None else {"retry-after": retry_after})


def test_rate_limit_waits_retry_after_then_succeeds(cfg, tmp_path, monkeypatch, caplog):
    sleeps = []
    monkeypatch.setattr("maya.ai.llm.time.sleep", sleeps.append)
    client = FakeClient(RateLimited("7"), RateLimited(), json.dumps(COMPARE))
    with caplog.at_level(logging.WARNING, logger="maya.ai.llm"):
        reply = ask(make(cfg, tmp_path, client))
    assert reply.answer.change_type == "substantive" and len(client.calls) == 3
    assert sleeps == [7.0, 10] and "waiting for Groq rate limit" in caplog.text


def test_rate_limit_gives_up_after_three_retries(cfg, tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr("maya.ai.llm.time.sleep", sleeps.append)
    client = FakeClient(*[RateLimited() for _ in range(4)])
    with pytest.raises(LLMError):
        ask(make(cfg, tmp_path, client))
    assert len(client.calls) == 4 and len(sleeps) == 3
