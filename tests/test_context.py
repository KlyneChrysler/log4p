from log4p import MDC, NDC


def test_mdc_put_get_remove():
    MDC.clear()
    MDC.put("req", "r-1")
    assert MDC.get("req") == "r-1"
    assert MDC.get("missing", "dflt") == "dflt"
    assert MDC.getCopy() == {"req": "r-1"}
    MDC.remove("req")
    assert MDC.get("req") is None
    assert MDC.getCopy() == {}


def test_mdc_is_isolated_per_thread():
    import threading

    MDC.clear()
    MDC.put("who", "main")
    seen = {}

    def worker():
        seen["before"] = MDC.get("who")
        MDC.put("who", "worker")
        seen["after"] = MDC.get("who")

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert seen["before"] is None
    assert seen["after"] == "worker"
    assert MDC.get("who") == "main"


def test_ndc_stack():
    NDC.clear()
    assert NDC.get() == ""
    NDC.push("outer")
    NDC.push("inner")
    assert NDC.peek() == "inner"
    assert NDC.getDepth() == 2
    assert NDC.get() == "outer inner"
    assert NDC.pop() == "inner"
    assert NDC.getDepth() == 1
    NDC.clear()
    assert NDC.pop() is None


def test_mdc_put_all_and_queries():
    MDC.clear()
    MDC.putAll({"a": 1, "b": 2})
    assert MDC.getCopy() == {"a": 1, "b": 2}
    MDC.putAll({"b": 3, "c": 4})
    assert MDC.getCopy() == {"a": 1, "b": 3, "c": 4}
    assert MDC.containsKey("a")
    assert not MDC.containsKey("z")
    assert not MDC.isEmpty()
    MDC.clear()
    assert MDC.isEmpty()
    assert MDC.getContext() == {}
    assert MDC.getImmutableContext() == {}


def test_mdc_set_context_replaces():
    MDC.clear()
    MDC.put("old", "x")
    MDC.setContext({"new": "y"})
    assert MDC.getCopy() == {"new": "y"}
    MDC.setContext({})
    assert MDC.isEmpty()


def test_ndc_helpers():
    NDC.clear()
    assert NDC.isEmpty()
    NDC.push("a")
    NDC.push("b")
    assert NDC.getStack() == ["a", "b"]
    assert not NDC.isEmpty()
    assert NDC.remove() == "b"
    NDC.clear()
    assert NDC.isEmpty()
