"""Run: baselines\\lumo\\.venv\\Scripts\\python.exe tests\\test_asr_fix.py   (also works under pytest)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from asr_fix import fix_asr, is_exit, cut_role_echo, stop_at_role_echo


def test_there_before_a_question_verb_becomes_where():
    assert fix_asr("there is the library") == "where is the library"
    assert fix_asr("There are my keys") == "where are my keys"
    assert fix_asr("there can i buy bread") == "where can i buy bread"


def test_everything_else_is_untouched():
    for t in ["is there a bank nearby", "where is the library", "thereafter is fine", "there", "over there is it", ""]:
        assert fix_asr(t) == t


def test_exit_heard_with_a_noise_word():
    ex = ["exit", "quit", "bye"]
    assert is_exit("plaintiff exit", ex) and is_exit("exit", ex) and is_exit("bye", ex)
    assert not is_exit("how do i exit a vim session", ex) and not is_exit("where is the exit", ex)  # 4+ words: a real question


def test_chat_echo_is_cut():
    assert cut_role_echo("I am ABLE. User: and you? ABLE: fine") == "I am ABLE."
    assert cut_role_echo("My name is ABLE, nice to meet you.") == "My name is ABLE, nice to meet you."
    toks = ["Sure", "!", " Here", " it", " is", ".", " Us", "er", ":", " next", " ABLE", ":", " x"]
    assert "".join(stop_at_role_echo(iter(toks))) == "Sure! Here it is."
    assert "".join(stop_at_role_echo(iter(["A", " cat", " is", " Use", "ful", "."]))) == "A cat is Useful."


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
