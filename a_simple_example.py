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