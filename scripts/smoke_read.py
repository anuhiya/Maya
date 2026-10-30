"""One live read_section pass over gov_rules_v2 (reader model), saved as a replay run."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maya.ai.llm import LLM, LLMError
from maya.ai.prompts import read_section
from maya.site import load_config
from maya.split import read_sections

RUN_NAME = "smoke_v2_read"


def _squash(text):
    return " ".join(text.split())


def main():
    cfg = load_config()
    llm = LLM(cfg=cfg)
    usage = {"prompt": 0, "completion": 0, "calls": 0}
    create = llm._groq().chat.completions.create

    def counted(*args, **kwargs):
        response = create(*args, **kwargs)
        usage["calls"] += 1
        usage["prompt"] += response.usage.prompt_tokens
        usage["completion"] += response.usage.completion_tokens
        return response

    llm._groq().chat.completions.create = counted

    sections = read_sections(Path(cfg["_root"]) / cfg["policies"]["main_pair"]["new"])
    failed = []
    started = time.monotonic()
    for section in sections:
        system, user = read_section(section)
        try:
            reply = llm.call("read_section", system, user, role="reader")
        except LLMError as err:
            failed.append((section.number, str(err)))
            print(f"{section.number}  FAILED SCHEMA")
            continue
        a = reply.answer
        verbatim = _squash(a.rule_quote) in _squash(section.text)
        retry = f" (retries {reply.retries})" if reply.retries else ""
        print(f"{section.number}  {a.category}  {a.value}  {a.effective_date}  quote verbatim: {'yes' if verbatim else 'NO'}{retry}")
    elapsed = time.monotonic() - started

    path = llm.save_run(RUN_NAME)
    print(f"saved {path}")
    print(f"{len(sections)} sections, {usage['calls']} calls, {elapsed:.1f}s, "
          f"{usage['prompt']} prompt + {usage['completion']} completion tokens")
    for number, err in failed:
        print(f"schema failure {number}: {err[:300]}")


if __name__ == "__main__":
    main()
