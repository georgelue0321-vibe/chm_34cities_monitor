#!/usr/bin/env python3
"""
Tests for event deduplication logic
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.deduplicator import EventDeduplicator


def test_extract_core_elements():
    """Test core element extraction."""
    dedup = EventDeduplicator()
    
    # Test case 1: Standard event
    text1 = "沈阳市房产局发布征集公告，收购存量商品房用作保障性住房，计划收购2000套"
    core1 = dedup.extract_core_elements(text1, "")
    
    assert core1["buyer"] == "沈阳市房产局", f"Expected 沈阳市房产局, got {core1['buyer']}"
    assert core1["units"] == 2000, f"Expected 2000, got {core1['units']}"
    print("✓ Test 1 passed: Standard event extraction")
    
    # Test case 2: Event with date
    text2 = "2025年6月3日，济南城市发展集团签约收购保利中科创新广场项目"
    core2 = dedup.extract_core_elements(text2, "")
    
    assert core2["buyer"] == "济南城市发展集团", f"Expected 济南城市发展集团, got {core2['buyer']}"
    assert core2["date"] == "2025-06-03", f"Expected 2025-06-03, got {core2['date']}"
    print("✓ Test 2 passed: Date extraction")
    
    # Test case 3: Event with location
    text3 = "沈河区拟收购759套存量房产用作配租型保障性住房"
    core3 = dedup.extract_core_elements(text3, "")
    
    assert core3["location"] == "沈河区", f"Expected 沈河区, got {core3['location']}"
    assert core3["units"] == 759, f"Expected 759, got {core3['units']}"
    print("✓ Test 3 passed: Location extraction")


def test_is_same_event():
    """Test event similarity detection."""
    dedup = EventDeduplicator()
    
    # Same event, different sources
    event1 = {
        "buyer": "沈阳市房产局",
        "project": "存量商品房收储项目",
        "date": "2025-06-03",
        "units": 2000,
        "location": "全市",
        "amount": 0
    }
    
    event2 = {
        "buyer": "沈阳市房产局",
        "project": "存量商品房收储项目",
        "date": "2025-06-03",
        "units": 2000,
        "location": "全市",
        "amount": 0
    }
    
    assert dedup.is_same_event(event1, event2) == True, "Should be same event"
    print("✓ Test 4 passed: Same event detection")
    
    # Different events
    event3 = {
        "buyer": "济南城市发展集团",
        "project": "保利中科创新广场",
        "date": "2024-12-31",
        "units": 500,
        "location": "历下区",
        "amount": 0
    }
    
    assert dedup.is_same_event(event1, event3) == False, "Should be different events"
    print("✓ Test 5 passed: Different event detection")
    
    # Similar event (minor differences)
    event4 = {
        "buyer": "沈阳市房产局",
        "project": "存量商品房收储项目",
        "date": "2025-06-03",
        "units": 2001,  # Slightly different
        "location": "全市",
        "amount": 0
    }
    
    assert dedup.is_same_event(event1, event4) == True, "Should be same event (minor difference)"
    print("✓ Test 6 passed: Minor difference handling")


def test_deduplicate():
    """Test full deduplication flow."""
    dedup = EventDeduplicator()
    
    events = [
        {
            "title": "沈阳市房产局发布征集公告",
            "abstract": "收购存量商品房2000套",
            "url": "https://fcj.shenyang.gov.cn/...",
            "source_priority": 100
        },
        {
            "title": "沈阳收储2000套存量房",
            "abstract": "沈阳市房产局发布公告",
            "url": "https://weixin.qq.com/...",
            "source_priority": 90
        },
        {
            "title": "济南城市发展集团签约",
            "abstract": "收购保利项目500套",
            "url": "https://jnjs.jinan.gov.cn/...",
            "source_priority": 100
        }
    ]
    
    deduplicated = dedup.deduplicate(events)
    
    assert len(deduplicated) == 2, f"Expected 2, got {len(deduplicated)}"
    print("✓ Test 7 passed: Deduplication count")
    
    # Verify the most authoritative source is kept
    shenyang_event = next(e for e in deduplicated if "沈阳" in e["title"])
    assert shenyang_event["source_priority"] == 100, "Should keep gov source"
    print("✓ Test 8 passed: Source priority")


def test_deduplication_report():
    """Test deduplication report generation."""
    dedup = EventDeduplicator()
    
    original = [{"title": "Event 1"}, {"title": "Event 2"}, {"title": "Event 3"}]
    deduplicated = [{"title": "Event 1"}, {"title": "Event 2"}]
    
    report = dedup.get_deduplication_report(original, deduplicated)
    
    assert report["original_count"] == 3
    assert report["deduplicated_count"] == 2
    assert report["removed_count"] == 1
    assert abs(report["removal_rate"] - 0.333) < 0.01
    print("✓ Test 9 passed: Report generation")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("Running deduplication tests...")
    print("=" * 50 + "\n")
    
    test_extract_core_elements()
    test_is_same_event()
    test_deduplicate()
    test_deduplication_report()
    
    print("\n" + "=" * 50)
    print("All tests passed! ✓")
    print("=" * 50)
