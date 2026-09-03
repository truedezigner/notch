import asyncio
import unittest

from notch.change_feed import ChangeFeed


class IOSChangeFeedTests(unittest.IsolatedAsyncioTestCase):
    async def test_waiter_wakes_immediately_after_publish(self):
        feed = ChangeFeed()
        revision = await feed.current()
        waiter = asyncio.create_task(feed.wait(revision, 2.0))
        await asyncio.sleep(0)
        published = await feed.publish()
        observed, changed = await asyncio.wait_for(waiter, timeout=0.5)
        self.assertTrue(changed)
        self.assertEqual(observed, published)

    async def test_stale_revision_returns_without_waiting(self):
        feed = ChangeFeed()
        observed, changed = await feed.wait(0, 2.0)
        self.assertTrue(changed)
        self.assertEqual(observed, await feed.current())

    async def test_timeout_is_a_clean_keepalive(self):
        feed = ChangeFeed()
        revision = await feed.current()
        observed, changed = await feed.wait(revision, 0.01)
        self.assertFalse(changed)
        self.assertEqual(observed, revision)


if __name__ == "__main__":
    unittest.main()
