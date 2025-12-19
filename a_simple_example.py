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
[18:34:13] start sequential vod1
[18:34:13] scrooling reel: 0

=== sequential ===
[18:34:13] start sequential vod1

=== concurrent ===
[18:34:13] start concurrent vod1
[18:34:13] start concurrent vod2
[18:34:14] scrooling reel: 1
[18:34:15] scrooling reel: 2
[18:34:16] end   sequential vod1
[18:34:16] start sequential vod2
[18:34:16] end   sequential vod1
[18:34:16] start sequential vod2
[18:34:16] end   concurrent vod1
[18:34:16] end   concurrent vod2
concurrent took 3.00 seconds
[18:34:16] scrooling reel: 3
[18:34:17] scrooling reel: 4
[18:34:18] scrooling reel: 5
[18:34:19] end   sequential vod2
sequential took 6.00 seconds
[18:34:19] end   sequential vod2
sequential took 6.00 seconds
[18:34:19] scrooling reel: 6
[18:34:20] scrooling reel: 7
[18:34:21] scrooling reel: 8
[18:34:22] scrooling reel: 9

=== WITH BLOCKING ===

=== sequential ===
[18:34:23] start sequential vod1
[18:34:23] scrooling reel: 0
[18:34:23] === before blocking_download ===
[18:34:23] vod1: start BLOCKING download
[18:34:28] vod1: end BLOCKING download
[18:34:28] === after blocking_download ===

=== sequential ===
[18:34:28] start sequential vod1

=== concurrent ===
[18:34:28] start concurrent vod1
[18:34:28] start concurrent vod2
[18:34:28] scrooling reel: 1
[18:34:28] end   sequential vod1
[18:34:28] start sequential vod2
[18:34:29] scrooling reel: 2
[18:34:30] scrooling reel: 3
[18:34:31] end   sequential vod1
[18:34:31] start sequential vod2
[18:34:31] end   concurrent vod1
[18:34:31] end   concurrent vod2
concurrent took 3.00 seconds
[18:34:31] end   sequential vod2
sequential took 8.00 seconds
[18:34:31] scrooling reel: 4
[18:34:32] scrooling reel: 5
[18:34:33] scrooling reel: 6
[18:34:34] end   sequential vod2
sequential took 6.00 seconds
[18:34:34] scrooling reel: 7
[18:34:35] scrooling reel: 8
[18:34:36] scrooling reel: 9

=== WITH BLOCKING ===

=== sequential ===
[18:34:37] start sequential vod1
[18:34:37] scrooling reel: 0

=== sequential ===
[18:34:37] start sequential vod1

=== concurrent ===
[18:34:37] === before blocking_download ===
[18:34:37] vod1: start BLOCKING download
[18:34:42] vod1: end BLOCKING download
[18:34:42] === after blocking_download ===
[18:34:42] start concurrent vod1
[18:34:42] start concurrent vod2
[18:34:42] scrooling reel: 1
[18:34:42] end   sequential vod1
[18:34:42] start sequential vod2
[18:34:42] end   sequential vod1
[18:34:42] start sequential vod2
[18:34:43] scrooling reel: 2
[18:34:44] scrooling reel: 3
[18:34:45] end   concurrent vod1
[18:34:45] end   concurrent vod2
[18:34:45] end   sequential vod2
sequential took 8.01 seconds
[18:34:45] end   sequential vod2
sequential took 8.01 seconds
concurrent took 8.01 seconds
[18:34:45] scrooling reel: 4
[18:34:46] scrooling reel: 5
[18:34:47] scrooling reel: 6
[18:34:48] scrooling reel: 7
[18:34:49] scrooling reel: 8
[18:34:50] scrooling reel: 9

=== HANDLE BLOCKING ===

=== sequential ===
[18:34:51] start sequential vod1
[18:34:51] scrooling reel: 0

=== sequential ===
[18:34:51] start sequential vod1

=== concurrent ===
[18:34:51] === before blocking_download ===
[18:34:51] vod1: start BLOCKING download
[18:34:51] start concurrent vod1
[18:34:51] start concurrent vod2
[18:34:52] scrooling reel: 1
[18:34:53] scrooling reel: 2
[18:34:54] end   sequential vod1
[18:34:54] start sequential vod2
[18:34:54] end   sequential vod1
[18:34:54] start sequential vod2
[18:34:54] scrooling reel: 3
[18:34:54] end   concurrent vod1
[18:34:54] end   concurrent vod2
concurrent took 3.01 seconds
[18:34:55] scrooling reel: 4
[18:34:56] scrooling reel: 5
[18:34:56] vod1: end BLOCKING download
[18:34:56] === after blocking_download ===
[18:34:57] end   sequential vod2
sequential took 6.00 seconds
[18:34:57] end   sequential vod2
sequential took 6.00 seconds
[18:34:57] scrooling reel: 6
[18:34:58] scrooling reel: 7
[18:34:59] scrooling reel: 8
[18:35:00] scrooling reel: 9
"""