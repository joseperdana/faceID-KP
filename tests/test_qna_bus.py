import asyncio

from core import qna_bus


def test_publish_from_worker_thread_reaches_subscriber():
    # Handler `def` berjalan di threadpool; SSE menunggu di event loop.
    async def scenario():
        q = qna_bus.subscribe()
        try:
            await asyncio.to_thread(qna_bus.publish, "questions")
            return await asyncio.wait_for(q.get(), timeout=1)
        finally:
            qna_bus.unsubscribe(q)

    assert asyncio.run(scenario()) == "questions"


def test_unsubscribed_queue_gets_nothing():
    async def scenario():
        q = qna_bus.subscribe()
        qna_bus.unsubscribe(q)
        await asyncio.to_thread(qna_bus.publish, "display")
        await asyncio.sleep(0.05)
        return q.qsize()

    assert asyncio.run(scenario()) == 0


def test_slow_client_is_dropped_not_blocking():
    async def scenario():
        q = qna_bus.subscribe()
        try:
            for _ in range(qna_bus.MAX_QUEUE + 10):
                await asyncio.to_thread(qna_bus.publish, "questions")
            await asyncio.sleep(0.05)
            return q.qsize()
        finally:
            qna_bus.unsubscribe(q)

    assert asyncio.run(scenario()) == qna_bus.MAX_QUEUE


def test_publish_prunes_subscriber_of_closed_loop():
    # Loop yang sudah ditutup (mis. koneksi SSE dari proses tes sebelumnya)
    # tidak boleh membuat publish gagal, dan entrinya harus dibuang.
    async def sub():
        return qna_bus.subscribe()

    q = asyncio.run(sub())  # loop sudah tertutup saat ini kembali
    qna_bus.publish("questions")
    assert all(entry[1] is not q for entry in qna_bus._subscribers)


def test_publish_without_subscribers_is_noop():
    assert not qna_bus._subscribers  # mendeteksi subscriber yang bocor
    qna_bus.publish("settings")
