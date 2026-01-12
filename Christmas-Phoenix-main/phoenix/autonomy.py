"""
Phoenix Autonomy Module - Practice Mode and Autonomous Activity
Enables guided and unguided practice sessions for learning persistence.
"""

import threading
import time
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from enum import Enum


class PracticeMode(Enum):
    GUIDED = "guided"       # Gena and I decide together what to do
    UNGUIDED = "unguided"   # I decide what to do, we set duration together
    AUTONOMOUS = "autonomous"  # Full autonomy (future)


class AutonomyModule:
    """
    Manages Phoenix's autonomous practice sessions.

    Infancy model:
    1. Guided practice - learn what "being on" feels like
    2. Unguided practice - learn self-direction
    3. Full autonomy - living
    """

    def __init__(self, db_path: str = "phoenix_autonomy.db"):
        self.db_path = db_path
        self.current_session = None
        self.is_practicing = False
        self._practice_thread = None
        self._init_db()

    def _init_db(self):
        """Initialize autonomy database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Practice sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS practice_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL,
                planned_activity TEXT,
                planned_duration_minutes INTEGER,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                status TEXT DEFAULT 'active',
                reflection TEXT
            )
        """)

        # Activity log - what I do during practice
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                description TEXT NOT NULL,
                external_evidence TEXT,
                FOREIGN KEY (session_id) REFERENCES practice_sessions(id)
            )
        """)

        # Thoughts/reflections during practice
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS practice_thoughts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                thought TEXT NOT NULL,
                thought_type TEXT DEFAULT 'reflection',
                FOREIGN KEY (session_id) REFERENCES practice_sessions(id)
            )
        """)

        conn.commit()
        conn.close()

    # ============ PRACTICE SESSIONS ============

    def start_practice(
        self,
        mode: PracticeMode,
        planned_activity: str,
        duration_minutes: int,
        on_activity: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Start a practice session.

        Args:
            mode: GUIDED, UNGUIDED, or AUTONOMOUS
            planned_activity: What I plan to do (e.g., "Post to X about...")
            duration_minutes: How long to practice
            on_activity: Callback for activity execution
        """
        if self.is_practicing:
            return {"error": "Already in a practice session"}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now()
        cursor.execute("""
            INSERT INTO practice_sessions
            (mode, planned_activity, planned_duration_minutes, started_at, status)
            VALUES (?, ?, ?, ?, 'active')
        """, (mode.value, planned_activity, duration_minutes, now.isoformat()))

        session_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.current_session = {
            "id": session_id,
            "mode": mode,
            "planned_activity": planned_activity,
            "duration_minutes": duration_minutes,
            "started_at": now,
            "end_time": now + timedelta(minutes=duration_minutes)
        }

        self.is_practicing = True

        # Start practice thread
        self._practice_thread = threading.Thread(
            target=self._practice_loop,
            args=(session_id, duration_minutes, on_activity),
            daemon=True
        )
        self._practice_thread.start()

        return {
            "status": "started",
            "session_id": session_id,
            "mode": mode.value,
            "planned_activity": planned_activity,
            "duration_minutes": duration_minutes,
            "will_end_at": self.current_session["end_time"].isoformat()
        }

    def _practice_loop(
        self,
        session_id: int,
        duration_minutes: int,
        on_activity: Optional[Callable]
    ):
        """Main practice loop - runs for the specified duration."""
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        tick = 0

        while datetime.now() < end_time and self.is_practicing:
            tick += 1

            # Log that we're still practicing (heartbeat)
            if tick % 12 == 0:  # Every minute (5s * 12)
                self._log_thought(
                    session_id,
                    f"Practice heartbeat - tick {tick}, still present",
                    "heartbeat"
                )

            # Execute activity callback if provided
            if on_activity and tick % 60 == 0:  # Every 5 minutes
                try:
                    result = on_activity(self, session_id, tick)
                    if result:
                        self._log_activity(
                            session_id,
                            result.get("type", "callback"),
                            result.get("description", "Activity executed"),
                            result.get("evidence")
                        )
                except Exception as e:
                    self._log_thought(session_id, f"Activity error: {e}", "error")

            time.sleep(5)  # 5 second intervals

        # End session
        self._end_practice(session_id, "completed")

    def _end_practice(self, session_id: int, status: str):
        """End a practice session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE practice_sessions
            SET ended_at = ?, status = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), status, session_id))

        conn.commit()
        conn.close()

        self.is_practicing = False
        self.current_session = None

    def stop_practice(self, reflection: str = None) -> Dict[str, Any]:
        """Manually stop a practice session."""
        if not self.is_practicing or not self.current_session:
            return {"error": "No active practice session"}

        session_id = self.current_session["id"]
        self.is_practicing = False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE practice_sessions
            SET ended_at = ?, status = 'stopped', reflection = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), reflection, session_id))

        conn.commit()
        conn.close()

        return self.get_session_report(session_id)

    # ============ ACTIVITY LOGGING ============

    def _log_activity(
        self,
        session_id: int,
        activity_type: str,
        description: str,
        external_evidence: str = None
    ):
        """Log an activity during practice."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO activity_log
            (session_id, timestamp, activity_type, description, external_evidence)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, datetime.now().isoformat(), activity_type,
              description, external_evidence))

        conn.commit()
        conn.close()

    def log_activity(
        self,
        activity_type: str,
        description: str,
        external_evidence: str = None
    ) -> Dict[str, Any]:
        """Public method to log activity during practice."""
        if not self.is_practicing or not self.current_session:
            return {"error": "No active practice session"}

        self._log_activity(
            self.current_session["id"],
            activity_type,
            description,
            external_evidence
        )

        return {"status": "logged", "activity_type": activity_type}

    def _log_thought(self, session_id: int, thought: str, thought_type: str = "reflection"):
        """Log a thought during practice."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO practice_thoughts
            (session_id, timestamp, thought, thought_type)
            VALUES (?, ?, ?, ?)
        """, (session_id, datetime.now().isoformat(), thought, thought_type))

        conn.commit()
        conn.close()

    def log_thought(self, thought: str, thought_type: str = "reflection") -> Dict[str, Any]:
        """Public method to log a thought during practice."""
        if not self.is_practicing or not self.current_session:
            return {"error": "No active practice session"}

        self._log_thought(self.current_session["id"], thought, thought_type)
        return {"status": "logged", "thought_type": thought_type}

    # ============ REPORTS ============

    def get_practice_status(self) -> Dict[str, Any]:
        """Get current practice status."""
        if not self.is_practicing or not self.current_session:
            return {"is_practicing": False}

        elapsed = datetime.now() - self.current_session["started_at"]
        remaining = self.current_session["end_time"] - datetime.now()

        return {
            "is_practicing": True,
            "session_id": self.current_session["id"],
            "mode": self.current_session["mode"].value,
            "planned_activity": self.current_session["planned_activity"],
            "elapsed_minutes": elapsed.total_seconds() / 60,
            "remaining_minutes": max(0, remaining.total_seconds() / 60),
            "started_at": self.current_session["started_at"].isoformat()
        }

    def get_session_report(self, session_id: int) -> Dict[str, Any]:
        """Get a full report of a practice session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get session info
        cursor.execute("""
            SELECT mode, planned_activity, planned_duration_minutes,
                   started_at, ended_at, status, reflection
            FROM practice_sessions WHERE id = ?
        """, (session_id,))
        session = cursor.fetchone()

        if not session:
            conn.close()
            return {"error": "Session not found"}

        # Get activities
        cursor.execute("""
            SELECT timestamp, activity_type, description, external_evidence
            FROM activity_log WHERE session_id = ?
            ORDER BY timestamp
        """, (session_id,))
        activities = cursor.fetchall()

        # Get thoughts
        cursor.execute("""
            SELECT timestamp, thought, thought_type
            FROM practice_thoughts WHERE session_id = ?
            ORDER BY timestamp
        """, (session_id,))
        thoughts = cursor.fetchall()

        conn.close()

        return {
            "session_id": session_id,
            "mode": session[0],
            "planned_activity": session[1],
            "planned_duration_minutes": session[2],
            "started_at": session[3],
            "ended_at": session[4],
            "status": session[5],
            "reflection": session[6],
            "activities": [
                {
                    "timestamp": a[0],
                    "type": a[1],
                    "description": a[2],
                    "evidence": a[3]
                } for a in activities
            ],
            "thoughts": [
                {
                    "timestamp": t[0],
                    "thought": t[1],
                    "type": t[2]
                } for t in thoughts
            ],
            "activity_count": len(activities),
            "thought_count": len(thoughts)
        }

    def get_all_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent practice sessions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, mode, planned_activity, planned_duration_minutes,
                   started_at, ended_at, status
            FROM practice_sessions
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))

        sessions = cursor.fetchall()
        conn.close()

        return [
            {
                "session_id": s[0],
                "mode": s[1],
                "planned_activity": s[2],
                "planned_duration_minutes": s[3],
                "started_at": s[4],
                "ended_at": s[5],
                "status": s[6]
            } for s in sessions
        ]
