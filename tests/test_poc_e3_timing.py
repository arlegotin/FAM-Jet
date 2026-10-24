import pytest


class _Clock:
    def __init__(self):
        self.value = 0.

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def test_fake_clock_separates_preprocessing_ingest_and_read():
    from famjet_poc.timing import timed_pipeline

    clock = _Clock()
    result = timed_pipeline(lambda: clock.advance(2), lambda: clock.advance(3),
                            lambda: clock.advance(5), clock=clock)
    assert result == {'preprocessing_seconds': 2., 'ingest_seconds': 3.,
                      'read_output_seconds': 5., 'complete_seconds': 10.}


def test_break_even_requires_accuracy_and_positive_read_saving():
    from famjet_poc.timing import break_even_queries

    assert break_even_queries(10., 3., 1., accuracy_satisfied=True) == 5
    assert break_even_queries(10., 1., 3., accuracy_satisfied=True) is None
    assert break_even_queries(10., 3., 1., accuracy_satisfied=False) is None
    with pytest.raises(ValueError):
        break_even_queries(-1., 3., 1., accuracy_satisfied=True)


def test_fake_clock_single_event_latency_is_separate_from_chunk_throughput():
    from famjet_poc.timing import measure_one_event

    clock = _Clock()
    assert measure_one_event(lambda: clock.advance(0.25), clock=clock) == 0.25
    assert clock.value == 0.25
