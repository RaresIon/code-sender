"""Deterministic hashing / noise. Never uses Python's salted hash() or wall clock."""
import math
import zlib

MASK = (1 << 64) - 1


def _ik(v):
    if isinstance(v, str):
        return zlib.crc32(v.encode())
    if isinstance(v, float):
        return int(round(v * 10000)) & MASK
    return int(v) & MASK


def h01(*keys):
    """Stable hash of keys -> float in [0,1)."""
    x = 0x9E3779B97F4A7C15
    for k in keys:
        x = (x ^ _ik(k)) & MASK
        x = (x * 0xBF58476D1CE4E5B9) & MASK
        x ^= x >> 31
        x = (x * 0x94D049BB133111EB) & MASK
        x ^= x >> 29
    return (x & 0xFFFFFF) / float(0x1000000)


def hr(a, b, *keys):
    return a + (b - a) * h01(*keys)


def noise1(t, *keys):
    """Smooth 1D value noise in [-1,1]."""
    i = math.floor(t)
    f = t - i
    u = f * f * (3 - 2 * f)
    a = h01(i, *keys) * 2 - 1
    b = h01(i + 1, *keys) * 2 - 1
    return a + (b - a) * u
