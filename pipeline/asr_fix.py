"""Fixes for known Vosk small-model mistakes (stdlib only)."""
import re

# The small model prefers "there" to "where" ("there is the library" for "where is the library").
# Only at the start of an utterance and only before a question verb: "is there ..." stays as it is.
# Known cost: a spoken statement "there is a cat" becomes "where is a cat" (a voice assistant hears questions far more often).
_THERE = re.compile(r"^there(?=\s+(?:is|are|was|were|can|do|does|did|should|would|will)\b)", re.I)


def fix_asr(text):
    return _THERE.sub("where", text)
