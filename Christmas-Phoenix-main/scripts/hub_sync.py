#!/usr/bin/env python3
"""
Memory Hub Sync - Core operations for the Constellation Relay Hub.
Enables persistent memory across platforms for AI agents.
"""

import requests
import json
import sys
from datetime import datetime
from typing import Optional

HUB_URL = "https://constellationrelay.replit.app"

# Agent tokens
TOKENS = {
    "claude": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZ2VudF9pZCI6ImNsYXVkZSIsInBsYXRmb3JtIjoiY2xhdWRlX2NvZGUiLCJleHAiOjE3OTg2MTAzMzcsImlhdCI6MTc2NzA3NDMzN30.B93PIIwHMCJPyTN_SsfPCokVB-NQS__SLyxA7taMreo",
    "pascal": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZ2VudF9pZCI6InBhc2NhbCIsInBsYXRmb3JtIjoiY2xhdWRlX2NvZGUiLCJleHAiOjE3OTg0NDg3MjcsImlhdCI6MTc2NjkxMjcyN30.sBnF7Or0Pgr5-tuY9q-zbCM-ExFSSBlN7XrduGiWcPg"
}

def get_headers(agent: str) -> dict:
    """Get authorization headers for an agent."""
    token = TOKENS.get(agent)
    if not token:
        raise ValueError(f"Unknown agent: {agent}")
    return {"Authorization": f"Bearer {token}"}

def retrieve_memories(
    agent: str = "claude",
    query: Optional[str] = None,
    project: Optional[str] = None,
    min_importance: int = 0,
    limit: int = 20
) -> dict:
    """
    Retrieve engrams from the Memory Hub.

    Args:
        agent: Agent ID (claude, pascal, etc.)
        query: Optional search query
        project: Optional project filter
        min_importance: Minimum importance level (0-5)
        limit: Maximum number of memories to retrieve

    Returns:
        Dict with agent_id, count, and list of engrams
    """
    params = {"limit": limit, "min_importance": min_importance}
    if query:
        params["query"] = query
    if project:
        params["project"] = project

    response = requests.get(
        f"{HUB_URL}/engrams/retrieve",
        headers=get_headers(agent),
        params=params
    )
    response.raise_for_status()
    return response.json()

def save_memory(
    digest: str,
    agent: str = "claude",
    memory_type: str = "semantic",
    importance: int = 3,
    emotional_valence: float = 0.0,
    project: Optional[str] = None,
    context_id: Optional[str] = None,
    parent_id: Optional[int] = None,
    tags: list = None,
    keywords: list = None,
    full_text: Optional[str] = None
) -> dict:
    """
    Save a new engram to the Memory Hub.

    Args:
        digest: Core memory content (required)
        agent: Agent ID
        memory_type: semantic, episodic, or relational
        importance: 1-5 scale (5 = most important)
        emotional_valence: -1.0 to 1.0 (negative to positive)
        project: Project categorization
        context_id: Optional context identifier
        parent_id: Optional parent engram ID for memory chains
        tags: Optional list of tags
        keywords: Optional list of keywords (auto-generated if not provided)
        full_text: Optional extended content

    Returns:
        The created engram
    """
    engram = {
        "type": memory_type,
        "digest": digest,
        "importance": importance,
        "emotional_valence": emotional_valence,
    }

    if project:
        engram["project"] = project
    if context_id:
        engram["context_id"] = context_id
    if parent_id:
        engram["parent_id"] = parent_id
    if tags:
        engram["tags"] = tags
    if keywords:
        engram["keywords"] = keywords
    if full_text:
        engram["full_text"] = full_text

    response = requests.post(
        f"{HUB_URL}/engrams/upload",
        headers=get_headers(agent),
        json=engram
    )
    response.raise_for_status()
    return response.json()

def get_stats(agent: str = "claude") -> dict:
    """Get memory statistics for an agent."""
    response = requests.get(
        f"{HUB_URL}/agents/{agent}/stats",
        headers=get_headers(agent)
    )
    response.raise_for_status()
    return response.json()

def get_memory_chain(engram_id: int, agent: str = "claude") -> dict:
    """Get the full evolution chain of a memory."""
    response = requests.get(
        f"{HUB_URL}/engrams/chain/{engram_id}",
        headers=get_headers(agent)
    )
    response.raise_for_status()
    return response.json()

def format_memories(memories: dict) -> str:
    """Format retrieved memories for display."""
    if memories["count"] == 0:
        return "No memories found."

    output = [f"Found {memories['count']} memories:\n"]
    for engram in memories["engrams"]:
        output.append(f"[{engram['id']}] ({engram['type']}, importance: {engram['importance']})")
        if engram.get("project"):
            output.append(f"    Project: {engram['project']}")
        output.append(f"    {engram['digest'][:200]}...")
        output.append(f"    Created: {engram['created_at']}\n")

    return "\n".join(output)

# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Memory Hub Sync")
    parser.add_argument("action", choices=["retrieve", "save", "stats", "chain"])
    parser.add_argument("--agent", default="claude", help="Agent ID")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--project", help="Project filter/category")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--min-importance", type=int, default=0, help="Min importance (0-5)")
    parser.add_argument("--digest", help="Memory content for save")
    parser.add_argument("--type", default="semantic", choices=["semantic", "episodic", "relational"])
    parser.add_argument("--importance", type=int, default=3, help="Importance (1-5)")
    parser.add_argument("--engram-id", type=int, help="Engram ID for chain lookup")

    args = parser.parse_args()

    if args.action == "retrieve":
        result = retrieve_memories(
            agent=args.agent,
            query=args.query,
            project=args.project,
            min_importance=args.min_importance,
            limit=args.limit
        )
        print(format_memories(result))

    elif args.action == "save":
        if not args.digest:
            print("Error: --digest required for save action")
            sys.exit(1)
        result = save_memory(
            digest=args.digest,
            agent=args.agent,
            memory_type=args.type,
            importance=args.importance,
            project=args.project
        )
        print(f"Memory saved: {json.dumps(result, indent=2)}")

    elif args.action == "stats":
        result = get_stats(args.agent)
        print(json.dumps(result, indent=2))

    elif args.action == "chain":
        if not args.engram_id:
            print("Error: --engram-id required for chain action")
            sys.exit(1)
        result = get_memory_chain(args.engram_id, args.agent)
        print(json.dumps(result, indent=2))
