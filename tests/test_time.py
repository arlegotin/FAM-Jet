"""Time/ownership regressions: padding, continuation and exact represented gaps."""
from dataclasses import replace
import pytest
import numpy as np
import torch
from jet_fixtures import events, queries, chunk, kernel_case


def memory(dtype=torch.float64):
    from famjet.memory.jet import JetMemory
    return JetMemory(torch.tensor([[.05, .5]], dtype=dtype), 3, 2, eps=1e-8, support_floor=1e-12, t_ref=2.)


def test_query_before_snapshot_rejected():
    e = events(); m = memory(); s = m.encode(e)
    with pytest.raises(ValueError, match='before'):
        m.features(s, queries(e, [[7], [7]]))
    with pytest.raises(ValueError, match='before'):
        m.advance_copy(s, 7)


def test_continuation_uses_snapshot_time_and_query_copy():
    e = events(); m = memory(); s = m.encode(chunk(e, 0, 3))
    before = {k: v.clone() for k, v in s.payload.items()}
    m.features(s, queries(e, [[20, 3], [30, 7]]))
    m.advance_copy(s, 40)
    continued = m.encode(chunk(e, 3, 6), s)
    whole = m.encode(e)
    for key in ('z', 'h'):
        torch.testing.assert_close(continued.payload[key], whole.payload[key], rtol=1e-12, atol=1e-12)
    assert all(torch.equal(s.payload[k], v) for k, v in before.items())
    assert continued.last_time.tolist() == [8, 7]
    assert continued.event_offset.tolist() == [6, 4]
    with pytest.raises(ValueError, match='before|order'):
        m.encode(chunk(e, 0, 2), continued)


def test_global_shift_and_units():
    e = events(); m = memory(); f = m.features(m.encode(e), queries(e, [[9], [10]]))
    for factor, offset in [(1, 2**60), (1000, 0)]:
        changed = replace(e, timestamps=e.timestamps * factor + offset, time_unit='scaled')
        from famjet.memory.jet import JetMemory
        other = JetMemory(m.rates / factor, 3, 2, eps=1e-8, support_floor=1e-12, t_ref=2. * factor)
        actual = other.features(other.encode(changed), queries(changed, [[9*factor+offset], [10*factor+offset]]))
        torch.testing.assert_close(actual.values, f.values, rtol=1e-12, atol=1e-12)


def test_mixed_timestamp_domains_and_integer_snapshot_precision():
    e = chunk(events(), 0, 2)
    e.timestamps = torch.tensor([[2**60-2, 2**60-1], [2**60-2, 2**60-1]])
    m = memory(); first = m.encode(chunk(e, 0, 1)); s = m.encode(chunk(e, 1, 2), first)
    assert s.last_time.dtype == torch.int64
    f = m.features(s, queries(e, [[float(2**60)], [float(2**60)]]))
    shifted = replace(e, timestamps=torch.tensor([[0, 1], [0, 1]]))
    expected = m.features(m.encode(shifted), queries(shifted, [[2], [2]]))
    torch.testing.assert_close(f.values, expected.values, rtol=1e-12, atol=1e-12)
    # A float query rounded below an integer snapshot must not pass a float-cast comparison.
    e.timestamps += 2
    with pytest.raises(ValueError, match='before'):
        m.features(m.encode(e), queries(e, [[float(2**60)], [float(2**60)]]))


def test_padding_invariance_and_revalidation():
    e = events(); m = memory(); s = m.encode(e)
    e.timestamps[1, 4:] = -100
    e.values[1, 4:] = 1e10
    padded = m.encode(e)
    torch.testing.assert_close(padded.payload['z'], s.payload['z'])
    torch.testing.assert_close(padded.payload['h'], s.payload['h'])
    e.values[1, 5, 0] = float('nan')
    with pytest.raises(ValueError, match='finite'):
        m.encode(e)


def test_empty_state_and_history_independent_byte_count():
    e = events(); m = memory(); s = m.init_state(2, device='cpu', dtype='float64')
    f = m.features(s, queries(e, [[-1, 100], [0, 5]]))
    assert not f.supported.any()
    assert torch.isfinite(f.values).all()
    assert not f.diagnostics['mean_age'].any()
    expected = sum(v.numel()*v.element_size() for v in s.payload.values()) + sum(v.numel()*v.element_size() for v in (s.last_time, s.valid, s.event_offset)) + 32 + 8
    assert m.persistent_nbytes(s) == expected
    assert m.persistent_nbytes(m.encode(e)) == expected


def test_public_modes_and_invalid_writes():
    e = events(); m = memory()
    streamed = m.encode(e)
    terminal = m.encode(e, mode='terminal')
    torch.testing.assert_close(streamed.payload['z'], terminal.payload['z'], rtol=1e-12, atol=1e-12)
    torch.testing.assert_close(streamed.payload['h'], terminal.payload['h'], rtol=1e-12, atol=1e-12)
    e.normalization = 'independent'; e.observed[0, 0, 0] = False
    with pytest.raises(ValueError, match='shared'):
        m.encode(e)
    e = events(); e.auxiliary['gate'][0, 0] = -1
    with pytest.raises(ValueError):
        m.encode(e)
    with pytest.raises(ValueError):
        m.encode(events(), mode='unknown')


def test_query_padding_does_not_round_fractional_snapshot_time():
    e = events(); e.timestamps = e.timestamps.double() + .5
    m = memory(); s = m.encode(e)
    q = queries(e, [[9, -100], [10, -100]])
    q.present[:, 1] = False; q.lengths[:] = 1
    f = m.features(s, q)
    assert f.supported[:, 0].all()
    assert not f.supported[:, 1].any()


def test_public_device_time_and_read(kernel_case):
    from famjet.memory.jet import JetMemory
    dtype, device, tol = kernel_case
    e = events(dtype, device)
    m = JetMemory(torch.tensor([[.05, .5]], dtype=dtype, device=device), 3, 2, t_ref=2.)
    empty = m.init_state(2, device=device, dtype=str(dtype).removeprefix('torch.'))
    assert not empty.valid.any()
    actual = m.features(m.encode(e), queries(e, [[9, 20], [10, 30]]))
    ref = memory().features(memory().encode(events()), queries(events(), [[9, 20], [10, 30]]))
    torch.testing.assert_close(actual.values.cpu().double(), ref.values, rtol=tol[0], atol=tol[1])
    changed = replace(e, timestamps=e.timestamps*1000, time_unit='scaled')
    other = JetMemory(m.rates/1000, 3, 2, t_ref=2000.)
    scaled = other.features(other.encode(changed), queries(changed, [[9000, 20000], [10000, 30000]]))
    torch.testing.assert_close(actual.values, scaled.values, rtol=tol[0], atol=tol[1])
    shifted = replace(e, timestamps=e.timestamps+2**60)
    shifted_f = m.features(m.encode(shifted), queries(shifted, [[2**60+9, 2**60+20], [2**60+10, 2**60+30]]))
    torch.testing.assert_close(actual.values, shifted_f.values, rtol=tol[0], atol=tol[1])


def test_terminal_continuation_empty_chunk_and_snapshot_rejections():
    e = events(); m = memory(); s = m.encode(chunk(e, 0, 3))
    tail = chunk(e, 3, 6)
    terminal = m.encode(tail, s, mode='terminal')
    stream = m.encode(e)
    for key in ('z', 'h'):
        torch.testing.assert_close(terminal.payload[key], stream.payload[key], rtol=1e-12, atol=1e-12)
        torch.testing.assert_close(m.encode(chunk(e, 6, 6), stream).payload[key], stream.payload[key])
    bad = replace(tail, history_ids=('other', 'b'))
    with pytest.raises(ValueError, match='identity'):
        m.encode(bad, s)
    with pytest.raises(ValueError, match='time_unit'):
        m.encode(replace(tail, time_unit='seconds'), s)
    with torch.no_grad(): m.rates.mul_(2)
    with pytest.raises(ValueError, match='parameter'):
        m.advance_copy(s, 30)


def test_no_observations_advance_known_time_without_mass():
    e = events(); e.observed.zero_(); m = memory(); s = m.encode(e)
    assert s.valid.all() and s.last_time.tolist() == [8, 7]
    assert not s.payload['z'].any() and not s.payload['h'].any()
    f = m.features(s, queries(e, [[9], [10]]))
    assert not f.supported.any() and not f.diagnostics['mean_age'].any()


def test_very_large_finite_host_gap_and_tiny_rate(kernel_case):
    from famjet.memory.jet import JetMemory
    dtype, device, tol = kernel_case
    e = chunk(events(dtype, device), 0, 1)
    e.timestamps = torch.zeros(2, 1, dtype=torch.float64)
    m = JetMemory(torch.tensor([[1e-30]], dtype=dtype, device=device), 3, 2)
    s = m.encode(e); decayed = m.advance_copy(s, 1e40)
    assert not decayed.payload['z'].any() and not decayed.payload['h'].any()
    # Huge float64 gaps must be multiplied before the FP32 cast, not clamped.
    m = JetMemory(torch.tensor([[1e-40]], dtype=dtype), 3, 2)
    cpu_e = chunk(events(dtype), 0, 1); cpu_e.timestamps = torch.zeros(2, 1, dtype=torch.float64)
    s = m.encode(cpu_e); decayed = m.advance_copy(s, 1e40)
    d = float(m.rates.item()) * 1e40
    torch.testing.assert_close(decayed.payload['z'], s.payload['z']*np.exp(-d), rtol=tol[0], atol=tol[1])
