try:
    import gc
except ImportError:
    gc = None

import time

try:
    from collections import deque as _deque
except ImportError:
    try:
        from ucollections import deque as _deque
    except ImportError:
        _deque = None


def ticks_us():
    if hasattr(time, "ticks_us"):
        return time.ticks_us()
    return time.perf_counter_ns() // 1000


def ticks_diff(end, start):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(end, start)
    return end - start


class ListQueue:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)

    def put_head(self, item):
        self.items.insert(0, item)

    def get_nowait(self):
        if self.items:
            return self.items.pop(0)
        return None

    def clear(self):
        self.items = []


class TwoListQueue:
    def __init__(self):
        self._front = []
        self._back = []

    def _rebalance(self):
        if not self._front and self._back:
            self._front = self._back[::-1]
            self._back = []

    def put(self, item):
        self._back.append(item)

    def put_head(self, item):
        self._front.append(item)

    def get_nowait(self):
        if self._front:
            return self._front.pop()
        self._rebalance()
        if self._front:
            return self._front.pop()
        return None

    def clear(self):
        self._front = []
        self._back = []


class RingQueue:
    def __init__(self, capacity):
        self.capacity = capacity
        self.buf = [None] * capacity
        self.head = 0
        self.tail = 0
        self.size = 0

    def put(self, item):
        if self.size >= self.capacity:
            raise OverflowError("ring queue full")
        self.buf[self.tail] = item
        self.tail = (self.tail + 1) % self.capacity
        self.size += 1

    def put_head(self, item):
        if self.size >= self.capacity:
            raise OverflowError("ring queue full")
        self.head = (self.head - 1) % self.capacity
        self.buf[self.head] = item
        self.size += 1

    def get_nowait(self):
        if self.size == 0:
            return None
        item = self.buf[self.head]
        self.buf[self.head] = None
        self.head = (self.head + 1) % self.capacity
        self.size -= 1
        return item

    def clear(self):
        self.buf = [None] * self.capacity
        self.head = 0
        self.tail = 0
        self.size = 0


class DequeQueue:
    def __init__(self, capacity):
        if _deque is None:
            raise RuntimeError("deque not available")
        self.capacity = capacity
        self.items = self._new_deque()

    def _new_deque(self):
        try:
            return _deque(())
        except TypeError:
            pass

        try:
            return _deque((), self.capacity)
        except TypeError:
            pass

        try:
            return _deque((), self.capacity, 1)
        except TypeError:
            pass

        raise TypeError("unsupported deque constructor signature")

    def put(self, item):
        self.items.append(item)

    def put_head(self, item):
        appendleft = getattr(self.items, "appendleft", None)
        if appendleft is None:
            raise AttributeError("deque.appendleft not available")
        appendleft(item)

    def get_nowait(self):
        popleft = getattr(self.items, "popleft", None)
        if popleft is None:
            raise AttributeError("deque.popleft not available")
        try:
            return popleft()
        except (IndexError, RuntimeError):
            return None

    def clear(self):
        clear = getattr(self.items, "clear", None)
        if clear is not None:
            clear()
        else:
            self.items = self._new_deque()


def bench_case(name, factory, count, rounds=3):
    best_us = None

    for _ in range(rounds):
        if gc is not None:
            gc.collect()

        q = factory()
        start = ticks_us()

        for i in range(count):
            q.put(i)

        for _ in range(count):
            q.get_nowait()

        elapsed = ticks_diff(ticks_us(), start)
        if best_us is None or elapsed < best_us:
            best_us = elapsed

    ops = count * 2
    return {
        "name": name,
        "count": count,
        "ops": ops,
        "best_us": best_us,
        "us_per_op": best_us / ops if ops else 0,
    }


def print_result(result, baseline=None):
    line = (
        "{name:<12} count={count:<6} best={best_us:>8} us  "
        "{us_per_op:>8.3f} us/op"
    ).format(**result)

    if baseline and result["best_us"]:
        speedup = baseline["best_us"] / result["best_us"]
        line += "  speedup={:.2f}x".format(speedup)

    print(line)


def run_suite(counts=(16, 64, 256, 1024, 4096), rounds=5):
    print("Queue benchmark: put + get")
    print("Focus: steady FIFO path")
    print("Current EventQueue ~= TwoListQueue")
    print("deque available: {}".format("yes" if _deque is not None else "no"))
    print("")

    for count in counts:
        results = []
        results.append(bench_case("list", ListQueue, count, rounds))
        results.append(bench_case("two-list", TwoListQueue, count, rounds))
        if _deque is not None:
            results.append(
                bench_case(
                    "deque",
                    lambda count=count: DequeQueue(max(8, count + 1)),
                    count,
                    rounds,
                )
            )
        results.append(
            bench_case(
                "ring",
                lambda count=count: RingQueue(max(8, count + 1)),
                count,
                rounds,
            )
        )

        baseline = results[0]
        for result in results:
            print_result(result, baseline if result["name"] != "list" else None)
        print("")


if __name__ == "__main__":
    run_suite()
