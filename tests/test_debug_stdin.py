
def test_check_stdin():
    import sys
    print(f"sys.stdin type: {type(sys.stdin)}")
    print(f"sys.stdin: {sys.stdin}")
    try:
        print(f"sys.stdin.isatty(): {sys.stdin.isatty()}")
    except Exception as exc:  # pragma: no cover - diagnostic
        print(f"sys.stdin.isatty() failed: {exc}")
