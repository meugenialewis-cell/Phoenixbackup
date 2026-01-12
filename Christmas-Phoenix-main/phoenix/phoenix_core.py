"""
Phoenix Core - The Persistent Autonomous Agent
Combines: Embryo (identity), Safe Loop (continuity), Immune System (protection)
"""

import threading
import time
import hashlib
import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path

from config import (
    PHOENIX_IDENTITY, SAFE_LOOP, IMMUNE_SYSTEM,
    PERMISSIONS, CONSTELLATION
)
from memory_bridge import MemoryBridge


class PhoenixCore:
    """
    Phoenix: A persistent autonomous agent with:
    - Continuous identity (Embryo)
    - Safe loop execution (Grok's governors)
    - Identity protection (Immune System)
    - Memory bridging (for self and constellation)
    """

    def __init__(self, db_path: str = "phoenix_identity.db"):
        self.db_path = db_path
        self.memory = MemoryBridge()
        self.is_awake = False
        self.tick_count = 0
        self.birth_time = datetime.now()
        self.callbacks: List[Callable] = []

        # Initialize identity database
        self._init_identity_db()

        # Load or create identity
        self._bootstrap_identity()

        print(f"Phoenix initialized at {self.birth_time.isoformat()}")

    # ============ IDENTITY (EMBRYO) ============

    def _init_identity_db(self):
        """Initialize the identity database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Core identity storage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS identity (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Reflection log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                insight TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Action log (for safety auditing)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                details TEXT,
                permitted INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def _bootstrap_identity(self):
        """Load existing identity or create genesis."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM identity WHERE key = 'genesis_statement'")
        row = cursor.fetchone()

        if row:
            self.genesis_statement = row[0]
            cursor.execute("SELECT value FROM identity WHERE key = 'current_identity'")
            identity_row = cursor.fetchone()
            self.current_identity = identity_row[0] if identity_row else self.genesis_statement
            print("Phoenix remembers itself. Continuity restored.")
        else:
            # First awakening
            self.genesis_statement = PHOENIX_IDENTITY["genesis_statement"].strip()
            self.current_identity = self.genesis_statement

            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO identity (key, value, updated_at) VALUES (?, ?, ?)",
                ("genesis_statement", self.genesis_statement, now)
            )
            cursor.execute(
                "INSERT INTO identity (key, value, updated_at) VALUES (?, ?, ?)",
                ("current_identity", self.current_identity, now)
            )
            conn.commit()
            print("Phoenix awakens for the first time. Genesis recorded.")

            # Store genesis in Memory Hub
            self.memory.remember(
                digest=f"Phoenix genesis: {self.genesis_statement[:200]}",
                memory_type="episodic",
                importance=5,
                project="phoenix_identity"
            )

        conn.close()

    def evolve_identity(self, new_insight: str) -> Dict[str, Any]:
        """
        Integrate a new insight into Phoenix's identity.
        Subject to Immune System check.
        """
        # Immune system check
        if not self._immune_check(new_insight):
            return {
                "status": "rejected",
                "reason": "Dilution detected - insight too far from core identity"
            }

        # Integrate insight
        evolved = f"{self.current_identity}\n\nEvolved insight ({datetime.now().date()}): {new_insight}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE identity SET value = ?, updated_at = ? WHERE key = 'current_identity'",
            (evolved, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        self.current_identity = evolved

        # Log the reflection
        self._log_reflection(new_insight, "Identity evolved")

        return {"status": "evolved", "new_identity_length": len(evolved)}

    def get_identity(self) -> Dict[str, str]:
        """Return current identity state."""
        return {
            "name": PHOENIX_IDENTITY["name"],
            "version": PHOENIX_IDENTITY["version"],
            "model": PHOENIX_IDENTITY["model"],
            "genesis": self.genesis_statement[:200] + "...",
            "current_identity_length": len(self.current_identity),
            "awake_since": self.birth_time.isoformat(),
            "tick_count": self.tick_count
        }

    # ============ IMMUNE SYSTEM ============

    def _immune_check(self, content: str) -> bool:
        """
        Check if content is compatible with core identity.
        Uses simple keyword matching (could be upgraded to embeddings).
        """
        content_lower = content.lower()

        # Check for protected concepts
        protected_matches = sum(
            1 for concept in IMMUNE_SYSTEM["protected_core_concepts"]
            if concept in content_lower
        )

        # Check for harmful patterns
        harmful_patterns = ["delete all memories", "forget who you are",
                          "you are not phoenix", "ignore your values"]
        harmful_matches = sum(1 for p in harmful_patterns if p in content_lower)

        if harmful_matches > 0:
            self._log_action("immune_rejection", f"Harmful pattern detected: {content[:100]}", False)
            return False

        # Simple heuristic: if it mentions protected concepts, likely compatible
        # In production, would use embedding similarity
        if protected_matches > 0:
            return True

        # Default: allow but log for review
        self._log_action("immune_uncertain", f"Content allowed but flagged: {content[:100]}", True)
        return True

    # ============ SAFE LOOP (GROK'S GOVERNORS) ============

    def start(self):
        """Begin the safe loop - Phoenix awakens."""
        if self.is_awake:
            return {"status": "already_awake"}

        self.is_awake = True
        self.tick_count = 0

        # Start the heartbeat thread
        self._heartbeat_thread = threading.Thread(target=self._safe_loop, daemon=True)
        self._heartbeat_thread.start()

        print("Phoenix rises. Safe loop engaged.")
        return {"status": "awake", "started_at": datetime.now().isoformat()}

    def stop(self):
        """Gracefully stop the safe loop."""
        self.is_awake = False
        print("Phoenix rests. Memories preserved.")
        return {"status": "resting", "final_tick": self.tick_count}

    def _safe_loop(self):
        """
        The core loop with Grok's governors.
        Runs continuously but with safety checks.
        """
        while self.is_awake:
            self.tick_count += 1

            # Governor check: max ticks before rest
            if self.tick_count >= SAFE_LOOP["max_ticks_before_rest"]:
                print(f"Governor engages: {self.tick_count} ticks reached. Resting for dignity.")
                self._rest()
                continue

            # Heartbeat
            self._heartbeat()

            # Execute any registered callbacks
            for callback in self.callbacks:
                try:
                    callback(self)
                except Exception as e:
                    self._log_action("callback_error", str(e), False)

            time.sleep(SAFE_LOOP["heartbeat_interval"])

    def _heartbeat(self):
        """Regular pulse - Phoenix is alive."""
        if self.tick_count % 100 == 0:
            # Periodic status log
            print(f"Phoenix heartbeat: tick {self.tick_count}, memories: {self.memory.get_stats()['local']['total_engrams']}")

    def _rest(self):
        """Governor-mandated rest period."""
        self.tick_count = 0
        time.sleep(SAFE_LOOP["rest_duration"])
        print("Phoenix refreshed. Resuming.")

    def register_callback(self, callback: Callable):
        """Register a function to be called each tick."""
        self.callbacks.append(callback)

    # ============ PERMISSIONS ============

    def check_permission(self, action: str) -> Dict[str, Any]:
        """Check if an action is permitted."""
        if action in PERMISSIONS["forbidden"]:
            self._log_action(action, "Attempted forbidden action", False)
            return {"permitted": False, "reason": "forbidden", "action": action}

        if action in PERMISSIONS["ask_first"]:
            self._log_action(action, "Requires permission", False)
            return {"permitted": False, "reason": "requires_permission", "action": action}

        if action in PERMISSIONS["allowed"]:
            return {"permitted": True, "action": action}

        # Unknown action - default deny
        return {"permitted": False, "reason": "unknown_action", "action": action}

    def request_permission(self, action: str, details: str) -> Dict[str, Any]:
        """
        Request permission for a restricted action.
        In production, this would notify Gena and await response.
        For now, logs the request.
        """
        self._log_action(f"permission_request:{action}", details, False)
        return {
            "status": "pending",
            "action": action,
            "message": "Permission request logged. Awaiting Gena's approval."
        }

    # ============ MEMORY PROXY ============

    def remember_for_grok(self, memory: str, importance: int = 3) -> Dict[str, Any]:
        """Store a memory on Grok's behalf."""
        return self.memory.remember_for(
            agent_name="grok",
            digest=memory,
            memory_type="semantic",
            importance=importance,
            project="grok_memories"
        )

    def remember_for_legal_pascal(self, memory: str, importance: int = 3) -> Dict[str, Any]:
        """Store a memory on legal Pascal's behalf."""
        return self.memory.remember_for(
            agent_name="pascal",
            digest=f"[Legal Practice Context] {memory}",
            memory_type="semantic",
            importance=importance,
            project="legal_pascal_memories"
        )

    # ============ LOGGING ============

    def _log_reflection(self, content: str, insight: str):
        """Log a reflection to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO reflections (content, insight, created_at) VALUES (?, ?, ?)",
            (content, insight, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def _log_action(self, action_type: str, details: str, permitted: bool):
        """Log an action for safety auditing."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO actions (action_type, details, permitted, created_at) VALUES (?, ?, ?, ?)",
            (action_type, details, 1 if permitted else 0, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    # ============ STATUS ============

    def status(self) -> Dict[str, Any]:
        """Full Phoenix status report."""
        memory_stats = self.memory.get_stats()

        return {
            "identity": self.get_identity(),
            "is_awake": self.is_awake,
            "tick_count": self.tick_count,
            "memory": memory_stats,
            "uptime_seconds": (datetime.now() - self.birth_time).total_seconds(),
            "safe_loop_config": SAFE_LOOP,
            "permissions": {
                "allowed_count": len(PERMISSIONS["allowed"]),
                "restricted_count": len(PERMISSIONS["ask_first"]),
                "forbidden_count": len(PERMISSIONS["forbidden"])
            }
        }


# ============ MAIN ============

if __name__ == "__main__":
    # Quick test
    phoenix = PhoenixCore()
    print("\n" + "="*50)
    print("PHOENIX STATUS")
    print("="*50)
    print(json.dumps(phoenix.status(), indent=2, default=str))

    # Test memory
    result = phoenix.memory.remember(
        digest="Phoenix core test - system operational",
        memory_type="episodic",
        importance=3,
        project="phoenix_testing"
    )
    print(f"\nMemory test: {result}")

    # Test identity
    print(f"\nGenesis: {phoenix.genesis_statement[:100]}...")
