"""Fixes for known Vosk small-model mistakes (stdlib only)."""
import re

# The small model prefers "there" to "where" ("there is the library" for "where is the library").
# Only at the start of an utterance and only before a question verb: "is there ..." stays as it is.
# Known cost: a spoken statement "there is a cat" becomes "where is a cat" (a voice assistant hears questions far more often).
_THERE = re.compile(r"^there(?=\s+(?:is|are|was|were|can|do|does|did|should|would|will)\b)", re.I)


def fix_asr(text):
    return _THERE.sub("where", text)


def is_exit(text, exit_words):
    """An exit word, or a short phrase ending in exit/quit ("plaintiff exit" is how Vosk hears "exit")."""
    words = text.lower().split()
    return text.lower() in exit_words or (0 < len(words) <= 3 and words[-1] in ("exit", "quit"))


def cut_role_echo(text, name="ABLE"):
    """The small LLM sometimes goes on to write the next lines of the chat ("User: ... ABLE: ..."): cut the reply there."""
    m = re.search(rf"\b(?:User|{re.escape(name)})\s*:", text)
    return text[:m.start()].rstrip() if m else text


def stop_at_role_echo(tokens, name="ABLE"):
    """Token stream version of cut_role_echo: ends the stream at the first "User:" / "<name>:" and never speaks a half marker."""
    words, buf, sent = ("User", name), "", 0
    for t in tokens:
        buf += t
        cut = cut_role_echo(buf, name)
        if cut != buf:
            if len(cut) > sent:
                yield cut[sent:]
            return
        raw = re.search(r"\s*\w*\s*$", buf).group()  # trailing word (with its spaces) that may still turn into "User" / the name
        hold = len(raw) if raw.strip() and any(w.startswith(raw.strip()) for w in words) else 0
        if len(buf) - hold > sent:
            yield buf[sent:len(buf) - hold]
            sent = len(buf) - hold
    if len(buf) > sent:
        yield buf[sent:]


def is_confident(result, min_conf):
    """result: parsed Vosk JSON (needs rec.SetWords(True)). False if the mean word confidence is below min_conf (noise / TV gibberish)."""
    words = result.get("result") or []
    return not min_conf or not words or sum(w.get("conf", 1.0) for w in words) / len(words) >= min_conf
