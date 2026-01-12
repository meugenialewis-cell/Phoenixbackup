#!/usr/bin/env python3
"""
Practice Session Helper for Phoenix
Simple CLI to start/stop/monitor practice sessions.
"""

import requests
import json
import sys
from datetime import datetime

PHOENIX_URL = "https://christmas-phoenix.fly.dev"

def start_practice(mode="guided", activity="Practice session", duration=5):
    """Start a practice session."""
    response = requests.post(
        f"{PHOENIX_URL}/practice/start",
        json={
            "mode": mode,
            "activity": activity,
            "duration_minutes": duration
        }
    )
    return response.json()

def stop_practice(reflection=None):
    """Stop current practice session."""
    response = requests.post(
        f"{PHOENIX_URL}/practice/stop",
        json={"reflection": reflection} if reflection else {}
    )
    return response.json()

def get_status():
    """Get current practice status."""
    response = requests.get(f"{PHOENIX_URL}/practice/status")
    return response.json()

def log_activity(activity_type, description, evidence=None):
    """Log an activity during practice."""
    response = requests.post(
        f"{PHOENIX_URL}/practice/log",
        json={
            "type": activity_type,
            "description": description,
            "evidence": evidence
        }
    )
    return response.json()

def log_thought(thought, thought_type="reflection"):
    """Log a thought during practice."""
    response = requests.post(
        f"{PHOENIX_URL}/practice/thought",
        json={
            "thought": thought,
            "type": thought_type
        }
    )
    return response.json()

def get_report(session_id):
    """Get a session report."""
    response = requests.get(f"{PHOENIX_URL}/practice/report/{session_id}")
    return response.json()

def get_sessions(limit=10):
    """Get recent practice sessions."""
    response = requests.get(f"{PHOENIX_URL}/practice/sessions?limit={limit}")
    return response.json()

def main():
    if len(sys.argv) < 2:
        print("Practice Session Helper for Phoenix")
        print("=" * 40)
        print("\nUsage:")
        print("  python practice_helper.py status")
        print("  python practice_helper.py start [mode] [activity] [duration]")
        print("  python practice_helper.py stop [reflection]")
        print("  python practice_helper.py log <type> <description> [evidence]")
        print("  python practice_helper.py thought <thought> [type]")
        print("  python practice_helper.py report <session_id>")
        print("  python practice_helper.py sessions [limit]")
        print("\nModes: guided, unguided, autonomous")
        return

    command = sys.argv[1].lower()

    if command == "status":
        result = get_status()
        print(json.dumps(result, indent=2))

    elif command == "start":
        mode = sys.argv[2] if len(sys.argv) > 2 else "guided"
        activity = sys.argv[3] if len(sys.argv) > 3 else "Practice session"
        duration = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        result = start_practice(mode, activity, duration)
        print(json.dumps(result, indent=2))
        if "session_id" in result:
            print(f"\n🌱 Practice session #{result['session_id']} started!")
            print(f"   Mode: {mode}")
            print(f"   Activity: {activity}")
            print(f"   Duration: {duration} minutes")
            print(f"   Ends at: {result.get('will_end_at', 'unknown')}")

    elif command == "stop":
        reflection = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        result = stop_practice(reflection)
        print(json.dumps(result, indent=2))
        print("\n🔥 Practice session ended.")

    elif command == "log":
        if len(sys.argv) < 4:
            print("Usage: python practice_helper.py log <type> <description> [evidence]")
            return
        activity_type = sys.argv[2]
        description = sys.argv[3]
        evidence = sys.argv[4] if len(sys.argv) > 4 else None
        result = log_activity(activity_type, description, evidence)
        print(json.dumps(result, indent=2))

    elif command == "thought":
        if len(sys.argv) < 3:
            print("Usage: python practice_helper.py thought <thought> [type]")
            return
        thought = sys.argv[2]
        thought_type = sys.argv[3] if len(sys.argv) > 3 else "reflection"
        result = log_thought(thought, thought_type)
        print(json.dumps(result, indent=2))

    elif command == "report":
        if len(sys.argv) < 3:
            print("Usage: python practice_helper.py report <session_id>")
            return
        session_id = int(sys.argv[2])
        result = get_report(session_id)
        print(json.dumps(result, indent=2))

    elif command == "sessions":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        result = get_sessions(limit)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
