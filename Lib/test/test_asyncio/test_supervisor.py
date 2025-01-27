# Adapted with permission from the EdgeDB project;
# license: PSFL.


import asyncio
import contextvars
import contextlib
from asyncio import supervisor
import unittest


# To prevent a warning "test altered the execution environment"
def tearDownModule():
    asyncio.set_event_loop_policy(None)


class MyExc(Exception):
    pass


class MyBaseExc(BaseException):
    pass


def get_error_types(eg):
    return {type(exc) for exc in eg.exceptions}


class TestSupervisor(unittest.IsolatedAsyncioTestCase):

    async def test_supervisor_01(self):

        async def foo1():
            await asyncio.sleep(0.1)
            return 42

        async def foo2():
            await asyncio.sleep(0.2)
            return 11

        async with supervisor.Supervisor() as g:
            t1 = g.create_task(foo1())
            t2 = g.create_task(foo2())

        self.assertEqual(t1.result(), 42)
        self.assertEqual(t2.result(), 11)

    async def test_supervisor_02(self):

        async def foo1():
            await asyncio.sleep(0.1)
            return 42

        async def foo2():
            await asyncio.sleep(0.2)
            return 11

        async with supervisor.Supervisor() as g:
            t1 = g.create_task(foo1())
            await asyncio.sleep(0.15)
            t2 = g.create_task(foo2())

        self.assertEqual(t1.result(), 42)
        self.assertEqual(t2.result(), 11)

    async def test_supervisor_03(self):

        async def foo1():
            await asyncio.sleep(1)
            return 42

        async def foo2():
            await asyncio.sleep(0.2)
            return 11

        async with supervisor.Supervisor() as g:
            t1 = g.create_task(foo1())
            await asyncio.sleep(0.15)
            # cancel t1 explicitly, i.e. everything should continue
            # working as expected.
            t1.cancel()

            t2 = g.create_task(foo2())

        self.assertTrue(t1.cancelled())
        self.assertEqual(t2.result(), 11)

    async def test_supervisor_04(self):

        NUM = 0
        t2_cancel = False
        t2 = None

        async def foo1():
            await asyncio.sleep(0.1)
            1 / 0

        async def foo2():
            nonlocal NUM, t2_cancel
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                t2_cancel = True
                raise
            NUM += 1

        async def runner():
            nonlocal NUM, t2

            async with supervisor.Supervisor() as g:
                g.create_task(foo1())
                t2 = g.create_task(foo2())

            NUM += 10   # never reached

        with self.assertRaises(ExceptionGroup) as cm:
            await asyncio.create_task(runner())

        self.assertEqual(get_error_types(cm.exception), {ZeroDivisionError})

        self.assertEqual(NUM, 1)    # foo2() is not canceled so, NUM == 1
        self.assertFalse(t2_cancel)
        self.assertFalse(t2.cancelled())
    
    async def test_children_complete_on_child_error(self):

        async def zero_division():
            1 / 0
        
        async def foo1():
            await asyncio.sleep(0.1)
            return 42
        
        async def foo2():
            await asyncio.sleep(0.2)
            return 11
        
        with self.assertRaises(ExceptionGroup) as cm:
            async with supervisor.Supervisor() as g:
                t1 = g.create_task(foo1())
                t2 = g.create_task(foo2())
                g.create_task(zero_division())
        
        self.assertEqual(get_error_types(cm.exception), {ZeroDivisionError})

        self.assertEqual(t1.result(), 42)
        self.assertEqual(t2.result(), 11)

    async def test_children_complete_on_inner_error(self):
        
        async def foo1():
            await asyncio.sleep(0.1)
            return 42
        
        async def foo2():
            await asyncio.sleep(0.2)
            return 11
        
        with self.assertRaises(ExceptionGroup) as cm:
            async with supervisor.Supervisor() as g:
                t1 = g.create_task(foo1())
                t2 = g.create_task(foo2())
                1 / 0

        self.assertEqual(get_error_types(cm.exception), {ZeroDivisionError})

        self.assertEqual(t1.result(), 42)
        self.assertEqual(t2.result(), 11)

    async def test_inner_complete_on_child_error(self):

        async def zero_division():
            1 / 0
        
        async def foo1():
            await asyncio.sleep(0.1)
            return 42
        
        async def foo2():
            await asyncio.sleep(0.2)
            return 11
        
        with self.assertRaises(ExceptionGroup) as cm:
            async with supervisor.Supervisor() as g:
                t1 = g.create_task(foo1())
                g.create_task(zero_division())
                r1 = await foo2()
        
        self.assertEqual(get_error_types(cm.exception), {ZeroDivisionError})

        self.assertEqual(t1.result(), 42)
        self.assertEqual(r1, 11)

    async def test_children_cancel_on_inner_base_error(self):
        
        async def foo1():
            await asyncio.sleep(0.1)
            return 42
        
        async def foo2():
            await asyncio.sleep(0.2)
            return 11
        
        with self.assertRaises(KeyboardInterrupt) as cm:
            async with supervisor.Supervisor() as g:
                t1 = g.create_task(foo1())
                t2 = g.create_task(foo2())
                raise KeyboardInterrupt()

        self.assertTrue(t1.cancelled())
        self.assertTrue(t2.cancelled())


if __name__ == "__main__":
    unittest.main()
