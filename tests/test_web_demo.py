"""Run: baselines\\lumo\\.venv\\Scripts\\python.exe tests\\test_web_demo.py   (also works under pytest)"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo"))
import web_demo as w


def test_short_phrase_starts_no_turn():
    n = len(w.S["turns"])
    w.heard_event("heard", text="hi")  # the loop drops it: the page must not go to "Reading"
    assert len(w.S["turns"]) == n and w.READ not in w.S["on"]


def test_phrase_starts_a_turn_and_ends_terminate():
    w.S["skip"] = True
    w.heard_event("heard", text="what time is it")
    assert w.S["turns"][-1]["heard"] == "what time is it" and w.S["on"] == {w.READ} and not w.S["skip"]


def test_state_matches_the_loop():
    w.S.update(on={w.READ}, running=False)
    assert json.loads(w.state())["on"] == []  # stopped loop: nothing lit
    w.S.update(on=set(), running=True)
    w.g.update(llm=1, is_speaking=True)
    assert json.loads(w.state())["on"] == ["Speaking"]  # mic muted between clips is not "Thinking"
    w.g["is_speaking"] = False
    assert json.loads(w.state())["on"] == ["Listening"]
    w.S["running"] = False


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
