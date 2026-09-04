"""Tests for the batched persistence in the polling base class."""

from typing import override

import pytest

from rpi.lib.polling import PollingService


class _Stub(PollingService[int]):
    def __init__(self) -> None:
        super().__init__(name="stub")
        self.next = 0
        self.published: list[int] = []
        self.persisted: list[list[int]] = []

    @override
    async def initialize(self) -> None: ...
    @override
    async def cleanup(self) -> None: ...

    @override
    async def poll(self) -> int:
        self.next += 1
        return self.next

    @override
    async def audit(self, reading: int) -> bool:
        return True

    @override
    def publish(self, reading: int) -> None:
        self.published.append(reading)

    @override
    async def persist(self, readings: list[int]) -> None:
        self.persisted.append(list(readings))


@pytest.mark.asyncio
async def test_publishes_every_cycle_persists_every_nth_in_batches():
    svc = _Stub()
    svc.persist_every = 2
    svc.flush_interval_sec = 10_000  # never flush on time during the test

    for _ in range(5):
        await svc._poll_cycle()

    assert svc.published == [1, 2, 3, 4, 5]
    assert svc.persisted == []
    assert svc._buffer == [2, 4]

    await svc.flush()
    assert svc.persisted == [[2, 4]]
    assert svc._buffer == []

    await svc.flush()  # empty buffer is a no-op
    assert svc.persisted == [[2, 4]]
