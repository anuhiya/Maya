"""Save and replay agent runs when Groq is unreachable (B9)."""
import json
import re
from pathlib import Path


class ReplayError(RuntimeError):
    """No saved reply is available for what was asked."""


def _file(replay_dir, run_name):
    if not re.fullmatch(r"[A-Za-z0-9._-]+", run_name or ""):
        raise ReplayError(f"Run name {run_name!r} is not valid: use letters, digits, dot, dash or underscore.")
    return Path(replay_dir) / f"{run_name}.json"


def save_run(run_name, records, replay_dir, federal_register=None):
    """Write a run's recorded calls to <replay_dir>/<run_name>.json and return the path.

    federal_register is the search result of the run (title, date and url per item), kept so a replay
    needs no network.
    """
    path = _file(replay_dir, run_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = [r for r in records if not r.get("replayed")]
    data = {"run": run_name, "records": kept}
    if federal_register is not None:
        data["federal_register"] = federal_register
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_federal_register(replay_dir, run_name):
    """The Federal Register items saved with a run, or None when the run has none."""
    try:
        data = json.loads(_file(replay_dir, run_name).read_text(encoding="utf-8"))
    except (OSError, ReplayError, ValueError):
        return None
    return data.get("federal_register")


class ReplayPlayer:
    """Plays back saved replies, matched by call kind plus a hash of the prompt."""

    def __init__(self, run_name, replay_dir):
        self.run_name = run_name
        self.path = _file(replay_dir, run_name)
        if not self.path.exists():
            raise ReplayError(
                f"No saved run named {run_name!r}: expected {self.path}. "
                "Set MAYA_REPLAY_RUN to a saved run or set MAYA_LLM_PROVIDER=groq with GROQ_API_KEY."
            )
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.federal_register = data.get("federal_register")
        self._by_key = {}
        for record in data["records"]:
            self._by_key.setdefault((record["kind"], record["prompt_hash"]), record)

    def get(self, kind, prompt_hash):
        try:
            return self._by_key[(kind, prompt_hash)]
        except KeyError:
            raise ReplayError(
                f"Saved run {self.run_name!r} has no reply for {kind} with this prompt. "
                "The policy text or the prompt changed since it was saved."
            ) from None
