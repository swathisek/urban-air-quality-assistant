import sys
import os

from data import get_air_quality
from advice import get_suggestions

def test_live():
    print("Testing live Ollama generation...")
    air = get_air_quality("Bengaluru")
    hh = {
        "children": 1,
        "older_adults": 1,
        "respiratory_sensitive": True,
        "has_purifier": True
    }
    res = get_suggestions("Bengaluru", air, hh, provider="ollama")
    print(f"ACTUAL PROVIDER USED: {res['provider_label']}")
    print(f"COUNT OF CARDS: {len(res['suggestions'])}")
    for i, s in enumerate(res["suggestions"], start=1):
        print(f"[{i}] ID: {s['action_id']}")
        print(f"    Label: {s['label']}")
        print(f"    Focus: {s['focus']}")
        print(f"    Action: {s['action']}")
        print(f"    Why: {s['why']}")
    assert len(res["suggestions"]) == 3, "Expected exactly 3 cards"
    assert len(set(s["action_id"] for s in res["suggestions"])) == 3, "Expected 3 distinct IDs"
    print("\nLive Ollama generation test PASSED successfully!")

if __name__ == "__main__":
    test_live()
