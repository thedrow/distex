import unittest
import itertools
import asyncio

from distex import Pool, util

loop = util.get_loop()
asyncio.set_event_loop(loop)
loop.set_debug(True)


def exception_handler(loop, context):
    print('Exception:', context)


loop.set_exception_handler(exception_handler)


def f(x):
    return x * 2


def g(x, y, z):
    return x * y - 4 * z


def exc(x):
    raise RuntimeError(x)


async def ait(it):
    for x in it:
        await asyncio.sleep(0.001)
        yield x


class PoolTest(unittest.TestCase):

    def setUp(self):
        self.pool = Pool(1, loop=loop, lazy_create=True)
#         self.pool.set_pickle(2, 0)
        self.reps = 100
        self.x = [i for i in range(self.reps)]
        self.y = [i * i for i in range(self.reps)]
        self.z = [i * 2 for i in range(self.reps)]
        self.xyz = list(zip(self.x, self.y, self.z))

    def tearDown(self):
        self.pool.shutdown()

    def test_run_coro(self):

        async def add(a, b):
            await asyncio.sleep(0.001)
            return a + b

        expected = 8
        actual = self.pool.run(add, 3, 5)
        self.assertEqual(actual, expected)

    def test_run_async(self):

        async def coro():
            tasks = [self.pool.run_async(g, self.x[i], self.y[i],
                    z=self.z[i]) for i in range(self.reps)]
            return await asyncio.gather(*tasks)

        expected = list(map(g, self.x, self.y, self.z))
        actual = loop.run_until_complete(coro())
        self.assertEqual(actual, expected)

    def test_run_async_with_exception(self):
        with self.assertRaises(RuntimeError):
            loop.run_until_complete(
                    self.pool.run_async(exc, 'Deliberatly thrown'))

    def test_run_on_all_async(self):

        def getpid():
            import os
            return os.getpid()

        interference = self.pool.map(f,
                2 * self.x[:self.pool.total_workers() + 1])
        pids = loop.run_until_complete(self.pool.run_on_all_async(getpid))
        self.assertEqual(self.pool.total_workers(), len(set(pids)))
        list(interference)

    def test_submit(self):
        expected = g(10, 9, z=8)
        f = self.pool.submit(g, 10, 9, z=8)
        actual = loop.run_until_complete(asyncio.wrap_future(f))
        self.assertEqual(actual, expected)

    def test_submit_with_exception(self):
        f = self.pool.submit(exc, 'Okay then')
        with self.assertRaises(RuntimeError):
            loop.run_until_complete(asyncio.wrap_future(f))

    def test_ordered_map_1_arg(self):
        expected = list(map(f, self.x))
        actual = list(self.pool.map(f, self.x))
        self.assertSequenceEqual(actual, expected)

    def test_ordered_map_3_arg(self):
        expected = list(map(g, self.x, self.y, self.z))
        actual = list(self.pool.map(g, self.x, self.y, self.z))
        self.assertEqual(actual, expected)

    def test_ordered_starmap(self):
        expected = list(itertools.starmap(g, self.xyz))
        actual = list(self.pool.map(g, self.xyz, star=True))
        self.assertEqual(actual, expected)

    def test_ordered_map_1_arg_chunked(self):
        expected = list(map(f, self.x))
        actual = list(self.pool.map(f, self.x, chunksize=7))
        self.assertEqual(actual, expected)

    def test_ordered_map_3_arg_chunked(self):
        expected = list(map(g, self.x, self.y, self.z))
        actual = list(self.pool.map(g, self.x, self.y, self.z, chunksize=10))
        self.assertEqual(actual, expected)

    def test_ordered_map_async_3_arg(self):

        async def coro():
            return [v async for v in self.pool.map_async(g,
                    self.x, self.y, self.z)]

        expected = list(map(g, self.x, self.y, self.z))
        actual = loop.run_until_complete(coro())
        self.assertEqual(actual, expected)

    def test_ordered_astarmap(self):

        async def coro():
            return [v async for v in self.pool.map_async(g,
                    self.xyz, star=True)]

        expected = list(itertools.starmap(g, self.xyz))
        actual = loop.run_until_complete(coro())
        self.assertEqual(actual, expected)

    def test_ordered_astarmap_async_iterator(self):

        async def coro():
            return [v async for v in self.pool.map_async(g,
                    ait(self.xyz), star=True)]

        expected = list(itertools.starmap(g, self.xyz))
        actual = loop.run_until_complete(coro())
        self.assertEqual(actual, expected)

    def test_ordered_map_sync_async_iterators(self):
        expected = list(itertools.starmap(g, self.xyz))
        actual = list(self.pool.map(g,
                    ait(self.x), ait(self.y), self.z))
        self.assertEqual(actual, expected)

    def test_ordered_map_async__sync_async_iterators_chunked(self):

        async def coro():
            return [v async for v in self.pool.map_async(g,
                    ait(self.x), ait(self.y), self.z, chunksize=10)]

        expected = list(itertools.starmap(g, self.xyz))
        actual = loop.run_until_complete(coro())
        self.assertEqual(actual, expected)

    def test_executor(self):
        expected = g(1, 2, 3)
        loop.set_default_executor(self.pool)
        actual = loop.run_until_complete(
                loop.run_in_executor(None, g, 1, 2, 3))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()