"""Tests for SingleFlight request coalescing."""
import asyncio
import pytest
from app.services.single_flight import SingleFlight


@pytest.mark.asyncio
async def test_single_flight_coalesces_concurrent_calls():
    """Verify that multiple concurrent calls to the same key execute only once."""
    sf = SingleFlight()
    execution_count = 0

    async def slow_operation():
        nonlocal execution_count
        execution_count += 1
        await asyncio.sleep(0.05)
        return "result_value"

    # Launch 10 concurrent tasks for the same key
    results = await asyncio.gather(*[
        sf.execute("shared_key", slow_operation)
        for _ in range(10)
    ])

    # Assert all 10 tasks received the exact same result
    assert len(results) == 10
    assert all(r == "result_value" for r in results)
    # Crucial: underlying function was only called once!
    assert execution_count == 1


@pytest.mark.asyncio
async def test_single_flight_independent_keys():
    """Verify that different keys execute independently."""
    sf = SingleFlight()
    executed_keys = []

    async def work(key: str):
        executed_keys.append(key)
        await asyncio.sleep(0.02)
        return f"result_{key}"

    results = await asyncio.gather(
        sf.execute("key_a", lambda: work("key_a")),
        sf.execute("key_b", lambda: work("key_b")),
        sf.execute("key_c", lambda: work("key_c")),
    )

    assert results == ["result_key_a", "result_key_b", "result_key_c"]
    assert sorted(executed_keys) == ["key_a", "key_b", "key_c"]


@pytest.mark.asyncio
async def test_single_flight_propagates_exceptions():
    """Verify that if the leader raises an exception, all waiting callers receive it."""
    sf = SingleFlight()
    execution_count = 0

    async def failing_operation():
        nonlocal execution_count
        execution_count += 1
        await asyncio.sleep(0.02)
        raise ValueError("Upstream failure")

    # Run 5 concurrent callers
    results = await asyncio.gather(
        *[sf.execute("fail_key", failing_operation) for _ in range(5)],
        return_exceptions=True,
    )

    assert len(results) == 5
    assert execution_count == 1
    for r in results:
        assert isinstance(r, ValueError)
        assert str(r) == "Upstream failure"


@pytest.mark.asyncio
async def test_single_flight_cleans_up_after_completion():
    """Verify that subsequent calls after a key completes execute a fresh invocation."""
    sf = SingleFlight()
    execution_count = 0

    async def operation():
        nonlocal execution_count
        execution_count += 1
        return execution_count

    first = await sf.execute("test_key", operation)
    assert first == 1
    assert execution_count == 1

    second = await sf.execute("test_key", operation)
    assert second == 2
    assert execution_count == 2

