"""Order helpers (miner fixture)."""

import asyncio
import functools


def total_price(items):
    """Sum of doubled prices for expensive items."""
    total = 0
    for item in items:
        if item.price > 100:
            total += item.price * 2
    return total


@functools.lru_cache(maxsize=None)
def cached_total(goods):
    # same code as total_price, different names, decorated
    acc = 0
    for g in goods:
        if g.price > 100:
            acc += g.price * 2
    return acc


class Cart:
    def total(self, items):
        total = 0
        for item in items:
            if item.price > self.threshold:
                total += item.price * 2
        return total

    @staticmethod
    def describe(items):
        def label(item):
            name = item.name.strip().title()
            return f"{name}: {item.price:.2f} EUR"

        return [label(i) for i in items]


async def fetch_all(urls, client):
    results = []
    for url in urls:
        response = await client.get(url, timeout=10)
        results.append(response.status_code)
    await asyncio.sleep(0)
    return results
