#!/usr/bin/env python3
"""
Source Validator - Validates and prioritizes information sources
"""

import urllib.request
import ssl
import socket
from typing import Tuple, Dict, Optional
from urllib.parse import urlparse


class SourceValidator:
    """Validates and classifies information sources."""
    
    # Source priority mapping
    SOURCE_PRIORITY = {
        "gov_official": 100,
        "gov_wechat": 90,
        "state_media": 80,
        "local_media": 70,
        "industry_media": 60,
        "other": 50
    }
    
    # Domain classifications
    GOV_DOMAINS = [".gov.cn", "gov."]
    STATE_MEDIA_DOMAINS = ["xinhuanet.com", "people.com.cn", "cctv.com", "china.com.cn"]
    LOCAL_MEDIA_DOMAINS = ["ifeng.com", "163.com", "sina.com", "sohu.com", "qq.com"]
    INDUSTRY_MEDIA_DOMAINS = ["anjuke.com", "lianjia.com", "ke.com", "fang.com"]
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        # Disable SSL verification for gov.cn sites
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
    
    def classify_source(self, url: str) -> str:
        """Classify source type based on URL."""
        if not url:
            return "other"
        
        url_lower = url.lower()
        
        # Government official
        if any(domain in url_lower for domain in self.GOV_DOMAINS):
            return "gov_official"
        
        # Government WeChat
        if "weixin.qq.com" in url_lower:
            # Check if it's a government account (simplified check)
            return "gov_wechat"
        
        # State media
        if any(domain in url_lower for domain in self.STATE_MEDIA_DOMAINS):
            return "state_media"
        
        # Local media
        if any(domain in url_lower for domain in self.LOCAL_MEDIA_DOMAINS):
            return "local_media"
        
        # Industry media
        if any(domain in url_lower for domain in self.INDUSTRY_MEDIA_DOMAINS):
            return "industry_media"
        
        return "other"
    
    def get_source_priority(self, url: str) -> int:
        """Get priority score for source."""
        source_type = self.classify_source(url)
        return self.SOURCE_PRIORITY.get(source_type, 50)
    
    def verify_url(self, url: str) -> Tuple[bool, str]:
        """Verify if URL is accessible."""
        if not url:
            return False, "empty_url"
        
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = "https://" + url
            
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                method="HEAD"
            )
            
            response = urllib.request.urlopen(
                req,
                timeout=self.timeout,
                context=self.ssl_context
            )
            
            status_code = response.getcode()
            return True, str(status_code)
            
        except urllib.error.HTTPError as e:
            return False, f"http_{e.code}"
        except urllib.error.URLError as e:
            return False, f"url_error: {str(e.reason)}"
        except socket.timeout:
            return False, "timeout"
        except Exception as e:
            return False, f"error: {str(e)}"
    
    def find_alternative_source(self, title: str, city_name: str) -> Optional[Dict]:
        """Find alternative source if primary is unavailable."""
        # This would typically involve searching for the same event
        # from other sources. For now, return None.
        # In a full implementation, this would:
        # 1. Search for the same title on other platforms
        # 2. Check government WeChat accounts
        # 3. Look for media转载
        return None
    
    def validate_source(self, url: str, title: str = "") -> Dict:
        """Full source validation."""
        source_type = self.classify_source(url)
        priority = self.get_source_priority(url)
        is_accessible, status = self.verify_url(url)
        
        result = {
            "url": url,
            "source_type": source_type,
            "priority": priority,
            "is_accessible": is_accessible,
            "status": status,
            "needs_alternative": not is_accessible and source_type in ["gov_official", "gov_wechat"]
        }
        
        # If government source is unavailable, try to find alternative
        if result["needs_alternative"] and title:
            alternative = self.find_alternative_source(title, "")
            if alternative:
                result["alternative"] = alternative
        
        return result
    
    def batch_validate(self, sources: list) -> list:
        """Validate multiple sources."""
        results = []
        for source in sources:
            url = source.get("url", "")
            title = source.get("title", "")
            result = self.validate_source(url, title)
            results.append({**source, **result})
        return results
