import asyncio
import time


class TraceStep(asyncio.tasks._PyTask):
    """
    source: I get this function from the import asyncio course by Łukasz Langa at EdgeDB
    """

    def _Task__step(self, exc=None):
        print(f"<step name = {self.get_name()} done = {self.done()}>")
        result = super()._Task__step(exc=exc)
        print(f"</step name = {self.get_name()} done = {self.done()}>")


async def coro2(value: int) -> str:
    print(f"start coro2({value}), doing nothing, just sleep with time.sleep")
    time.sleep(0.5)
    print(f"finish coro2({value}), doing nothing, just sleep with time.sleep")
    return f"coro2 {value}"


async def coro1(count: int = 3) -> list[str]:
    print("start coro1()")
    results = []
    for i in range(count):
        results.append(await coro2(value=i))
    return results


async def tick():
    print("before await asyncio.sleep")
    await asyncio.sleep(2)
    print("after await asyncio.sleep")
    print("Tick!")

async def async_main() -> None:
    print("async main, before await coro1() ")
    asyncio.create_task(tick())
    result = await coro1()
    print(f"async main, after await coro1(), {result = }")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_task_factory(lambda loop, coro: TraceStep(coro, loop=loop))
    loop.run_until_complete(async_main())
    # asyncio.run(async_main())
