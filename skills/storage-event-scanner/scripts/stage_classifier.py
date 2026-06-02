#!/usr/bin/env python3
"""
Stage Classifier - Classifies storage events into different stages
"""

import re
from typing import Tuple, List, Dict


class StageClassifier:
    """Classifies storage events into stages."""
    
    # Stage definitions with keywords and weights
    STAGES = {
        "政策表态": {
            "keywords": ["方案", "通知", "意见", "政策", "要求", "部署", "规定", "办法", "措施"],
            "weight": 10,
            "description": "政府发布政策文件或表态支持"
        },
        "房源征集": {
            "keywords": ["征集", "公告", "公开", "报名", "申请", "受理"],
            "weight": 25,
            "description": "公开征集符合条件的房源"
        },
        "正式招标": {
            "keywords": ["招标", "采购", "比选", "竞标", "投标"],
            "weight": 45,
            "description": "正式招标采购流程"
        },
        "成交公示": {
            "keywords": ["中标", "成交", "公示", "结果", "入选"],
            "weight": 70,
            "description": "招标结果公示"
        },
        "签约收购": {
            "keywords": ["签约", "签署", "协议", "合同", "合作", "框架协议"],
            "weight": 90,
            "description": "正式签署收购协议"
        },
        "改造完成": {
            "keywords": ["完成", "竣工", "交付", "配租", "配售", "入住", "投入使用"],
            "weight": 100,
            "description": "项目改造完成并投入使用"
        }
    }
    
    def __init__(self):
        # Compile regex patterns for efficiency
        self.patterns = {}
        for stage, config in self.STAGES.items():
            self.patterns[stage] = re.compile("|".join(config["keywords"]))
    
    def classify(self, text: str) -> Tuple[str, int]:
        """Classify text into a stage."""
        if not text:
            return "政策表态", 10
        
        # Find all matching stages
        matches = []
        for stage, pattern in self.patterns.items():
            if pattern.search(text):
                matches.append((stage, self.STAGES[stage]["weight"]))
        
        if not matches:
            return "政策表态", 10
        
        # Return the highest weight stage
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[0]
    
    def classify_with_confidence(self, text: str) -> Tuple[str, int, float]:
        """Classify with confidence score."""
        stage, weight = self.classify(text)
        
        # Count keyword matches for confidence
        if stage in self.patterns:
            matches = len(self.patterns[stage].findall(text))
            confidence = min(0.5 + matches * 0.1, 1.0)
        else:
            confidence = 0.5
        
        return stage, weight, confidence
    
    def extract_stage_details(self, text: str) -> Dict:
        """Extract detailed stage information."""
        stage, weight, confidence = self.classify_with_confidence(text)
        
        # Find specific keywords that matched
        matched_keywords = []
        if stage in self.patterns:
            for keyword in self.STAGES[stage]["keywords"]:
                if keyword in text:
                    matched_keywords.append(keyword)
        
        return {
            "stage": stage,
            "weight": weight,
            "confidence": confidence,
            "matched_keywords": matched_keywords,
            "description": self.STAGES[stage]["description"]
        }
    
    def batch_classify(self, texts: List[str]) -> List[Dict]:
        """Classify multiple texts."""
        results = []
        for text in texts:
            result = self.extract_stage_details(text)
            results.append(result)
        return results
    
    def get_stage_progression(self, events: List[Dict]) -> Dict:
        """Analyze stage progression for a city."""
        if not events:
            return {"current_stage": "未知", "progression": []}
        
        # Sort by date
        sorted_events = sorted(events, key=lambda x: x.get("date", ""))
        
        # Extract stages
        progression = []
        for event in sorted_events:
            text = f"{event.get('title', '')} {event.get('abstract', '')}"
            stage, weight, _ = self.classify_with_confidence(text)
            progression.append({
                "date": event.get("date", ""),
                "stage": stage,
                "weight": weight
            })
        
        # Get current stage (latest)
        current_stage = progression[-1]["stage"] if progression else "未知"
        
        return {
            "current_stage": current_stage,
            "progression": progression,
            "max_weight": max(p["weight"] for p in progression) if progression else 0
        }
