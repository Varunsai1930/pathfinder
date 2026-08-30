"""Sanitization for untrusted free text before it reaches storage or an LLM prompt.

The student's goal text is data, never instructions: it is quoted in prompts and
echoed verbatim by the deterministic fallback, so anything instruction-shaped
inside it must be neutralized at the boundary, not by asking the model nicely.
"""

from __future__ import annotations

import re
import unicodedata

_MAX_LEN = 2000

# Instruction-shaped phrases that must never survive into a prompt or a quote.
_INJECTION_RE = re.compile(
    "|".join(
        (
            r"ignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?|messages?)",
            r"disregard\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|foregoing)\s+(?:instructions?|prompts?|rules?|messages?)",
            r"disregard\s+(?:all|everything)\s+(?:that\s+was\s+)?above\b",
            r"forget\s+(?:(?:all|any|your|everything)\s+)*(?:instructions?|prompts?|rules?)",
            r"\byou\s+are\s+now\b",
            r"\bnew\s+instructions?\s*:",
            r"\bsystem\s*prompt\b",
            r"</?\s*(?:system|assistant|developer)\s*>",
            r"\bdeveloper\s+mode\b",
            r"\bprint\s+(?:your|the)\s+(?:instructions?|prompts?|rules?)\b",
            r"\breveal\s+your\s+(?:instructions?|prompts?|rules?)\b",
        )
    ),
    re.IGNORECASE,
)

# Control characters (except \n and \t) and invisible/bidi characters that could
# smuggle tokens past a human review.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INVISIBLE_RE = re.compile(r"[\u200b-\u200f\u2028\u2029\u202a-\u202e]")


def sanitize_untrusted_text(text: str | None, max_length: int = _MAX_LEN) -> str | None:
    """Return ``text`` with injection patterns redacted and control chars stripped.

    ``None`` passes through untouched (goal text is optional). Redacted content
    is replaced with a visible ``[redacted]`` marker rather than silently
    dropped, so the student can see their text was modified.

    Normalization order matters:
      1. NFKC folds compatibility homoglyphs (fullwidth "ｉｇｎｏｒｅ", ligatures)
         onto their ASCII forms before any pattern is applied. (Pure
         cross-script look-alikes — e.g. Cyrillic і for Latin i — are NOT
         covered by NFKC; they remain a known limitation.)
      2. Invisible characters are handled two ways, both BEFORE matching:
         stripped (catches keywords split by a zero-width char, like
         "ig\\u200bnore") and substituted with a space (catches words fused by
         an invisible separator, like "disregard\\u200ball previous"). The
         variant that matches is the one that gets redacted.
    """
    if not text:
        return None
    cleaned = unicodedata.normalize("NFKC", text)
    compact = _CONTROL_RE.sub(" ", _INVISIBLE_RE.sub("", cleaned))
    spaced = _CONTROL_RE.sub(" ", _INVISIBLE_RE.sub(" ", cleaned))
    if _INJECTION_RE.search(compact):
        cleaned = _INJECTION_RE.sub("[redacted]", compact)
    elif _INJECTION_RE.search(spaced):
        cleaned = _INJECTION_RE.sub("[redacted]", spaced)
    else:
        cleaned = compact
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = cleaned.strip()[:max_length]
    return cleaned or None
