"""Independent FP64 impulse sums; no streaming recurrence is used here."""
import numpy as np


def direct_moments(times: np.ndarray, writes: np.ndarray, rates: np.ndarray,
                   T: float) -> tuple[np.ndarray, np.ndarray]:
    """Return Z,H shaped [J,*writes.shape[1:]] for writes [N,...].

    Caller supplies augmented writes (including the normalization column).
    This diagnostic intentionally materializes temporal weights for direct sums.
    """
    times, writes, rates = (np.asarray(x, dtype=np.float64) for x in (times, writes, rates))
    if times.ndim != 1 or writes.ndim < 2 or writes.shape[0] != len(times):
        raise ValueError('times [N] and writes [N,...] required')
    if rates.ndim != 1 or not rates.size or np.any(rates <= 0):
        raise ValueError('rates must be positive [J]')
    if not all(np.isfinite(x).all() for x in (times, writes, rates)) or not np.isfinite(T):
        raise ValueError('finite inputs required')
    if np.any(times > T) or np.any(np.diff(times) < 0):
        raise ValueError('times must be ordered and at/before T')
    with np.errstate(over='ignore'):
        d = rates[:, None] * (T - times[None, :])
    weight = np.exp(-d)
    moment = np.zeros_like(d)
    np.multiply(d, weight, out=moment, where=np.isfinite(d))
    return (np.tensordot(weight, writes, axes=(1, 0)),
            np.tensordot(moment, writes, axes=(1, 0)))
