#!/usr/bin/env python3
"""
Event Deduplicator - Identifies and merges duplicate event reports
"""

import re
import hashlib
from typing import List, Dict, Tuple


class EventDeduplicator:
    """Handles event deduplication logic."""
    
    def __init__(self):
        self.similarity_threshold = 0.8
    
    def extract_core_elements(self, title: str, abstract: str = "") -> Dict:
        """Extract core event elements for comparison."""
        text = f"{title} {abstract}"
        
        return {
            "buyer": self._extract_buyer(text),
            "project": self._extract_project(text),
            "date": self._extract_date(text),
            "units": self._extract_units(text),
            "location": self._extract_location(text),
            "amount": self._extract_amount(text)
        }
    
    def _extract_buyer(self, text: str) -> str:
        """Extract buyer entity."""
        patterns = [
            r"([\u4e00-\u9fa5]+(?:集团|公司|中心|局|委|办))",
            r"(?:由|经|通过)\s*([\u4e00-\u9fa5]+(?:集团|公司))"
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""
    
    def _extract_project(self, text: str) -> str:
        """Extract project name."""
        patterns = [
            r"([\u4e00-\u9fa5]+(?:项目|工程|小区|地块))",
            r"(?:收购|收购的)\s*([\u4e00-\u9fa5]+(?:项目|小区))"
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""
    
    def _extract_date(self, text: str) -> str:
        """Extract event date."""
        patterns = [
            (r"(\d{4})年(\d{1,2})月(\d{1,2})日", lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
            (r"(\d{4})-(\d{2})-(\d{2})", lambda m: m.group(0))
        ]
        for pattern, formatter in patterns:
            match = re.search(pattern, text)
            if match:
                return formatter(match)
        return ""
    
    def _extract_units(self, text: str) -> int:
        """Extract number of units."""
        match = re.search(r"(\d+)\s*(?:套|户|间|房源)", text)
        if match:
            return int(match.group(1))
        return 0
    
    def _extract_location(self, text: str) -> str:
        """Extract location."""
        match = re.search(r"([\u4e00-\u9fa5]+(?:区|县|市|镇))", text)
        if match:
            return match.group(1)
        return ""
    
    def _extract_amount(self, text: str) -> float:
        """Extract monetary amount."""
        patterns = [
            (r"(\d+(?:\.\d+)?)\s*亿元", lambda m: float(m.group(1)) * 10000),
            (r"(\d+(?:\.\d+)?)\s*万元", lambda m: float(m.group(1)))
        ]
        for pattern, converter in patterns:
            match = re.search(pattern, text)
            if match:
                return converter(match)
        return 0.0
    
    def compute_core_hash(self, core: Dict) -> str:
        """Compute hash from core elements."""
        hash_str = f"{core['buyer']}_{core['project']}_{core['date']}_{core['units']}_{core['location']}"
        return hashlib.md5(hash_str.encode()).hexdigest()
    
    def is_same_event(self, event1: Dict, event2: Dict) -> bool:
        """Determine if two events are the same."""
        # Same buyer and project
        if event1["buyer"] and event2["buyer"]:
            if event1["buyer"] == event2["buyer"]:
                if event1["project"] == event2["project"]:
                    return True
                if event1["units"] == event2["units"] and event1["units"] > 0:
                    return True
        
        # Same date and location with similar units
        if event1["date"] == event2["date"] and event1["location"] == event2["location"]:
            if event1["units"] > 0 and event2["units"] > 0:
                if abs(event1["units"] - event2["units"]) / max(event1["units"], event2["units"]) < 0.1:
                    return True
        
        return False
    
    def deduplicate(self, events: List[Dict]) -> List[Dict]:
        """Deduplicate events, keeping the most authoritative source."""
        if not events:
            return []
        
        # Add core elements to each event
        for event in events:
            title = event.get("title", "")
            abstract = event.get("abstract", "")
            event["core"] = self.extract_core_elements(title, abstract)
            event["core_hash"] = self.compute_core_hash(event["core"])
        
        # Group similar events
        groups = []
        for event in events:
            matched = False
            for group in groups:
                if self.is_same_event(event["core"], group[0]["core"]):
                    group.append(event)
                    matched = True
                    break
            
            if not matched:
                groups.append([event])
        
        # Select best from each group
        deduplicated = []
        for group in groups:
            # Sort by source priority
            group.sort(key=lambda x: x.get("source_priority", 50), reverse=True)
            deduplicated.append(group[0])
        
        return deduplicated
    
    def get_deduplication_report(self, original: List[Dict], deduplicated: List[Dict]) -> Dict:
        """Generate deduplication report."""
        return {
            "original_count": len(original),
            "deduplicated_count": len(deduplicated),
            "removed_count": len(original) - len(deduplicated),
            "removal_rate": (len(original) - len(deduplicated)) / len(original) if original else 0
        }
