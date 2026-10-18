"""Try harder: run the last dictation again, more carefully.

Dictate with a fast model as usual; if a word came out wrong, press the Try
harder key within REDO_WINDOW_SEC and the same recording is transcribed
again, and only the part that changed is retyped. The recording is kept in
memory for that window only and never written to disk.

"Again" means a bigger model when one is allowed and already downloaded
(free: Small; Pro: Large turbo, Large or Medium). When there is none, for
example someone already on Large turbo, the model in use runs again in
careful mode: live dictation uses quick greedy decoding for speed, a redo
weighs several candidate sentences (beam search). Either way pressing the
key never starts a download and never dead-ends.
"""

from __future__ import annotations

# How long after a dictation it can still be redone, in seconds.
REDO_WINDOW_SEC = 120
# Pressing the key later than that, but within this long, explains why
# nothing happens instead of failing silently.
LATE_HINT_SEC = 600
# The first few "Typed" pills mention the key, so people find the feature.
TYPED_HINT_COUNT = 5

DEFAULT_REDO_HOTKEY = "f8"

# Beam size for a redo; live dictation uses 1.
CAREFUL_BEAM_SIZE = 5

# Smallest to biggest.
_SIZE_ORDER = ["tiny", "base", "small", "medium", "large-v3-turbo", "large"]
FREE_REDO_SIZES = {"small"}
# Best first: Large turbo is nearly as accurate as Large and much quicker.
_PREFERENCE = ["large-v3-turbo", "large", "medium", "small"]


def pick_redo_model(current: str, is_pro: bool, downloaded: set[str]) -> tuple[str, bool]:
    """(model size, bigger) for a redo.

    `bigger` is True when a bigger, allowed, already downloaded model was
    found; False means: run the current model again in careful mode.
    """
    rank = {size: i for i, size in enumerate(_SIZE_ORDER)}
    current_rank = rank.get(current, 0)
    for size in _PREFERENCE:
        if (
            rank[size] > current_rank
            and (is_pro or size in FREE_REDO_SIZES)
            and size in downloaded
        ):
            return size, True
    return current, False
