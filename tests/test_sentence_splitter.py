"""Run: baselines\\lumo\\.venv\\Scripts\\python.exe tests\\test_sentence_splitter.py   (also works under pytest)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from sentence_splitter import SentenceSplitter, split_sentences

CUT_OFF = "Photosynthesis is how plants make food. It uses sunlight, water and"
LONG = "Well, a rainbow forms when sunlight enters a raindrop and bends as it slows down, then reflects off the back"

CASES = [
    ("Paris is the capital.", ["Paris is the capital."]),
    ("Dr. Smith lives in St. Louis. He is nice.", ["Dr. Smith lives in St. Louis.", "He is nice."]),
    ("It costs 3.5 dollars.", ["It costs 3.5 dollars."]),
    ("Wait... really? Yes!", ["Wait... really?", "Yes!"]),
    ("no punctuation at all here", ["no punctuation at all here"]),
    ("", []),
    (CUT_OFF, ["Photosynthesis is how plants make food.", "It uses sunlight, water and"]),  # cut by max_tokens
    ("Mr. and Mrs. Lee like cats, dogs, etc. and birds. Cats vs. dogs? Both!",
     ["Mr. and Mrs. Lee like cats, dogs, etc. and birds.", "Cats vs. dogs?", "Both!"]),
    ("1. Sleep well. 2. Take breaks. It was 1999. Then 3.", ["1. Sleep well.", "2. Take breaks.", "It was 1999.", "Then 3."]),
]


def streamed(text, step, **kw):
    s, out = SentenceSplitter(**kw), []
    for i in range(0, len(text), step):
        out += s.feed(text[i:i + step])
    return out + s.flush()


def test_cases_whole_and_streamed():
    for text, want in CASES:
        assert split_sentences(text) == want, (text, split_sentences(text))
        for step in (1, 3, 7):  # token boundaries must not change the result
            assert streamed(text, step) == want, (text, step, streamed(text, step))


def test_sentence_is_emitted_before_the_reply_ends():
    s = SentenceSplitter()
    assert s.feed("Paris is the capital.") == []  # the end is not known until whitespace follows
    assert s.feed(" It") == ["Paris is the capital."]


def test_long_first_sentence_is_cut_at_a_comma():
    got = streamed(LONG, 1, max_first_chunk_words=12)
    assert got[0] == "Well, a rainbow forms when sunlight enters a raindrop and bends as it slows down,", got
    assert " ".join(got) == LONG
    assert split_sentences(LONG, max_first_chunk_words=99) == [LONG]


def test_only_the_first_chunk_is_cut_early():
    text = "Hi. " + LONG
    assert split_sentences(text) == ["Hi.", LONG]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
