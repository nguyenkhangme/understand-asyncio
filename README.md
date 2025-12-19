---
title: "Understand Concurrency in Python with asyncio: Dig Into the asyncio Source Code"
date: 2025-12-19
categories:
  - normal-ml
  - coding
  - python
tags:
  - english
---

Read this on [my blog](https://nguyenkhang.me/posts/2025/12/understand-concurrency-in-python-with-asyncio-dig-into-the-asyncio-source-code/)

- [1. Some concept](#1-some-concept)
  - [1.1. I/O-bound and CPU-bound](#11-io-bound-and-cpu-bound)
  - [1.2. Sequential execution vs Concurrency vs Parallelism](#12-sequential-execution-vs-concurrency-vs-parallelism)
  - [1.3. Event loop](#13-event-loop)
  - [1.4. Future](#14-future)
  - [1.5. Coroutine](#15-coroutine)
  - [1.6. Task](#16-task)
- [2. How asyncio works under the hood](#2-how-asyncio-works-under-the-hood)
  - [2.1. Await](#21-await)
  - [2.2. Running top-level coroutine](#22-running-top-level-coroutine)
  - [2.3. Connect the dots](#23-connect-the-dots)
  - [2.4. Demonstrate 1](#24-demonstrate-1)
    - [2.4.1. Demonstrate 1 setup](#241-demonstrate-1-setup)
    - [2.4.2. Demonstrate 1 visualization](#242-demonstrate-1-visualization)
    - [2.4.3. Demonstrate 1 explanation](#243-demonstrate-1-explanation)
  - [2.5. Demonstrate 2](#25-demonstrate-2)
    - [2.5.1. Demonstrate 2 setup](#251-demonstrate-2-setup)
    - [2.5.2. Demonstrate 2 visualization](#252-demonstrate-2-visualization)
    - [2.5.3. Demonstrate 2 explanation](#253-demonstrate-2-explanation)
- [3. What's next](#3-whats-next)
- [5. Resources](#5-resources)

*Writing this post dives me into the flow, because it shows how fascinating programming can be. There is no magic, only thoughtfully crafted code.*

If anything is the most important piece of this post, [the section 2.5.2. Demonstrate 2 visualization](#252-demonstrate-2-visualization) will be it.

We will first see some concepts, then answer the following questions by digging into the asyncio source code:

- How event loop schedule and run callbacks under the hood?
- How event loop run one callback at a time and execute many callbacks interleave using coroutines?

By answering those questions, when working with asyncio, we can avoid bugs from the start, debug more easily when something goes wrong, and have the intuition to understand what went wrong and why. This also makes exception handling clearer and maintaining legacy source code much easier. It’s also interesting to understand and see how things are implemented.

This post focuses only on answering those questions, since this topic already contains a lot of information and could be overwhelming if we include other topics, which I will mention what’s next in Section 3.

I wrote this post with Python 3.11. I also glanced at Python 3.14 sometimes for comparison, and will point out the notable difference that I encountered.

For the ease of reading, when mentioning a specific function, I may not show all of its arguments, but only show `function_name()`.

If something you doubt or is unclear, I highly recommend that you `command + click` and check the asyncio source code yourself. If it goes to an abstract method in events.py, you can go to the `base_events.py` file and search for that method there. If it goes to an abstract in `base_events.py`, you can go to `selector_events.py` or `proactor_events.py` to check.

If you want a comprehensive and easy-to-understand guide, I recommend watching this [YouTube tutorial series](https://www.youtube.com/watch?v=Xbl7XjFYsN4&list=PLhNSoGM2ik6SIkVGXWBwerucXjgP1rHmB) by Łukasz Langa, a member of the Python core team.

The demonstration code for this post can be found [here](https://github.com/nguyenkhangme/understand-asyncio).

## 1. Some concept

### 1.1. I/O-bound and CPU-bound

- I/O bound: The task spends most of its time waiting for a result from other devices, such as:
  - Waiting for a database
  - Waiting for HTTP responses
  - Waiting for file reads
- CPU-bound: The task spends most of its time computing:
  - Image processing
  - Chunking and parsing large documents
  - Local ML inference

### 1.2. Sequential execution vs Concurrency vs Parallelism

- Sequential execution:
  - Execute tasks sequentially, where each task completes before the next begins.
  - Example:
    - When cooking, you steam the chicken breast for 45 minutes, and during that time, you are not doing anything, just waiting for it to finish before doing other tasks.
    - From A to B (a straight route), to transport 30 people, a supercar transports one person at a time (except the driver), and does it in 30 trips to finish.
- Concurrency:
  - Concurrency means multiple tasks are in progress (their lifetimes overlap)
  - Note: When searching for the word "concurrency" to confirm my understanding, I found that there are varies understanding and definitions of this term. I guess it's because of the bias of one's own native language, programming language, point of view,...
  - For this post, when I mention concurrency, what I mean is the concurrency that asyncio provides: single-threaded, cooperative concurrency, multiple tasks are in progress, but only one is running at the given moment. This is especially effective for I/O-bound workloads by overlapping waiting periods.
  - Example: While steaming the chicken, you cook the rice, then let the rice cook, and go to wash the tomatoes and cucumber. During this time, the chicken is steamed. You finish washing the cucumber first, then return to take out the chicken breast and slice it before continuing to cut the vegetables.
- Parallelism:
  - Parallelism means multiple tasks execute at the same time (simultaneously).
  - Example:
    - You are breathing and reading this at the same time. (Yes, you just noticed that you are breathing right now, and yeah, you may try to hold your breath as well, and that holding happens in parallel when you read this)
    - From A to B (a straight route), to transport 30 people, a bus transports 30 people at a time and finishes in one trip. Or, 10 supercar transports at a time, and finish after 3 times.

### 1.3. Event loop

- Event loop
  - An event loop **is a loop** that, on each iteration, polls for I/O events via a selector, schedules callbacks associated with those events, schedules due timed callbacks (call_later callbacks), and then runs the ready callbacks.
  - A selector is a system call that monitors multiple file descriptors and returns those that are ready for I/O without blocking.
  - Event loop can only run one callback at a time, but can handle many callbacks and execute them interleave.
  - `loop.call_soon(callback)`: Arrange for a callback to be called as soon as possible.
  - `asyncio.get_event_loop()`: return an asyncio event loop
    - From Python 3.14, if no current event loops are running, call `loop = asyncio.get_event_loop()` will throw a RuntimeError: There is no current event loop in thread. You need to do this instead: `loop = asyncio.new_event_loop()` and then `asyncio.set_event_loop(loop)` to set that loop as the current event loop.

### 1.4. Future

- Future:
  - A future object represents an outcome that may not be available yet (hence the name future). When that outcome becomes known, the future is marked as done and schedules its callbacks. It can do so by some importance methods: set_result(), set_exception(), cancel(), add_done_callback()
  - `done()`:
    - Return True if the future is done.
    - A future is done if a result/exception is available, or if the future was cancelled.
  - `add_done_callback()`:
    - If that future is done, schedule the callback to be called as soon as possible using `loop.call_soon()`
    - If not, add that callback to the `_callbacks` list, which will be scheduled to be called when the future is done
  - How futures are completed.
    - `set_result()`:
      - Mark the future done and set its result.
      - Schedule to call all `_callbacks` as soon as possible.
    - `set_exception()`:
      - Mark the future done and set an exception.
      - Schedule to call all `_callbacks` as soon as possible.
    - `cancel()`:
      - Mark the future done.
      - If the future is already done, return False. Otherwise, change the future's state to cancelled, schedule to call all `_callbacks` as soon as possible, and return True.
  - For example, when waiting for an I/O operation, a future represents the pending outcome. Once the operation finishes, the event loop completes the future by calling `set_result()` or `set_exception()`, marking it as done, and scheduling all registered callbacks.

### 1.5. Coroutine

- Coroutine
  - By saying coroutine, we mean *native coroutine* (introduced in [PEP 492](https://peps.python.org/pep-0492)) that returns from an `async def` function. There are also *generator-based coroutine* (introduced in [PEP 3156](https://peps.python.org/pep-3156/#coroutines-and-the-scheduler)) return from a function decorated with `types.coroutine()`, which is legacy and should not be used at the application level.
  - `async def`: async functions are regular functions. When we call them, we always get back a coroutine, even if they do not contain an `await` expression inside. Calling a coroutine does not start its code running.
  - Coroutines are based on generators internally, but are distinct types.
  - One distinction from generators is that `yield` is not allowed in a coroutine. Using `yield` inside an `async def` function turns it into an asynchronous generator function instead.
  - Knowing couroutines is implemented on top of generators and having this difference is important to understand how couroutines are scheduled and run cooperatively, which is what we will discuss in the section 2 below.
  - To start running a coroutine, we need to call `await coroutine` from an already running coroutine, or convert it to a task (we will see why below in [How asyncio works under the hood](#how-asyncio-works-under-the-hood))

```python
async def detect(): # <- a coroutine function
    ...

detect() # <- a coroutine, or a coroutine object, this is not running yet
print(type(detect)) # <class 'function'>
print(type(detect())) # <class 'coroutine'>
```

We can also run a coroutine as below if it does not await on anything that requires a running event loop. While this is not meaningful in real programs, it is useful for understanding that a coroutine is implemented on top of a generator:

```python
async def coro():
    print("haha")
    return "ok"


try:
    coro().send(None)
except StopIteration as exc:
    print("Finish running the coroutine, return value: ", exc.value)
```

Output:

```text
haha
Finish running the coroutine, return value:  ok
```

### 1.6. Task

- Task
  - Task is a subclass of [Future](#14-future)
  - Taks is "A coroutine wrapped in a Future" - asyncio source code
  - The scheduler that enable coroutine to run concurrently is implemented within Task.
  - Task is commonly created via `asyncio.create_task(coro)`, which internally retrieves the currently running event loop and calls `loop.create_task(coro)`. Hence, with this method, a task can only be created when an event loop is already running, which is reasonable because task initialization schedules its __step() method to run as soon as possible.

## 2. How asyncio works under the hood

### 2.1. Await

- Await is similar to yield from: "It uses the `yield from` implementation with an extra step of validating its argument" - PEP 492
  - Any `yield from` chain of calls ends with a `yield`, or an exception (that is not `StopIteration`), or finishes running and raises StopIteration
- Awaitable object: an object is an awaitable object if it can be used in an await expression.
  - Coroutine, task, future, and any object implementing `__await__()` (custom awaitable) is awaitable
  - We can check whether an object is awaitable or not by using `inspect.isawaitable()`
- Await can await only on an awaitable object.
  - Since `yield` is not allowed in a coroutine, how does the `await` chain calls end, except raising an exception (that is not `StopIteration`), or finishes running and raises `StopIteration`?
  - The answer lay in other awaitable object types:
    - We can `yield` inside `__await__` method of a custom awaitable object, or yield inside a generator-based coroutine `@types.coroutine` function, but we can only yield None or else while running (with task) it will raise an exception, the reason is how task is implemented, discussed below in the section 2.3.
    - Inside Future implementation, we see a `yield self` there. How it works will be discussed more below as well:

```python
    def __await__(self):
        if not self.done():
            self._asyncio_future_blocking = True
            yield self  # This tells Task to wait for completion.
        if not self.done():
            raise RuntimeError("await wasn't used with future")
        return self.result()  # May raise too.
```

### 2.2. Running top-level coroutine

After you already implemented your program with coroutines, we can start running it by calling the following methods, normally only once for the top-level coroutine:

- `asyncio.run()`
  - taking care of managing the asyncio event loop
  - expect to receive a coroutine
  - Wrap coroutine in a task: using `loop.create_task(coro)`
- `loop.run_until_complete()`
  - Awaitable object is required
  - The object will be wrapped using tasks.ensure_future:
    - Custom awaitable objects will be wrapped into a coroutine
    - Coroutines will be wrapped in a task (using `loop.create_task(coro)`)
    - Futures/Tasks will remain themself
- `loop.run_forever()`
  - to run a coroutine with `loop.run_forever()` you need to schedule it by `loop.create_task(coro)`

-> So, whatever way we choose to run, a top-level coroutine is always wrapped into a task when run in the event loop

### 2.3. Connect the dots

- When a task is initiated:
  - It schedule it's `__step()` method to be called as soon as possible using `loop.call_soon(__step)`.
  - Inside `task.__step()`, if the task hasn't done and hasn't had a cancel requested, it gets `result = coro.send(None)` or `result = coro.throw(exc)`. This will run through the `await` chain of calls. As we mentioned above in the 2.1 section, those 2 calls will go back to the `__step()` when:
    - result is a Future
      - result can be a future because inside the future's `__await__` method, it `yield` itself when it is not done. This causes the `await` chain calls to stop at that `yield`, allowing the coroutine to suspend and return the future to `result`. Also, `__step()` checks `_asyncio_future_blocking` attribute to make sure the result is a future yielded by await or yield from.
    - result is `None`: happens when running into bare yield. `await asyncio.sleep(0)` also hits this path because it bare yield internally inside a generator-based coroutine.
    - a `StopIteration` is raised
      - `StopIteration` is raised when the coroutine (of the task) finishes execution. If the coroutine `return some_value`, then `some_value` is carried inside `StopIteration.value`.
    - an Exception:
      - an KeyboardInterrupt / SystemExit
      - a CancelledError
      - a Base Exception: Since this is the exception while running the coroutine and the coroutine does not handle it, we just `set_exception` for the task.
    - result is anything else: `__step()` will schedule itself again with an exception, then in its next call, it will call `coro.throw(exc)`, so that the coroutine can handle this exception by itself and continue running.
    - I also skip some exception handling here
- After suspending the `await` chain call, `__step` handle correspondingly, finish running, and allow the event loop to continue running.
- Specifically, from the user's point of view, the flow will be different based on the object you await:
  - await a coroutine: This will continue running and not return until it reaches something that actually suspends, then it can allow the event loop to continue calling another callback. That something actually suspended is what we discussed above on the `__step()` method.
    - Notice that`return some_value` in a coroutine does not mean it will raise a `StopIteration` back to the __step(). If a coroutine is awaited by another coroutine, the awaiter “catches” the completion instead. If it’s wrapped in a Task, then the Task catches the completion of the coroutine it owns.
  - await a task or future:  if the task/future hasn't done, `__step()` registers `__wakeup()` as a done callback to the future:

```python
result.add_done_callback(self.__wakeup, context=self._context)
```

```python
def __wakeup(self, future):
        try:
            future.result()
        except BaseException as exc:
            # This may also be a cancellation.
            self.__step(exc)
        else:
            # Don't pass the value of `future.result()` explicitly,
            # as `Future.__iter__` and `Future.__await__` don't need it.
            # If we call `_step(value, None)` instead of `_step()`,
            # Python eval loop would use `.send(value)` method call,
            # instead of `__next__()`, which is slower for futures
            # that return non-generator iterators from their `__iter__`.
            self.__step()
        self = None  # Needed to break cycles when an exception occurs.
```

Basically, when that future completes, it schedules `__wakeup()` (which will call `__step()`) to be called again. Then, `__step()` will continue the yield from chain calls to future, go to `__await__` and return `future.result()` to the assigned variable of await and continue running until it reaches something that suspends.

```python
def __await__(self):
    if not self.done():
        self._asyncio_future_blocking = True
        yield self  # <- last yield 
    if not self.done():
        raise RuntimeError("await wasn't used with future")
    return self.result()  # <- go to this and continue running
```

Let's demonstrate the knowledge we just learnt with some coding and visualization.

### 2.4. Demonstrate 1

#### 2.4.1. Demonstrate 1 setup

The first demonstration is somewhat unrealistic when we define two async functions `coro1()` and `coro2()` does nothing related to I/O work, or that function does not await on any futures. But it helps us see how await on a coroutine works as described above, also we have a coroutine function `tick()` wrapped as a task and show some weird behavior (it's weird if we didn't know how it works).

<details>
<summary>Code ([source](https://github.com/nguyenkhangme/understand-asyncio/task_demonstration_1.py)):</summary>

```python
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

```

</details>

<details>
<summary>The output:</summary>

```text
<step name = Task-1 done = False>
async main, before await coro1() 
start coro1()
start coro2(0), doing nothing, just sleep with time.sleep
finish coro2(0), doing nothing, just sleep with time.sleep
start coro2(1), doing nothing, just sleep with time.sleep
finish coro2(1), doing nothing, just sleep with time.sleep
start coro2(2), doing nothing, just sleep with time.sleep
finish coro2(2), doing nothing, just sleep with time.sleep
async main, after await coro1(), result = ['coro2 0', 'coro2 1', 'coro2 2']
</step name = Task-1 done = True>
<step name = Task-2 done = False>
before await asyncio.sleep
</step name = Task-2 done = False>
```

</details>

#### 2.4.2. Demonstrate 1 visualization

![demonstrate 1](/out/demo1/demo1.svg)

#### 2.4.3. Demonstrate 1 explanation

- What we can observe:
  - Task-1 is just run sequentially until done.
  - Task-1 (async_main) is done before Task-2 start to run even Task-2 is created inside `async_main`.
  - Even after `async_main` is finished running, Task-2 is still able to run one step before the program ends.
  - Task-2 does not finish before the program ends.
- Reason:
  - Task-1 never await on something that suspends until it finishes and returns `StopIteration`.
  - Task-2 is created and scheduled to run as soon as possible when the event loop regains control, i.e., in the next iteration of the loop (we will see it in the demo 2 below). Since Task-1 keeps running without yielding back to the event loop, Task-2 must wait until the event loop can take over again, which is when Task-1 is done.
  - When Task-1 is done, it will schedule to run a callback that stops the event loop, since the Task-2 `__step(`) is scheduled before this stop callback, the event loop runs Task-2 `__step()` first.
  - Task-2 run and hit asyncio.sleep, which is a future, hence it releases control back to the event loop to run the ready callback, which is the stop callback. Now the program ends before Task-2 can continue to run

### 2.5. Demonstrate 2

#### 2.5.1. Demonstrate 2 setup

In this demonstrate we use asyncio.gather():

- asyncio.gather(*coros_or_futures, return_exceptions=False):
  - Return a future aggregating results from the given coroutines/futures
  - Awaitable object is required with `tasks._ensure_future(coro_or_future, *, loop=None)`:
    - Coroutines or custom awaitable objects will be wrapped in a task (return `loop.create_task(coro_or_future)`)
    - Futures/Tasks will remain themself
  - In the happy case that no exception or cancellation happens:
    - Each future done will call the callback to notify gather() that one future has been done
    - The last future's on done callback will make the number of futures done == number of futures gather() wait for. Then it will aggregate all the results in order of the original future sequence passed in, and set that result to the return future (this also makes the future done).

<details>
<summary>Code ([source](https://github.com/nguyenkhangme/understand-asyncio/task_demonstration_2.py)):</summary>

```python
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

```

</details>

<details>
<summary>The output:</summary>

```text
<step name=Task-1 done=False>
 [accept_requests] 291561.280 before spawn rq1
 [accept_requests] 291561.280 after spawn rq1
 [accept_requests] 291561.280 before await on loop rq1
</step name=Task-1 done=False>
    <step name=Task-2 done=False>
     [req 1] 291561.280 req 1: enter
     [req 1] 291561.280 Before await spawn db
     [req 1] 291561.280 After await spawn db
     [req 1] 291561.280 Before await spawn fake_http
     [req 1] 291561.280 After await spawn fake_http
     [req 1] 291561.280 Before await gather db_task,fake_http
    </step name=Task-2 done=False>
        <step name=Task-3 done=False>
          291561.280 req 1: db start
        </step name=Task-3 done=False>
        <step name=Task-4 done=False>
          291561.280 req 1: http start
        </step name=Task-4 done=False>
<step name=Task-1 done=False>
 [accept_requests] 291561.332 after await on loop rq1
 [accept_requests] 291561.332 before spawn rq2
 [accept_requests] 291561.332 after spawn rq2
 [accept_requests] 291561.332 before await on loop rq2
</step name=Task-1 done=False>
    <step name=Task-5 done=False>
     [req 2] 291561.332 req 2: enter
     [req 2] 291561.332 Before await spawn db
     [req 2] 291561.332 After await spawn db
     [req 2] 291561.332 Before await spawn fake_http
     [req 2] 291561.332 After await spawn fake_http
     [req 2] 291561.332 Before await gather db_task,fake_http
    </step name=Task-5 done=False>
        <step name=Task-6 done=False>
          291561.332 req 2: db start
        </step name=Task-6 done=False>
        <step name=Task-7 done=False>
          291561.332 req 2: http start
        </step name=Task-7 done=False>
<step name=Task-1 done=False>
 [accept_requests] 291561.383 after await on loop rq2
 [accept_requests] 291561.383 before spawn rq3
 [accept_requests] 291561.383 after spawn rq3
 [accept_requests] 291561.383 before await on loop rq3
</step name=Task-1 done=False>
    <step name=Task-8 done=False>
     [req 3] 291561.383 req 3: enter
     [req 3] 291561.383 Before await spawn db
     [req 3] 291561.383 After await spawn db
     [req 3] 291561.383 Before await spawn fake_http
     [req 3] 291561.383 After await spawn fake_http
     [req 3] 291561.383 Before await gather db_task,fake_http
    </step name=Task-8 done=False>
        <step name=Task-9 done=False>
          291561.383 req 3: db start
        </step name=Task-9 done=False>
        <step name=Task-10 done=False>
          291561.383 req 3: http start
        </step name=Task-10 done=False>
<step name=Task-1 done=False>
 [accept_requests] 291561.434 after await on loop rq3
</step name=Task-1 done=True>
        <step name=Task-3 done=False>
          291564.282 req 1: db done
        </step name=Task-3 done=True>
        <step name=Task-4 done=False>
          291564.282 req 1: http done
        </step name=Task-4 done=True>
    <step name=Task-2 done=False>
     [req 1] 291564.282 After await gather db_task,fake_http
     [req 1] 291564.282 req 1: COMPLETE -> respond
    </step name=Task-2 done=True>
 [server] 291564.282 SEND RESPONSE: {'id': 1, 'a': 'db', 'b': 'http'}
        <step name=Task-6 done=False>
          291564.333 req 2: db done
        </step name=Task-6 done=True>
        <step name=Task-7 done=False>
          291564.333 req 2: http done
        </step name=Task-7 done=True>
    <step name=Task-5 done=False>
     [req 2] 291564.333 After await gather db_task,fake_http
     [req 2] 291564.333 req 2: COMPLETE -> respond
    </step name=Task-5 done=True>
 [server] 291564.333 SEND RESPONSE: {'id': 2, 'a': 'db', 'b': 'http'}
        <step name=Task-9 done=False>
          291564.384 req 3: db done
        </step name=Task-9 done=True>
        <step name=Task-10 done=False>
          291564.384 req 3: http done
        </step name=Task-10 done=True>
    <step name=Task-8 done=False>
     [req 3] 291564.384 After await gather db_task,fake_http
     [req 3] 291564.384 req 3: COMPLETE -> respond
    </step name=Task-8 done=True>
 [server] 291564.384 SEND RESPONSE: {'id': 3, 'a': 'db', 'b': 'http'}

```

</details>

#### 2.5.2. Demonstrate 2 visualization

I found this simple hand drawing is intuitive, and will help to follow the visualization 2 easier :D

![demonstrate 2 simple visualization](/out/demo2/demo2_hand_drawing.png)
![demonstrate 2 detail visualization](/out/demo2/demo2.svg)

#### 2.5.3. Demonstrate 2 explanation

- In this demonstration, we can see:
  - How **task.__step() oschetrate and enable cooperative concurrent with coroutines**: each `__step()` runs a little bit, then it needs to wait for an I/O-like event (in this demo), so it yields control to the event loop to run another `__step()` or callback that is ready. So, callbacks are executed interleaved and have overlapping lifetimes.
  - Without awaiting it, a task will keep running in the background independently of the parent task (as long as the event loop is still running). To get the result of a task (or propagate its exception), we either `await` it or `await asyncio.gather()`, which uses `add_done_callback()`:
    - For await task, the parent task will add_done_callback to wake_up the parent task when the child task is done.
    - For await asynio.gather(), gather() will add_done_callback to all the child tasks. The parent task, again, add_done_callback on the gather future to wake itself up.
    - For Task-1, we add_done_callback to the task by ourselves, and do not await it, so Task-1 is done before its child.
  - **How event loop enable callback to be called** with `loop.call_soon()` inside task init, `loop.call_later()` in `asyncio.sleep()`, and especially with the method `add_done_callback()` of future.

Hence, we answer the question:

- How event loop schedule and run callbacks under the hood?
- How event loop run one callback at a time and execute many callbacks interleave using coroutines?

In this demonstration, we use `asyncio.sleep()` to simulate an I/O wait. Under the hood, it schedules a timer callback that later completes a Future by setting its result to None. When the future is completed, the awaiting task resumes.

In practice, instead of waiting on a timer to set result for the future, file descriptors are monitored by the event loop using `selector.select(timeout)`.

In real I/O operations, instead of waiting on a timer, the event loop waits for operating-system I/O readiness. File descriptors (fds) are registered with the event loop, and the loop blocks inside selector.select(timeout) until the OS reports that an fd is ready for reading or writing. When that happens, the corresponding callback runs and completes the associated awaitable, allowing the task to continue.

## 3. What's next

In this post, I show a lot of methods. This is for teaching purposes only, because it helps us really understand the logic behind the scenes. However, this can also confuse you, since there are too many ways to do one thing.

My next post in this series, hopefully, will help you be less confused by showing how to apply what we learned here to implement a practical asynchronous Python program: [LLM: Asynchronous Tool Calls & Best of N Requests](#) (not sure when I'm free to write again, hope it can be up soon)

I suggest reading about the GIL to understand why asyncio looks like it does today, and why asyncio provides single-threaded, cooperative concurrency.

Also, it's good to check on:

- Asynchronous Context Managers and “async with”
- Asynchronous Iterators and “async for”
- Asynchronous Generator
- Task Cancellation
- Use TaskGroup instead of manual task management
- Exception handling (including ExceptionGroup / except*)
- Timeouts and shielding (asyncio.timeout(), wait_for, shield)
- Queues and backpressure (asyncio.Queue)
- Synchronization primitives: Lock, Event, Semaphore, Condition

Also, you can check [PEP 3148 – futures - execute computations asynchronously](https://peps.python.org/pep-3148/) to learn about the `concurrent.futures` package, which introduces two core classes: Executor and Future (different from `asyncio.Future`). We can use it with `loop.run_in_executor(executor, func, *args)` to run a blocking function in an executor. The executor can be a `ThreadPoolExecutor` (uses a pool of threads) or a `ProcessPoolExecutor` (uses a pool of processes), and the call returns an awaitable that gives you the function’s result.

- The `ProcessPoolExecutor` helps with CPU-bound work by running code in parallel across multiple CPU cores.
- The `ThreadPoolExecutor` helps with blocking I/O code: Not every library is asyncio-native, so you can't await it even if it does I/O. In that case, we can offload the work to another thread and await the result. We can easily do this by calling `asyncio.to_thread()`.

You can also check my simple Python example for a minimal demonstration of how to use asyncio [here](https://github.com/nguyenkhangme/understand-asyncio/blob/main/a_simple_example.py) (I didn’t include it in this post).

<details>
<summary><a href="https://github.com/nguyenkhangme/understand-asyncio/blob/main/a_simple_example.py">a_simple_example.py</a>:</summary>

```python
import asyncio
import time


async def scrooling_reel():
    i = 0
    while i < 10:
        print(f"[{time.strftime('%X')}] scrooling reel: {i}")
        await asyncio.sleep(1)
        i += 1


def blocking_download(name: str):
    print(f"[{time.strftime('%X')}] {name}: start BLOCKING download")
    time.sleep(5)  # blocks the OS thread
    print(f"[{time.strftime('%X')}] {name}: end BLOCKING download")



async def get_learning_resource_blocking():
    print(f"[{time.strftime('%X')}] === before blocking_download ===")
    blocking_download("vod1")  # <- no await here
    print(f"[{time.strftime('%X')}] === after blocking_download ===")


async def handle_get_learning_resource_blocking():
    print(f"[{time.strftime('%X')}] === before blocking_download ===")
    await asyncio.to_thread(blocking_download, "vod1")
    print(f"[{time.strftime('%X')}] === after blocking_download ===")


async def download(name: str, delay: float):
    print(f"[{time.strftime('%X')}] start {name}")
    await asyncio.sleep(delay)
    print(f"[{time.strftime('%X')}] end   {name}")


async def sequential_download():
    print("\n=== sequential ===")
    start = time.perf_counter()

    await download("sequential vod1", 3)
    await download("sequential vod2", 3)

    end = time.perf_counter()
    print(f"sequential took {end - start:.2f} seconds")

async def concurrent_download():
    print("\n=== concurrent ===")
    start = time.perf_counter()

    task1 = asyncio.create_task(download("concurrent vod1", 3))
    task2 = asyncio.create_task(download("concurrent vod2", 3))

    await task1
    await task2

    end = time.perf_counter()
    print(f"concurrent took {end - start:.2f} seconds")

async def main():
    print("\n=== WITHOUT BLOCKING ===")
    await asyncio.gather(
        sequential_download(),
        scrooling_reel(),
        sequential_download(),
        concurrent_download(),
    )

    print("\n=== WITH BLOCKING ===")
    await asyncio.gather(
        sequential_download(),
        scrooling_reel(),
        get_learning_resource_blocking(),
        sequential_download(),
        concurrent_download(),
    )

    print("\n=== WITH BLOCKING ===")
    await asyncio.gather(
        sequential_download(),
        scrooling_reel(),
        sequential_download(),
        concurrent_download(),
        get_learning_resource_blocking(),
    )

    print("\n=== HANDLE BLOCKING ===")
    await asyncio.gather(
        sequential_download(),
        scrooling_reel(),
        sequential_download(),
        concurrent_download(),
        handle_get_learning_resource_blocking(),
    )


if __name__ == "__main__":
    asyncio.run(main())

"""
Output:
=== WITHOUT BLOCKING ===

=== sequential ===
[04:25:32] start sequential vod1
[04:25:32] scrooling reel: 0

=== sequential ===
[04:25:32] start sequential vod1

=== concurrent ===
[04:25:32] start concurrent vod1
[04:25:32] start concurrent vod2
[04:25:33] scrooling reel: 1
[04:25:34] scrooling reel: 2
[04:25:35] end   sequential vod1
[04:25:35] start sequential vod2
[04:25:35] end   sequential vod1
[04:25:35] start sequential vod2
[04:25:35] end   concurrent vod1
[04:25:35] end   concurrent vod2
concurrent took 3.00 seconds
[04:25:35] scrooling reel: 3
[04:25:36] scrooling reel: 4
[04:25:37] scrooling reel: 5
[04:25:38] end   sequential vod2
sequential took 6.00 seconds
[04:25:38] end   sequential vod2
sequential took 6.00 seconds
[04:25:38] scrooling reel: 6
[04:25:39] scrooling reel: 7
[04:25:41] scrooling reel: 8
[04:25:42] scrooling reel: 9

=== WITH BLOCKING ===

=== sequential ===
[04:25:43] start sequential vod1
[04:25:43] scrooling reel: 0
[04:25:43] === before blocking_download ===
[04:25:43] vod1: start BLOCKING download
[04:25:48] vod1: end BLOCKING download
[04:25:48] === after blocking_download ===

=== sequential ===
[04:25:48] start sequential vod1

=== concurrent ===
[04:25:48] start concurrent vod1
[04:25:48] start concurrent vod2
[04:25:48] scrooling reel: 1
[04:25:48] end   sequential vod1
[04:25:48] start sequential vod2
[04:25:49] scrooling reel: 2
[04:25:50] scrooling reel: 3
[04:25:51] end   sequential vod1
[04:25:51] start sequential vod2
[04:25:51] end   concurrent vod1
[04:25:51] end   concurrent vod2
[04:25:51] end   sequential vod2
sequential took 8.00 seconds
concurrent took 3.00 seconds
[04:25:51] scrooling reel: 4
[04:25:52] scrooling reel: 5
[04:25:53] scrooling reel: 6
[04:25:54] end   sequential vod2
sequential took 6.00 seconds
[04:25:54] scrooling reel: 7
[04:25:55] scrooling reel: 8
[04:25:56] scrooling reel: 9

=== WITH BLOCKING ===

=== sequential ===
[04:25:57] start sequential vod1
[04:25:57] scrooling reel: 0

=== sequential ===
[04:25:57] start sequential vod1

=== concurrent ===
[04:25:57] === before blocking_download ===
[04:25:57] vod1: start BLOCKING download
[04:26:02] vod1: end BLOCKING download
[04:26:02] === after blocking_download ===
[04:26:02] start concurrent vod1
[04:26:02] start concurrent vod2
[04:26:02] scrooling reel: 1
[04:26:02] end   sequential vod1
[04:26:02] start sequential vod2
[04:26:02] end   sequential vod1
[04:26:02] start sequential vod2
[04:26:03] scrooling reel: 2
[04:26:04] scrooling reel: 3
[04:26:05] end   concurrent vod1
[04:26:05] end   concurrent vod2
[04:26:05] end   sequential vod2
sequential took 8.01 seconds
[04:26:05] end   sequential vod2
sequential took 8.01 seconds
concurrent took 8.01 seconds
[04:26:05] scrooling reel: 4
[04:26:06] scrooling reel: 5
[04:26:07] scrooling reel: 6
[04:26:08] scrooling reel: 7
[04:26:09] scrooling reel: 8
[04:26:10] scrooling reel: 9
"""
```

</details>

Also, you can check the resources listed below.

## 5. Resources

[Python documentation](https://docs.python.org/3/library/asyncio.html)

[import asyncio YouTube tutorial series](https://www.youtube.com/watch?v=Xbl7XjFYsN4&list=PLhNSoGM2ik6SIkVGXWBwerucXjgP1rHmB)

[PEP 342 – Coroutines via Enhanced Generators](https://peps.python.org/pep-0342/)

[PEP 380 – Syntax for Delegating to a Subgenerator](https://peps.python.org/pep-0380)

[PEP 3156 – Asynchronous IO Support Rebooted: the “asyncio” Module](https://peps.python.org/pep-3156)

[PEP 492 – Coroutines with async and await syntax](https://peps.python.org/pep-0492/#api-design-and-implementation-revisions)

[PEP 3148 – futures - execute computations asynchronously](https://peps.python.org/pep-3148)

[PEP 479 – Change StopIteration handling inside generators](https://peps.python.org/pep-0479/#explanation-of-generators-iterators-and-stopiteration)

[PEP 703 – Making the Global Interpreter Lock Optional in CPython](https://peps.python.org/pep-0703)

[Cooperative vs. Preemptive: a quest to maximize concurrency power](https://medium.com/traveloka-engineering/cooperative-vs-preemptive-a-quest-to-maximize-concurrency-power-3b10c5a920fe)
