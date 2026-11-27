"""Deterministic hashing primitives.

Colours must be comparable *across* graphs (observed window vs. reference template vs. another
organisation's graph), so we never use Python's salted ``hash``. Multisets are hashed additively
(sum of item hashes mod 2^64): order independent and O(1) to update when an item is added or
removed, which is what makes incremental refinement cheap.
"""

import hashlib
import math

MASK = (1 << 64) - 1


def h64(*parts) -> int:
    m = hashlib.blake2b(digest_size=8)
    for p in parts:
        m.update(str(p).encode())
        m.update(b"\x1f")
    return int.from_bytes(m.digest(), "big")


def color_str(c: int) -> str:
    return f"{c:016x}"


def mult_bucket(count: int, mode: str) -> int:
    """Map an item multiplicity to its contribution class.

    exact: every repetition counts; log: 1,2,3-4,5-8,...; set: presence only."""
    if mode == "exact":
        return count
    if mode == "set":
        return 1 if count > 0 else 0
    if count <= 0:
        return 0
    return 1 + int(math.ceil(math.log2(count))) if count > 1 else 1


def item_contribution(item_hash: int, bucket: int) -> int:
    """Contribution of an item seen in multiplicity class ``bucket`` to an additive multiset hash.

    The multiset hash is the sum over *distinct* items of h(item, bucket(count)); in "exact" mode
    bucket == count, so this is a collision-resistant hash of the full multiset."""
    if bucket == 0:
        return 0
    return h64(item_hash, "b", bucket)
