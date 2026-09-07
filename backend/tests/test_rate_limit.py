import pytest

from backend.app.rate_limit.token_bucket import TokenBucket


@pytest.mark.asyncio
async def test_bucket_allows_up_to_capacity():
    bucket = TokenBucket(capacity=3, refill_per_sec=0.0)
    for _ in range(3):
        allowed, _ = await bucket.try_consume()
        assert allowed
    allowed, retry_after = await bucket.try_consume()
    assert not allowed
    assert retry_after > 0


@pytest.mark.asyncio
async def test_bucket_refills_over_time():
    bucket = TokenBucket(capacity=1, refill_per_sec=1000.0)  # fast refill for test speed
    allowed, _ = await bucket.try_consume()
    assert allowed
    import asyncio

    await asyncio.sleep(0.01)
    allowed, _ = await bucket.try_consume()
    assert allowed
