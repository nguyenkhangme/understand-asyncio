import asyncio
import contextvars
import os
import time
from typing import Any, Coroutine, Dict


DEPTH = contextvars.ContextVar("DEPTH", default=1)


def step_indent():
    spaces = 4
    d = DEPTH.get()
    return " " * (spaces * (d - 1))


class TraceStep(asyncio.tasks._PyTask):
    """
    source: I get this function from the import asyncio course by Łukasz Langa at EdgeDB and adjust a bit
    """

    def _Task__step(self, exc=None):
        pad = step_indent()
        print(f"{pad}<step name={self.get_name()} done={self.done()}>")
        try:
            return super()._Task__step(exc)
        finally:
            print(f"{pad}</step name={self.get_name()} done={self.done()}>")


def ts():
    return f"{time.perf_counter():.3f}"


def indent() -> str:
    spaces = 4
    d = DEPTH.get()
    return " " * (spaces * (d - 1))


def log(*parts: Any, prefix: str = "") -> None:
    print(indent(), prefix, ts(), *parts)


async def spawn(
    coro: Coroutine[Any, Any, Any],
    name: str = None
) -> asyncio.Task[Any]:
    parent_depth = DEPTH.get()
    ctx = contextvars.copy_context()
    ctx.run(DEPTH.set, parent_depth + 1)
    return asyncio.create_task(coro, name=name, context=ctx)


async def fake_db(req_id: int) -> str:
    log(f"req {req_id}: db start")
    await asyncio.sleep(3)
    log(f"req {req_id}: db done")
    return "db"


async def fake_http(req_id: int) -> str:
    log(f"req {req_id}: http start")
    await asyncio.sleep(3)
    log(f"req {req_id}: http done")
    return "http"


async def handle_request(req_id: int) -> Dict[str, Any]:
    log(f"req {req_id}: enter", prefix=f"[req {req_id}]")

    log(f"Before await spawn db", prefix=f"[req {req_id}]")
    db_task = await spawn(fake_db(req_id))
    log(f"After await spawn db", prefix=f"[req {req_id}]")

    log(f"Before await spawn fake_http", prefix=f"[req {req_id}]")
    http_task = await spawn(fake_http(req_id))
    log(f"After await spawn fake_http", prefix=f"[req {req_id}]")

    log(f"Before await gather db_task,fake_http", prefix=f"[req {req_id}]")
    a, b = await asyncio.gather(db_task, http_task)
    log(f"After await gather db_task,fake_http", prefix=f"[req {req_id}]")
    
    log(f"req {req_id}: COMPLETE -> respond", prefix=f"[req {req_id}]")
    return {"id": req_id, "a": a, "b": b}


def on_done(task: asyncio.Task[Any]) -> None:
    if task.cancelled():
        log("TASK CANCELLED")
        return
    exc = task.exception()
    if exc:
        log("TASK ERROR:", repr(exc))
        return
    log("SEND RESPONSE:", task.result(), prefix="[server]")


async def accept_requests() -> None:
    for i in range(1, 4):
        log(f"before spawn rq{i}", prefix=f"[accept_requests]")
        t = await spawn(handle_request(i))
        log(f"after spawn rq{i}", prefix=f"[accept_requests]")
        t.add_done_callback(on_done)
        log(f"before await on loop rq{i}", prefix=f"[accept_requests]")
        await asyncio.sleep(0.05)
        log(f"after await on loop rq{i}", prefix=f"[accept_requests]")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.set_task_factory(lambda loop, coro, context=None: TraceStep(coro, loop=loop, context=context))

    ctx = contextvars.copy_context()
    ctx.run(DEPTH.set, 1)
    # loop.run_until_complete(accept_requests())
    loop.create_task(accept_requests(), context=ctx)

    loop.call_later(6, lambda loop: loop.stop(), loop)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("KeyboardInterrupt")
    finally:
        loop.close()
