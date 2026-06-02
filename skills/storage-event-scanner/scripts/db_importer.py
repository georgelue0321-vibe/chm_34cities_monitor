#!/usr/bin/env python3
"""
Database Importer - Handles importing events into the CHM database
"""

import sqlite3
import hashlib
from datetime import datetime
from typing import List, Dict, Tuple


class DBImporter:
    """Handles database operations for storage events."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path)
    
    def compute_event_hash(self, city_id: str, date: str, stage: str, title: str) -> str:
        """Compute unique hash for event."""
        hash_str = f"{city_id}_{date}_{stage}_{title}"
        return hashlib.md5(hash_str.encode()).hexdigest()
    
    def event_exists(self, event_hash: str) -> bool:
        """Check if event already exists."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM storage_execution_events WHERE event_hash = ?",
            (event_hash,)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def insert_event(self, event: Dict) -> bool:
        """Insert a single event."""
        # Compute hash
        event_hash = self.compute_event_hash(
            event["city_id"],
            event.get("date", ""),
            event.get("stage", ""),
            event.get("title", "")
        )
        
        # Check if exists
        if self.event_exists(event_hash):
            return False
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO storage_execution_events (
                    city_id, district, event_date, event_stage, title, details,
                    buyer_entity, seller_entity, project_name,
                    units_planned, units_acquired, area_sqm_planned, area_sqm_acquired,
                    acquisition_price_total, acquisition_price_sqm, local_resale_avg_price_sqm,
                    discount_to_market, funding_type, source_url, source_reliability,
                    collected_at, event_hash, data_status, confidence_score,
                    is_score_eligible, methodology_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event["city_id"],
                event.get("district", "全市"),
                event.get("date", datetime.now().strftime("%Y-%m-%d")),
                event.get("stage", "政策表态"),
                event.get("title", ""),
                event.get("details", ""),
                event.get("buyer", ""),
                event.get("seller", ""),
                event.get("project", ""),
                event.get("units_planned", 0),
                event.get("units_acquired", 0),
                event.get("area_planned", 0.0),
                event.get("area_acquired", 0.0),
                event.get("price_total", 0.0),
                event.get("price_sqm", 0.0),
                event.get("resale_avg", 0.0),
                event.get("discount", 0.0),
                event.get("funding_type", ""),
                event.get("source_url", ""),
                event.get("source_priority", 50),
                datetime.now().isoformat(),
                event_hash,
                "official",
                event.get("confidence", 80),
                1,
                event.get("methodology_note", "")
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error inserting event: {e}")
            conn.rollback()
            return False
            
        finally:
            conn.close()
    
    def insert_events(self, events: List[Dict]) -> Tuple[int, int]:
        """Insert multiple events."""
        imported = 0
        skipped = 0
        
        for event in events:
            if self.insert_event(event):
                imported += 1
            else:
                skipped += 1
        
        return imported, skipped
    
    def update_event(self, event_hash: str, updates: Dict) -> bool:
        """Update an existing event."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Build update query
            set_clauses = []
            values = []
            for key, value in updates.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)
            
            if not set_clauses:
                return False
            
            values.append(event_hash)
            
            cursor.execute(f"""
                UPDATE storage_execution_events 
                SET {', '.join(set_clauses)}
                WHERE event_hash = ?
            """, values)
            
            conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            print(f"Error updating event: {e}")
            conn.rollback()
            return False
            
        finally:
            conn.close()
    
    def get_events_by_city(self, city_id: str) -> List[Dict]:
        """Get all events for a city."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM storage_execution_events 
            WHERE city_id = ? 
            ORDER BY event_date DESC
        """, (city_id,))
        
        events = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return events
    
    def get_event_statistics(self) -> Dict:
        """Get event statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Total events
        cursor.execute("SELECT COUNT(*) FROM storage_execution_events")
        stats["total_events"] = cursor.fetchone()[0]
        
        # Events by city
        cursor.execute("""
            SELECT city_id, COUNT(*) as count 
            FROM storage_execution_events 
            GROUP BY city_id
        """)
        stats["events_by_city"] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Events by stage
        cursor.execute("""
            SELECT event_stage, COUNT(*) as count 
            FROM storage_execution_events 
            GROUP BY event_stage
        """)
        stats["events_by_stage"] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Latest event date
        cursor.execute("""
            SELECT MAX(event_date) FROM storage_execution_events
        """)
        stats["latest_event_date"] = cursor.fetchone()[0]
        
        conn.close()
        
        return stats
    
    def cleanup_duplicates(self) -> int:
        """Remove duplicate events, keeping the most recent."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Find duplicates
        cursor.execute("""
            SELECT city_id, title, COUNT(*) as count
            FROM storage_execution_events
            GROUP BY city_id, title
            HAVING count > 1
        """)
        
        duplicates = cursor.fetchall()
        removed = 0
        
        for city_id, title, count in duplicates:
            # Keep the most recent, delete others
            cursor.execute("""
                DELETE FROM storage_execution_events 
                WHERE city_id = ? AND title = ? AND id NOT IN (
                    SELECT id FROM storage_execution_events 
                    WHERE city_id = ? AND title = ? 
                    ORDER BY collected_at DESC 
                    LIMIT 1
                )
            """, (city_id, title, city_id, title))
            
            removed += cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return removed
