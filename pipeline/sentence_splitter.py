"""Incremental sentence splitter for streamed LLM tokens (stdlib only).

feed(token) returns the sentences completed so far; flush() returns whatever is left at end of reply.
A sentence ends at . ! or ? followed by whitespace (end of text is only known at flush()).
Not a sentence end: abbreviations (Dr. St. etc.), single-letter initials (e.g. / J. K.), ellipses (...).
Decimals (3.5) never match because the dot is not followed by whitespace.
"""
import re

ABBREVIATIONS = {"dr", "mr", "mrs", "ms", "st", "vs", "etc", "prof", "sr", "jr"}
MIN_CHUNK_WORDS = 3
_END =re.compile(r"""([.!?]+)["')\]]*(?=\s)""")
_SOFT = re.compile(r"[,;](?=\s)")


class SentenceSplitter:
    def __init__(self, max_first_chunk_words=12):
        self.max_first_chunk_words = max_first_chunk_words
        self.buf = ""
        self.emitted = 0

    def _is_end(self, m):
        punct = m.group(1)
        if punct != ".":
            return set(punct) != {"."}  # "..." is a pause, "?!" is an end
        if self.buf[:m.start()].strip().isdigit():
            return False  # list marker: "1. Break down ..."
        word = re.search(r"(\w+)$", self.buf[:m.start()])
        if not word:
            return True
        w = word.group(1)
        return not (w.lower() in ABBREVIATIONS or (len(w) == 1 and w.isalpha() and w != "I"))

    def _cut(self, end, out):
        piece, self.buf = self.buf[:end].strip(), self.buf[end:]
        if piece:
            out.append(piece)
            self.emitted += 1

    def feed(self, text):
        self.buf += text
        out, pos = [], 0
        while m := _END.search(self.buf, pos):
            if self._is_end(m):
                self._cut(m.end(), out)
                pos = 0
            else:
                pos = m.end()
        # Only the very first chunk of a reply is cut early: it is the one that decides time to first audio.
        if not self.emitted and len(self.buf.split()) > self.max_first_chunk_words:
            for m in _SOFT.finditer(self.buf):
                if len(self.buf[:m.end()].split()) >= MIN_CHUNK_WORDS:  # not worth a Piper start for "Well,"
                    self._cut(m.end(), out)
                    break
        return out

    def flush(self):
        out = self.feed(" ")
        self._cut(len(self.buf), out)
        return out


def split_sentences(text, max_first_chunk_words=12):
    s = SentenceSplitter(max_first_chunk_words)
    return s.feed(text) + s.flush()


def trim_to_sentence(text):
    """A reply cut off by max_tokens ends mid-sentence: drop the unfinished tail. Unchanged if it ends in . ! ? or has no sentence end."""
    text = text.strip()
    if re.search(r"[.!?][\"')\]]*$", text):
        return text
    ends = list(_END.finditer(text + " "))
    return text[:ends[-1].end()].strip() if ends else text
