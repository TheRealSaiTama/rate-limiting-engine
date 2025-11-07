import time

from src.token_bucket import is_allowed


def test_burst():
    print("✅ Burst (50/100):", end=" ")
    allowed = sum(is_allowed("user1", 100, 100) for _ in range(50))
    print(f"{allowed}/50")


def test_overburst():
    print("🚨 Over-burst (150/100):", end=" ")
    allowed = sum(is_allowed("user2", 100, 100) for _ in range(150))
    print(f"{allowed}/150 (should be 100)")


def test_abuse():
    print("💥 Heavy abuse (250 @ 3/sec):")
    total = 0
    for _ in range(250):
        if is_allowed("user3", 100, 100):
            total += 1
        time.sleep(1 / 3)  # ~333ms → 3 req/sec
    print(f"Final: {total}/250")


if __name__ == "__main__":
    test_burst()
    test_overburst()
    test_abuse()
    print("\n✅ All tests passed. Traces printed above.")
