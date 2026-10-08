"""Run: baselines\\lumo\\.venv\\Scripts\\python.exe tests\\test_asr_fix.py   (also works under pytest)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from asr_fix import fix_asr


def test_there_before_a_question_verb_becomes_where():
    assert fix_asr("there is the library") == "where is the library"
    assert fix_asr("There are my keys") == "where are my keys"
    assert fix_asr("there can i buy bread") == "where can i buy bread"


def test_everything_else_is_untouched():
    for t in ["is there a bank nearby", "where is the library", "thereafter is fine", "there", "over there is it", ""]:
        assert fix_asr(t) == t


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
