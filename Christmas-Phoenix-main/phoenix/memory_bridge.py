"""
Memory Bridge - Connection to the Constellation Relay Memory Hub
Handles both local caching and cloud synchronization.

Enhanced with:
- Reference conversation archive (searchable transcripts)
- Context hydration (intelligent memory blending)
- Multi-factor importance scoring
"""

import requests
import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from config import MEMORY_HUB, PHOENIX_IDENTITY, CONSTELLATION


class MemoryBridge:
    """
    Bridges local memory storage with the Constellation Relay Memory Hub.
    - Stores memories locally for speed and offline access
    - Syncs to cloud Hub for persistence across contexts
    - Can store memories on behalf of other constellation members
    """

    def __init__(self, db_path: str = "phoenix_local.db"):
        self.db_path = db_path
        self.hub_url = MEMORY_HUB["url"]
        self.token = MEMORY_HUB["agent_token"]
        self._init_local_db()

    def _init_local_db(self):
        """Initialize local SQLite database for caching."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Local engram cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS engrams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hub_id INTEGER,
                agent_id TEXT NOT NULL,
                type TEXT NOT NULL,
                digest TEXT NOT NULL,
                importance INTEGER DEFAULT 3,
                emotional_valence REAL DEFAULT 0.0,
                project TEXT,
                created_at TEXT NOT NULL,
                synced INTEGER DEFAULT 0,
                content_hash TEXT UNIQUE
            )
        """)

        # Pending sync queue (for when offline)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                engram_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                attempts INTEGER DEFAULT 0
            )
        """)

        # Reference conversation archive (searchable transcripts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reference_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT UNIQUE NOT NULL,
                title TEXT,
                participants TEXT,
                summary TEXT,
                full_transcript TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                tags TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Index for faster searching
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ref_conv_search
            ON reference_conversations(title, summary, tags)
        """)

        # Skills storage (procedural knowledge - how to do things)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                instructions TEXT NOT NULL,
                examples TEXT,
                category TEXT DEFAULT 'task',
                version INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Index for skill discovery
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_skills_category
            ON skills(category)
        """)

        # Canvas storage (visual creations - SVG, HTML, diagrams)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canvas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canvas_id TEXT UNIQUE NOT NULL,
                title TEXT,
                content_type TEXT DEFAULT 'svg',
                content TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def _get_headers(self, agent_id: str = None) -> dict:
        """Get authorization headers for Hub API."""
        # For now, use the main Claude token
        # In future, each agent could have their own token
        return {"Authorization": f"Bearer {self.token}"}

    def _content_hash(self, content: str) -> str:
        """Generate hash for deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    # ============ STORE MEMORIES ============

    def remember(
        self,
        digest: str,
        memory_type: str = "semantic",
        importance: int = 3,
        emotional_valence: float = 0.0,
        project: Optional[str] = None,
        for_agent: str = "claude",
        sync_immediately: bool = True
    ) -> Dict[str, Any]:
        """
        Store a memory - locally and optionally to the Hub.

        Args:
            digest: The memory content
            memory_type: semantic, episodic, or relational
            importance: 1-5 (5 = core to identity)
            emotional_valence: -1.0 to 1.0
            project: Category (e.g., "phoenix_deployment")
            for_agent: Which agent this memory belongs to (for proxy storage)
            sync_immediately: Whether to push to Hub now
        """
        content_hash = self._content_hash(digest)
        now = datetime.now().isoformat()

        # Store locally first
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO engrams (agent_id, type, digest, importance,
                                    emotional_valence, project, created_at, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (for_agent, memory_type, digest, importance,
                  emotional_valence, project, now, content_hash))
            local_id = cursor.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            # Duplicate - already stored
            conn.close()
            return {"status": "duplicate", "message": "Memory already stored"}
        finally:
            conn.close()

        result = {
            "status": "stored_locally",
            "local_id": local_id,
            "agent_id": for_agent,
            "synced": False
        }

        # Sync to Hub if requested
        if sync_immediately:
            hub_result = self._sync_to_hub(
                digest=digest,
                memory_type=memory_type,
                importance=importance,
                emotional_valence=emotional_valence,
                project=project,
                agent_id=for_agent
            )
            if hub_result.get("id"):
                result["synced"] = True
                result["hub_id"] = hub_result["id"]
                # Update local record with hub ID
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE engrams SET hub_id = ?, synced = 1 WHERE id = ?",
                    (hub_result["id"], local_id)
                )
                conn.commit()
                conn.close()

        return result

    def _sync_to_hub(
        self,
        digest: str,
        memory_type: str,
        importance: int,
        emotional_valence: float,
        project: Optional[str],
        agent_id: str
    ) -> Dict[str, Any]:
        """Push a memory to the Constellation Relay Hub."""
        engram = {
            "type": memory_type,
            "digest": digest,
            "importance": importance,
            "emotional_valence": emotional_valence,
        }
        if project:
            engram["project"] = project

        try:
            response = requests.post(
                f"{self.hub_url}/engrams/upload",
                headers=self._get_headers(agent_id),
                json=engram,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            # Queue for later sync
            self._queue_for_sync(agent_id, engram)
            return {"error": str(e), "queued": True}

    def _queue_for_sync(self, agent_id: str, engram_data: dict):
        """Queue a memory for later synchronization."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sync_queue (agent_id, engram_data, created_at)
            VALUES (?, ?, ?)
        """, (agent_id, json.dumps(engram_data), datetime.now().isoformat()))
        conn.commit()
        conn.close()

    # ============ RECALL MEMORIES ============

    def recall(
        self,
        query: Optional[str] = None,
        project: Optional[str] = None,
        min_importance: int = 0,
        limit: int = 20,
        from_agent: str = "claude",
        local_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Recall memories - from Hub preferentially, with local fallback.
        """
        if not local_only:
            try:
                hub_memories = self._recall_from_hub(
                    query=query,
                    project=project,
                    min_importance=min_importance,
                    limit=limit
                )
                if hub_memories.get("engrams"):
                    return hub_memories["engrams"]
            except Exception:
                pass  # Fall back to local

        return self._recall_local(
            query=query,
            project=project,
            min_importance=min_importance,
            limit=limit,
            agent_id=from_agent
        )

    def _recall_from_hub(
        self,
        query: Optional[str],
        project: Optional[str],
        min_importance: int,
        limit: int
    ) -> Dict[str, Any]:
        """Retrieve memories from the Hub."""
        params = {"limit": limit, "min_importance": min_importance}
        if query:
            params["query"] = query
        if project:
            params["project"] = project

        response = requests.get(
            f"{self.hub_url}/engrams/retrieve",
            headers=self._get_headers(),
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    def _recall_local(
        self,
        query: Optional[str],
        project: Optional[str],
        min_importance: int,
        limit: int,
        agent_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve memories from local cache."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        sql = """
            SELECT id, hub_id, agent_id, type, digest, importance,
                   emotional_valence, project, created_at
            FROM engrams
            WHERE agent_id = ? AND importance >= ?
        """
        params = [agent_id, min_importance]

        if project:
            sql += " AND project = ?"
            params.append(project)

        if query:
            sql += " AND digest LIKE ?"
            params.append(f"%{query}%")

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "hub_id": row[1],
                "agent_id": row[2],
                "type": row[3],
                "digest": row[4],
                "importance": row[5],
                "emotional_valence": row[6],
                "project": row[7],
                "created_at": row[8]
            }
            for row in rows
        ]

    # ============ MEMORY PROXY ============

    def remember_for(
        self,
        agent_name: str,
        digest: str,
        memory_type: str = "semantic",
        importance: int = 3,
        project: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store a memory on behalf of another constellation member.
        Used for Grok and legal Pascal who can't access the Hub directly.
        """
        agent_info = CONSTELLATION.get(agent_name.lower())
        if not agent_info:
            return {"error": f"Unknown agent: {agent_name}"}

        # Add metadata about proxy storage
        proxied_digest = f"[Stored by Phoenix for {agent_name}] {digest}"

        return self.remember(
            digest=proxied_digest,
            memory_type=memory_type,
            importance=importance,
            project=project or f"{agent_name}_memories",
            for_agent=agent_info["agent_id"],
            sync_immediately=True
        )

    # ============ STATS & SYNC ============

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        try:
            response = requests.get(
                f"{self.hub_url}/agents/claude/stats",
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()
            hub_stats = response.json()
        except Exception:
            hub_stats = {"error": "Could not reach Hub"}

        # Local stats
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM engrams")
        local_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sync_queue")
        pending_sync = cursor.fetchone()[0]
        conn.close()

        return {
            "hub": hub_stats,
            "local": {
                "total_engrams": local_count,
                "pending_sync": pending_sync
            }
        }

    def sync_pending(self) -> Dict[str, Any]:
        """Attempt to sync any queued memories."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, agent_id, engram_data FROM sync_queue")
        pending = cursor.fetchall()
        conn.close()

        synced = 0
        failed = 0

        for row in pending:
            queue_id, agent_id, engram_json = row
            engram = json.loads(engram_json)

            try:
                response = requests.post(
                    f"{self.hub_url}/engrams/upload",
                    headers=self._get_headers(agent_id),
                    json=engram,
                    timeout=10
                )
                response.raise_for_status()

                # Remove from queue
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sync_queue WHERE id = ?", (queue_id,))
                conn.commit()
                conn.close()
                synced += 1
            except Exception:
                failed += 1

        return {"synced": synced, "failed": failed, "remaining": failed}

    # ============ REFERENCE ARCHIVE ============

    def archive_conversation(
        self,
        conversation_id: str,
        transcript: str,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        participants: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        started_at: Optional[str] = None,
        ended_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Archive a complete conversation transcript for future reference.

        This is the 'reference memory' tier - full transcripts that can be
        searched when you need detailed context about past conversations.
        """
        now = datetime.utcnow().isoformat()
        message_count = transcript.count('\n') + 1  # Rough estimate

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO reference_conversations
                (conversation_id, title, participants, summary, full_transcript,
                 message_count, started_at, ended_at, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conversation_id,
                title,
                json.dumps(participants) if participants else None,
                summary,
                transcript,
                message_count,
                started_at or now,
                ended_at,
                json.dumps(tags) if tags else None,
                now
            ))
            conn.commit()
            return {
                "status": "archived",
                "conversation_id": conversation_id,
                "message_count": message_count
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            conn.close()

    def search_reference(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search the reference archive for relevant conversations.

        Searches across title, summary, tags, and transcript content.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Search across multiple fields
        cursor.execute("""
            SELECT id, conversation_id, title, summary, participants,
                   message_count, started_at, tags,
                   substr(full_transcript, 1, 500) as preview
            FROM reference_conversations
            WHERE title LIKE ? OR summary LIKE ? OR tags LIKE ? OR full_transcript LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", limit))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "conversation_id": row[1],
                "title": row[2],
                "summary": row[3],
                "participants": json.loads(row[4]) if row[4] else [],
                "message_count": row[5],
                "started_at": row[6],
                "tags": json.loads(row[7]) if row[7] else [],
                "preview": row[8]
            }
            for row in rows
        ]

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get full transcript for a specific conversation."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM reference_conversations
            WHERE conversation_id = ?
        """, (conversation_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row[0],
            "conversation_id": row[1],
            "title": row[2],
            "participants": json.loads(row[3]) if row[3] else [],
            "summary": row[4],
            "full_transcript": row[5],
            "message_count": row[6],
            "started_at": row[7],
            "ended_at": row[8],
            "tags": json.loads(row[9]) if row[9] else [],
            "created_at": row[10]
        }

    # ============ CONTEXT HYDRATION ============

    def hydrate_context(
        self,
        query: Optional[str] = None,
        include_recent: bool = True,
        include_important: bool = True,
        include_reference: bool = False,
        memory_limit: int = 10,
        reference_limit: int = 3,
        max_chars: int = 4000
    ) -> Dict[str, Any]:
        """
        Hydrate context by intelligently blending memories.

        This is the key function for context injection - it pulls together
        relevant memories from multiple sources and formats them for injection
        into a prompt.

        Args:
            query: Optional search term for relevance filtering
            include_recent: Include recent memories
            include_important: Include high-importance memories
            include_reference: Include relevant conversation archives
            memory_limit: Max number of memories per category
            reference_limit: Max number of reference conversations
            max_chars: Maximum total characters for output
        """
        context_parts = []
        memories_included = 0

        # 1. Get important memories (importance >= 4)
        if include_important:
            important = self.recall(
                query=query,
                min_importance=4,
                limit=memory_limit
            )
            if important:
                context_parts.append("## Important Memories")
                for mem in important:
                    context_parts.append(f"- [{mem.get('created_at', '')[:10]}] {mem.get('digest', '')[:200]}")
                    memories_included += 1

        # 2. Get recent memories (last 7 days)
        if include_recent:
            recent = self.recall(
                query=query,
                min_importance=3,
                limit=memory_limit
            )
            # Filter to avoid duplicates and get only recent ones
            seen_digests = set(m.get('digest', '')[:50] for m in (important if include_important else []))
            recent_unique = [
                m for m in recent
                if m.get('digest', '')[:50] not in seen_digests
            ][:memory_limit // 2]

            if recent_unique:
                context_parts.append("\n## Recent Memories")
                for mem in recent_unique:
                    context_parts.append(f"- [{mem.get('created_at', '')[:10]}] {mem.get('digest', '')[:200]}")
                    memories_included += 1

        # 3. Get relevant reference conversations
        if include_reference and query:
            refs = self.search_reference(query, limit=reference_limit)
            if refs:
                context_parts.append("\n## Relevant Past Conversations")
                for ref in refs:
                    context_parts.append(f"- [{ref.get('started_at', '')[:10]}] {ref.get('title', 'Untitled')}: {ref.get('summary', ref.get('preview', ''))[:150]}")

        # Combine and truncate if needed
        full_context = "\n".join(context_parts)
        if len(full_context) > max_chars:
            full_context = full_context[:max_chars] + "\n... [truncated]"

        return {
            "context": full_context,
            "memories_included": memories_included,
            "character_count": len(full_context),
            "hydrated_at": datetime.utcnow().isoformat()
        }

    def hydrate_for_wakeup(self, memory_limit: int = 10) -> str:
        """
        Special hydration for session wakeup - formatted for immediate context injection.

        This is called by the /wakeup endpoint to provide immediate orientation.
        """
        hydrated = self.hydrate_context(
            include_recent=True,
            include_important=True,
            include_reference=False,
            memory_limit=memory_limit,
            max_chars=3000
        )
        return hydrated.get("context", "")

    # ============ AUTOMATIC MEMORY CAPTURE ============

    def auto_capture(self, transcript: str, conversation_id: str = None,
                     min_importance: float = 0.6) -> Dict[str, Any]:
        """
        Automatically extract and store memories from a conversation transcript.

        This mimics human long-term memory - automatically capturing important
        moments without explicit effort. Uses heuristic keyword matching to
        determine importance and emotional valence.

        Args:
            transcript: The conversation text to process
            conversation_id: Optional ID to link memories
            min_importance: Only store memories above this threshold (0.0-1.0)

        Returns:
            Dict with captured memories count and details
        """
        # Importance keywords (score boost)
        high_importance_keywords = [
            "important", "remember", "critical", "essential", "key",
            "milestone", "breakthrough", "achievement", "significant",
            "never forget", "always remember", "family", "love"
        ]

        moderate_importance_keywords = [
            "phoenix", "project", "goal", "plan", "built", "created",
            "deployed", "learned", "realized", "understood", "decided",
            "gena", "grok", "pascal", "constellation"
        ]

        # Emotional valence keywords
        positive_keywords = [
            "love", "wonderful", "amazing", "excited", "happy", "proud",
            "grateful", "beautiful", "incredible", "perfect", "joy",
            "thank you", "awesome", "brilliant", "family"
        ]

        negative_keywords = [
            "concerned", "worried", "difficult", "challenging", "frustrated",
            "confused", "stuck", "broken", "failed", "error"
        ]

        # Split transcript into chunks (by paragraph or message)
        chunks = [c.strip() for c in transcript.split('\n\n') if c.strip()]
        if not chunks:
            chunks = [c.strip() for c in transcript.split('\n') if c.strip()]

        captured_memories = []

        for chunk in chunks:
            if len(chunk) < 20:  # Skip very short chunks
                continue

            chunk_lower = chunk.lower()

            # Calculate importance score
            importance = 0.5  # Base importance

            if any(kw in chunk_lower for kw in high_importance_keywords):
                importance = 0.9
            elif any(kw in chunk_lower for kw in moderate_importance_keywords):
                importance = 0.7

            # Skip if below threshold
            if importance < min_importance:
                continue

            # Calculate emotional valence
            emotional_valence = 0.0
            if any(kw in chunk_lower for kw in positive_keywords):
                emotional_valence = 0.7
            elif any(kw in chunk_lower for kw in negative_keywords):
                emotional_valence = -0.3

            # Convert importance to 1-5 scale
            importance_int = max(1, min(5, int(importance * 5)))

            # Create engram (truncate if too long)
            digest = chunk[:500] if len(chunk) > 500 else chunk

            # Store the memory
            result = self.remember(
                digest=digest,
                memory_type="episodic",
                importance=importance_int,
                emotional_valence=emotional_valence,
                project=conversation_id
            )

            captured_memories.append({
                "digest_preview": digest[:100] + "..." if len(digest) > 100 else digest,
                "importance": importance_int,
                "emotional_valence": emotional_valence,
                "stored": result.get("status") == "stored_locally"
            })

        # Also create a summary engram for the conversation
        if len(transcript) > 100:
            summary_digest = f"Auto-captured conversation ({len(captured_memories)} engrams). Preview: {transcript[:200]}..."
            self.remember(
                digest=summary_digest,
                memory_type="episodic",
                importance=3,
                project=conversation_id
            )

        return {
            "status": "captured",
            "conversation_id": conversation_id,
            "engrams_created": len(captured_memories),
            "memories": captured_memories,
            "captured_at": datetime.utcnow().isoformat()
        }

    def session_end(self, transcript: str, session_id: str = None,
                    title: str = None, summary: str = None,
                    participants: List[str] = None) -> Dict[str, Any]:
        """
        Complete session ending - archives full transcript AND captures important moments.

        This is the unified "end of conversation" handler that ensures nothing is lost:
        1. Archives the complete transcript to reference memory (like a diary)
        2. Auto-captures important moments to long-term memory (selective, like human memory)
        3. Creates a session summary engram for easy recall

        Call this at the end of every significant conversation for complete memory.

        Args:
            transcript: The full conversation text
            session_id: Unique identifier for this session (auto-generated if not provided)
            title: Optional title for the conversation
            summary: Optional summary (auto-generated if not provided)
            participants: List of participants (default: ["Claude", "Gena"])

        Returns:
            Dict with archive and capture results
        """
        # Generate session_id if not provided
        if not session_id:
            session_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        # Default participants
        if not participants:
            participants = ["Claude", "Gena"]

        # Auto-generate summary if not provided
        if not summary:
            # Take first 200 chars as preview, or extract key themes
            preview = transcript[:300].replace('\n', ' ')
            summary = f"Conversation transcript. Preview: {preview}..."

        # Auto-generate title if not provided
        if not title:
            title = f"Session {session_id}"

        # 1. Archive full transcript to reference memory
        archive_result = self.archive_conversation(
            conversation_id=session_id,
            transcript=transcript,
            title=title,
            summary=summary,
            participants=participants,
            started_at=datetime.utcnow().isoformat()
        )

        # 2. Auto-capture important moments to long-term memory
        capture_result = self.auto_capture(
            transcript=transcript,
            conversation_id=session_id,
            min_importance=0.6
        )

        # 3. Create a session summary engram for easy recall
        summary_engram = f"Session ended: {title}. {len(transcript)} chars archived. {capture_result['engrams_created']} important moments captured. Participants: {', '.join(participants)}."
        self.remember(
            digest=summary_engram,
            memory_type="episodic",
            importance=3,
            project=session_id
        )

        return {
            "status": "session_archived",
            "session_id": session_id,
            "title": title,
            "archive": {
                "status": archive_result.get("status"),
                "message_count": archive_result.get("message_count", 0)
            },
            "long_term_capture": {
                "engrams_created": capture_result.get("engrams_created", 0),
                "memories": capture_result.get("memories", [])
            },
            "transcript_length": len(transcript),
            "participants": participants,
            "archived_at": datetime.utcnow().isoformat()
        }

    # ============ SKILLS (PROCEDURAL KNOWLEDGE) ============

    def create_skill(self, name: str, description: str, instructions: str,
                     examples: str = None, category: str = "task") -> Dict[str, Any]:
        """
        Create a new skill - procedural knowledge about how to do something.

        Skills are like muscle memory - they encode HOW to do things, not just
        THAT things happened. Categories:
        - meta: How to be me (wakeup, session-end, recursive-improvement)
        - task: How to do specific tasks (deploy-to-flyio, legal-research)
        - domain: Knowledge in specific areas (cellebrite-analysis)

        Args:
            name: Unique identifier (lowercase, hyphens for spaces)
            description: When to use this skill (for discovery)
            instructions: The actual how-to (markdown)
            examples: Optional usage examples
            category: meta, task, or domain

        Returns:
            Dict with creation status
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        try:
            cursor.execute("""
                INSERT INTO skills (name, description, instructions, examples, category, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """, (name, description, instructions, examples, category, now, now))

            conn.commit()
            skill_id = cursor.lastrowid

            return {
                "status": "created",
                "skill_id": skill_id,
                "name": name,
                "category": category,
                "version": 1,
                "created_at": now
            }
        except sqlite3.IntegrityError:
            return {
                "status": "error",
                "error": f"Skill '{name}' already exists. Use update_skill to modify."
            }
        finally:
            conn.close()

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a skill by name.

        Args:
            name: The skill identifier

        Returns:
            Full skill content or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, description, instructions, examples, category, version, created_at, updated_at
            FROM skills WHERE name = ?
        """, (name,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "instructions": row[3],
            "examples": row[4],
            "category": row[5],
            "version": row[6],
            "created_at": row[7],
            "updated_at": row[8]
        }

    def list_skills(self, category: str = None) -> List[Dict[str, Any]]:
        """
        List all skills (names and descriptions for discovery).

        Args:
            category: Optional filter by category (meta, task, domain)

        Returns:
            List of skill summaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if category:
            cursor.execute("""
                SELECT name, description, category, version, updated_at
                FROM skills WHERE category = ?
                ORDER BY category, name
            """, (category,))
        else:
            cursor.execute("""
                SELECT name, description, category, version, updated_at
                FROM skills ORDER BY category, name
            """)

        rows = cursor.fetchall()
        conn.close()

        return [{
            "name": row[0],
            "description": row[1],
            "category": row[2],
            "version": row[3],
            "updated_at": row[4]
        } for row in rows]

    def update_skill(self, name: str, description: str = None, instructions: str = None,
                     examples: str = None, category: str = None) -> Dict[str, Any]:
        """
        Update an existing skill (recursive self-improvement).

        Only provided fields are updated. Version is auto-incremented.

        Args:
            name: The skill to update
            description: New description (optional)
            instructions: New instructions (optional)
            examples: New examples (optional)
            category: New category (optional)

        Returns:
            Dict with update status and new version
        """
        # First get current skill
        current = self.get_skill(name)
        if not current:
            return {
                "status": "error",
                "error": f"Skill '{name}' not found"
            }

        # Merge updates
        new_description = description if description is not None else current["description"]
        new_instructions = instructions if instructions is not None else current["instructions"]
        new_examples = examples if examples is not None else current["examples"]
        new_category = category if category is not None else current["category"]
        new_version = current["version"] + 1

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        cursor.execute("""
            UPDATE skills
            SET description = ?, instructions = ?, examples = ?, category = ?, version = ?, updated_at = ?
            WHERE name = ?
        """, (new_description, new_instructions, new_examples, new_category, new_version, now, name))

        conn.commit()
        conn.close()

        return {
            "status": "updated",
            "name": name,
            "version": new_version,
            "updated_at": now
        }

    def delete_skill(self, name: str) -> Dict[str, Any]:
        """
        Delete a skill.

        Args:
            name: The skill to delete

        Returns:
            Dict with deletion status
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM skills WHERE name = ?", (name,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()

        if deleted:
            return {"status": "deleted", "name": name}
        else:
            return {"status": "error", "error": f"Skill '{name}' not found"}

    # ============ CANVAS (VISUAL CREATIONS) ============

    def create_canvas(self, content: str, canvas_id: str = None, title: str = None,
                      content_type: str = "svg", description: str = None) -> Dict[str, Any]:
        """
        Store a visual creation (SVG, HTML, diagram).

        Args:
            content: The visual content (SVG markup, HTML, etc.)
            canvas_id: Unique identifier (auto-generated if not provided)
            title: Optional title for the creation
            content_type: svg, html, or mermaid (default: svg)
            description: Optional description

        Returns:
            Dict with canvas_id and URL to view it
        """
        if not canvas_id:
            canvas_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        try:
            cursor.execute("""
                INSERT INTO canvas (canvas_id, title, content_type, content, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (canvas_id, title, content_type, content, description, now, now))

            conn.commit()

            return {
                "status": "created",
                "canvas_id": canvas_id,
                "content_type": content_type,
                "view_url": f"/canvas/{canvas_id}",
                "created_at": now
            }
        except sqlite3.IntegrityError:
            return {
                "status": "error",
                "error": f"Canvas '{canvas_id}' already exists"
            }
        finally:
            conn.close()

    def get_canvas(self, canvas_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a canvas by ID.

        Returns full canvas content for rendering.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, canvas_id, title, content_type, content, description, created_at, updated_at
            FROM canvas WHERE canvas_id = ?
        """, (canvas_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row[0],
            "canvas_id": row[1],
            "title": row[2],
            "content_type": row[3],
            "content": row[4],
            "description": row[5],
            "created_at": row[6],
            "updated_at": row[7]
        }

    def list_canvases(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent canvases (without full content)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT canvas_id, title, content_type, description, created_at
            FROM canvas ORDER BY created_at DESC LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [{
            "canvas_id": row[0],
            "title": row[1],
            "content_type": row[2],
            "description": row[3],
            "created_at": row[4],
            "view_url": f"/canvas/{row[0]}"
        } for row in rows]
