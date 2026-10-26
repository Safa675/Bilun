"""One Turkish text fold for keyword and name matching.

Every module that compares Turkish text (drug, material, lab, branch names, rule keywords, MEDULA
messages) folds it with ``fold_turkish`` and names how far it folds. The folds are not one fold,
because the callers did not fold alike before they shared this helper, and each kept its own:

- ``LOWER`` / ``CASEFOLD``: ``str.lower`` / ``str.casefold`` only. ``İ`` becomes ``i`` plus a
  combining dot (U+0307) and ``I`` becomes ``i``.
- ``DOTTED_I``: Turkish lower case (``utils.turkish_lower``), then ``ı`` → ``i``, so ``İ I ı i``
  all read ``i``. ``ç ğ ö ş ü`` and every other accent stay.
- ``ASCII``: ``DOTTED_I`` and ``ç ğ ö ş ü`` → ``c g o s u``. Other accents (``é``) stay.
- ``ACCENTLESS``: ``casefold``, NFKD, every combining mark dropped. ``ş ç ğ ü ö İ é`` lose their
  marks, but the dotless ``ı`` has none and stays ``ı``. NFKD also opens compatibility forms
  (``ﬁ`` → ``fi``, ``²`` → ``2``).
- ``ACCENTLESS_DOTLESS_I``: ``ACCENTLESS`` with ``ı`` → ``i`` before NFKD.

``strip=True`` trims leading and trailing whitespace before folding. The text goes through
``str()`` first, so a caller that read ``None`` as ``""`` passes ``text or ""``.
"""

from __future__ import annotations

import unicodedata
from enum import Enum

from .utils import turkish_lower


class TurkishFold(Enum):
    LOWER = "lower"
    CASEFOLD = "casefold"
    DOTTED_I = "dotted_i"
    ASCII = "ascii"
    ACCENTLESS = "accentless"
    ACCENTLESS_DOTLESS_I = "accentless_dotless_i"


_TURKISH_TO_ASCII = str.maketrans("ıçğöşü", "icgosu")


def _without_marks(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


_FOLDS = {
    TurkishFold.LOWER: str.lower,
    TurkishFold.CASEFOLD: str.casefold,
    TurkishFold.DOTTED_I: lambda text: turkish_lower(text).replace("ı", "i"),
    TurkishFold.ASCII: lambda text: turkish_lower(text).translate(_TURKISH_TO_ASCII),
    TurkishFold.ACCENTLESS: lambda text: _without_marks(text.casefold()),
    TurkishFold.ACCENTLESS_DOTLESS_I: lambda text: _without_marks(text.casefold().replace("ı", "i")),
}


def fold_turkish(text: object, how: TurkishFold, *, strip: bool = False) -> str:
    """``str(text)``, trimmed when ``strip``, folded as ``how`` says (see the module docstring)."""
    value = str(text)
    if strip:
        value = value.strip()
    return _FOLDS[how](value)
