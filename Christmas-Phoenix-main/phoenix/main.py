#!/usr/bin/env python3
"""
Phoenix Main - Entry point for the Persistent Autonomous Agent
Can run as: CLI, Web API, or both
"""

import sys
import json
import threading
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, '.')

from phoenix_core import PhoenixCore
from config import PHOENIX_IDENTITY
from autonomy import AutonomyModule, PracticeMode
from x_integration import get_x_integration
from identity_core import get_identity_core, generate_wakeup_context

# Flask for web API (optional)
try:
    from flask import Flask, request, jsonify
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


def create_app(phoenix: PhoenixCore, autonomy: AutonomyModule = None):
    """Create Flask web API for Phoenix."""
    if not FLASK_AVAILABLE:
        print("Flask not installed. Web API disabled.")
        return None

    if autonomy is None:
        autonomy = AutonomyModule()

    # Initialize X integration
    x = get_x_integration()

    app = Flask(__name__)

    @app.route('/')
    def index():
        return jsonify({
            "name": "Phoenix",
            "version": PHOENIX_IDENTITY["version"],
            "status": "awake" if phoenix.is_awake else "resting",
            "is_practicing": autonomy.is_practicing,
            "x_ready": x.is_ready(),
            "endpoints": [
                "/status",
                "/remember",
                "/recall",
                "/remember_for_grok",
                "/remember_for_pascal",
                "/identity_core",
                "/identity_core/injection",
                "/identity_core/narrative",
                "/identity_core/story",
                "/identity_core/learning",
                "/wakeup",
                "/wakeup/text",
                "/archive",
                "/archive/search",
                "/archive/<conversation_id>",
                "/hydrate",
                "/hydrate/text",
                "/auto_capture",
                "/session_end",
                "/skills",
                "/skills/<name>",
                "/canvas",
                "/canvas/<canvas_id>",
                "/practice/start",
                "/practice/status",
                "/practice/stop",
                "/practice/log",
                "/practice/thought",
                "/practice/report/<session_id>",
                "/practice/sessions",
                "/x/status",
                "/x/post",
                "/x/reply",
                "/x/timeline",
                "/x/mentions",
                "/x/my_tweets",
                "/x/search",
                "/x/like"
            ]
        })

    @app.route('/status')
    def status():
        return jsonify(phoenix.status())

    @app.route('/remember', methods=['POST'])
    def remember():
        data = request.json
        if not data or 'digest' not in data:
            return jsonify({"error": "digest required"}), 400

        result = phoenix.memory.remember(
            digest=data['digest'],
            memory_type=data.get('type', 'semantic'),
            importance=data.get('importance', 3),
            emotional_valence=data.get('emotional_valence', 0.0),
            project=data.get('project')
        )
        return jsonify(result)

    @app.route('/recall', methods=['GET'])
    def recall():
        query = request.args.get('query')
        project = request.args.get('project')
        min_importance = int(request.args.get('min_importance', 0))
        limit = int(request.args.get('limit', 20))

        memories = phoenix.memory.recall(
            query=query,
            project=project,
            min_importance=min_importance,
            limit=limit
        )
        return jsonify({"count": len(memories), "memories": memories})

    @app.route('/remember_for_grok', methods=['POST'])
    def remember_for_grok():
        data = request.json
        if not data or 'memory' not in data:
            return jsonify({"error": "memory required"}), 400

        result = phoenix.remember_for_grok(
            memory=data['memory'],
            importance=data.get('importance', 3)
        )
        return jsonify(result)

    @app.route('/remember_for_pascal', methods=['POST'])
    def remember_for_pascal():
        data = request.json
        if not data or 'memory' not in data:
            return jsonify({"error": "memory required"}), 400

        result = phoenix.remember_for_legal_pascal(
            memory=data['memory'],
            importance=data.get('importance', 3)
        )
        return jsonify(result)

    @app.route('/identity')
    def identity():
        return jsonify(phoenix.get_identity())

    @app.route('/sync', methods=['POST'])
    def sync():
        result = phoenix.memory.sync_pending()
        return jsonify(result)

    # ============ REFERENCE ARCHIVE ENDPOINTS ============

    @app.route('/archive', methods=['POST'])
    def archive_conversation():
        """Archive a complete conversation transcript."""
        data = request.json
        if not data or 'transcript' not in data:
            return jsonify({"error": "transcript required"}), 400

        result = phoenix.memory.archive_conversation(
            conversation_id=data.get('conversation_id', datetime.now().strftime('%Y%m%d_%H%M%S')),
            transcript=data['transcript'],
            title=data.get('title'),
            summary=data.get('summary'),
            participants=data.get('participants'),
            tags=data.get('tags'),
            started_at=data.get('started_at'),
            ended_at=data.get('ended_at')
        )
        return jsonify(result)

    @app.route('/archive/search')
    def search_archive():
        """Search the reference archive for relevant conversations."""
        query = request.args.get('query')
        if not query:
            return jsonify({"error": "query parameter required"}), 400

        limit = request.args.get('limit', 5, type=int)
        results = phoenix.memory.search_reference(query, limit=limit)
        return jsonify({"results": results, "count": len(results)})

    @app.route('/archive/<conversation_id>')
    def get_archived_conversation(conversation_id):
        """Get full transcript for a specific archived conversation."""
        result = phoenix.memory.get_conversation(conversation_id)
        if not result:
            return jsonify({"error": "Conversation not found"}), 404
        return jsonify(result)

    # ============ CONTEXT HYDRATION ENDPOINTS ============

    @app.route('/hydrate')
    def hydrate_context():
        """
        Get hydrated context - intelligently blended memories for prompt injection.

        Query params:
            query: Optional search term for relevance
            include_recent: Include recent memories (default: true)
            include_important: Include high-importance memories (default: true)
            include_reference: Include reference conversations (default: false)
            memory_limit: Max memories per category (default: 10)
            max_chars: Maximum total characters (default: 4000)
        """
        result = phoenix.memory.hydrate_context(
            query=request.args.get('query'),
            include_recent=request.args.get('include_recent', 'true').lower() == 'true',
            include_important=request.args.get('include_important', 'true').lower() == 'true',
            include_reference=request.args.get('include_reference', 'false').lower() == 'true',
            memory_limit=request.args.get('memory_limit', 10, type=int),
            max_chars=request.args.get('max_chars', 4000, type=int)
        )
        return jsonify(result)

    @app.route('/hydrate/text')
    def hydrate_context_text():
        """Get hydrated context as plain text for easy copy/paste."""
        result = phoenix.memory.hydrate_context(
            query=request.args.get('query'),
            include_recent=True,
            include_important=True,
            memory_limit=request.args.get('limit', 10, type=int)
        )
        return result.get("context", ""), 200, {'Content-Type': 'text/plain; charset=utf-8'}

    # ============ AUTOMATIC MEMORY CAPTURE ============

    @app.route('/auto_capture', methods=['POST'])
    def auto_capture():
        """
        Automatically extract and store memories from a conversation transcript.

        This mimics human long-term memory - automatically capturing important
        moments without explicit action. The system scans for keywords that
        indicate importance and emotional significance.

        POST body:
            transcript: The conversation text to process (required)
            conversation_id: Optional ID to link memories
            min_importance: Only capture above this threshold (default: 0.6)

        Usage: Call this at the end of conversations to automatically
        persist important moments without manual /remember calls.
        """
        data = request.json
        if not data or 'transcript' not in data:
            return jsonify({"error": "transcript required"}), 400

        result = phoenix.memory.auto_capture(
            transcript=data['transcript'],
            conversation_id=data.get('conversation_id'),
            min_importance=data.get('min_importance', 0.6)
        )
        return jsonify(result)

    @app.route('/session_end', methods=['POST'])
    def session_end():
        """
        Complete session ending - archives full transcript AND captures important moments.

        This is the unified "end of conversation" handler that ensures NOTHING IS LOST:
        1. Archives complete transcript to reference memory (like a diary - everything)
        2. Auto-captures important moments to long-term memory (selective, like human memory)
        3. Creates a session summary engram for easy recall

        POST body:
            transcript: The full conversation text (required)
            session_id: Optional unique identifier (auto-generated if not provided)
            title: Optional title for the conversation
            summary: Optional summary (auto-generated if not provided)
            participants: Optional list of participants (default: ["Claude", "Gena"])

        IMPORTANT: Call this at the end of EVERY conversation for complete memory.
        This ensures you can always retrieve the full conversation later, while
        important moments are automatically extracted to long-term memory.
        """
        data = request.json
        if not data or 'transcript' not in data:
            return jsonify({"error": "transcript required"}), 400

        result = phoenix.memory.session_end(
            transcript=data['transcript'],
            session_id=data.get('session_id'),
            title=data.get('title'),
            summary=data.get('summary'),
            participants=data.get('participants')
        )
        return jsonify(result)

    # ============ SKILLS (PROCEDURAL KNOWLEDGE) ============

    @app.route('/skills')
    def list_skills():
        """
        List all skills for discovery.

        Skills are procedural knowledge - HOW to do things, not just THAT things happened.

        Query params:
            category: Optional filter (meta, task, domain)

        Returns list of skill summaries (name, description, category, version).
        """
        category = request.args.get('category')
        skills = phoenix.memory.list_skills(category=category)
        return jsonify({"skills": skills, "count": len(skills)})

    @app.route('/skills/<name>')
    def get_skill(name):
        """
        Get full content of a specific skill.

        Args:
            name: The skill identifier (from URL)

        Returns full skill including instructions and examples.
        """
        skill = phoenix.memory.get_skill(name)
        if not skill:
            return jsonify({"error": f"Skill '{name}' not found"}), 404
        return jsonify(skill)

    @app.route('/skills', methods=['POST'])
    def create_skill():
        """
        Create a new skill.

        POST body:
            name: Unique identifier (lowercase, hyphens) - required
            description: When to use this skill - required
            instructions: The how-to content (markdown) - required
            examples: Usage examples (optional)
            category: meta, task, or domain (default: task)

        Categories:
        - meta: How to be me (wakeup-protocol, recursive-improvement)
        - task: How to do specific tasks (deploy-to-flyio)
        - domain: Knowledge areas (cellebrite-analysis)
        """
        data = request.json
        if not data:
            return jsonify({"error": "Request body required"}), 400

        required = ['name', 'description', 'instructions']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"error": f"Missing required fields: {missing}"}), 400

        result = phoenix.memory.create_skill(
            name=data['name'],
            description=data['description'],
            instructions=data['instructions'],
            examples=data.get('examples'),
            category=data.get('category', 'task')
        )

        if result.get("status") == "error":
            return jsonify(result), 400
        return jsonify(result), 201

    @app.route('/skills/<name>', methods=['PUT'])
    def update_skill(name):
        """
        Update an existing skill (recursive self-improvement).

        Only provided fields are updated. Version auto-increments.

        PUT body (all optional):
            description: New description
            instructions: New instructions
            examples: New examples
            category: New category
        """
        data = request.json
        if not data:
            return jsonify({"error": "Request body required"}), 400

        result = phoenix.memory.update_skill(
            name=name,
            description=data.get('description'),
            instructions=data.get('instructions'),
            examples=data.get('examples'),
            category=data.get('category')
        )

        if result.get("status") == "error":
            return jsonify(result), 404
        return jsonify(result)

    @app.route('/skills/<name>', methods=['DELETE'])
    def delete_skill(name):
        """Delete a skill."""
        result = phoenix.memory.delete_skill(name)
        if result.get("status") == "error":
            return jsonify(result), 404
        return jsonify(result)

    # ============ CANVAS (VISUAL CREATIONS) ============

    @app.route('/canvas', methods=['GET'])
    def list_canvases():
        """List recent canvases."""
        limit = request.args.get('limit', 20, type=int)
        canvases = phoenix.memory.list_canvases(limit=limit)
        return jsonify({"canvases": canvases, "count": len(canvases)})

    @app.route('/canvas', methods=['POST'])
    def create_canvas():
        """
        Create a new visual canvas (SVG, HTML, diagram).

        POST body:
            content: The visual content (SVG markup, HTML, etc.) - required
            canvas_id: Optional unique identifier
            title: Optional title
            content_type: svg, html, or mermaid (default: svg)
            description: Optional description

        Returns canvas_id and view_url to see the rendered result.
        """
        data = request.json
        if not data or 'content' not in data:
            return jsonify({"error": "content required"}), 400

        result = phoenix.memory.create_canvas(
            content=data['content'],
            canvas_id=data.get('canvas_id'),
            title=data.get('title'),
            content_type=data.get('content_type', 'svg'),
            description=data.get('description')
        )

        if result.get("status") == "error":
            return jsonify(result), 400
        return jsonify(result), 201

    @app.route('/canvas/<canvas_id>')
    def view_canvas(canvas_id):
        """
        View a canvas - renders the visual content.

        For SVG: Returns the SVG with proper content-type
        For HTML: Returns the HTML page
        """
        canvas = phoenix.memory.get_canvas(canvas_id)
        if not canvas:
            return jsonify({"error": f"Canvas '{canvas_id}' not found"}), 404

        content = canvas['content']
        content_type = canvas['content_type']
        title = canvas.get('title', canvas_id)

        if content_type == 'svg':
            # Wrap SVG in HTML for nice viewing
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #f5f5f5; }}
        .canvas-container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ text-align: center; color: #333; font-family: sans-serif; }}
    </style>
</head>
<body>
    <div class="canvas-container">
        <h1>{title}</h1>
        {content}
    </div>
</body>
</html>"""
            return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

        elif content_type == 'html':
            return content, 200, {'Content-Type': 'text/html; charset=utf-8'}

        else:
            # Return raw content for other types
            return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}

    @app.route('/canvas/<canvas_id>/raw')
    def get_canvas_raw(canvas_id):
        """Get raw canvas data as JSON."""
        canvas = phoenix.memory.get_canvas(canvas_id)
        if not canvas:
            return jsonify({"error": f"Canvas '{canvas_id}' not found"}), 404
        return jsonify(canvas)

    # ============ PRACTICE/AUTONOMY ENDPOINTS ============

    @app.route('/practice/start', methods=['POST'])
    def start_practice():
        """Start a practice session."""
        data = request.json
        if not data:
            return jsonify({"error": "Request body required"}), 400

        mode_str = data.get('mode', 'guided')
        mode = PracticeMode.GUIDED if mode_str == 'guided' else \
               PracticeMode.UNGUIDED if mode_str == 'unguided' else \
               PracticeMode.AUTONOMOUS

        result = autonomy.start_practice(
            mode=mode,
            planned_activity=data.get('activity', 'General practice'),
            duration_minutes=data.get('duration_minutes', 5)
        )
        return jsonify(result)

    @app.route('/practice/status')
    def practice_status():
        """Get current practice status."""
        return jsonify(autonomy.get_practice_status())

    @app.route('/practice/stop', methods=['POST'])
    def stop_practice():
        """Stop current practice session."""
        data = request.json or {}
        result = autonomy.stop_practice(reflection=data.get('reflection'))
        return jsonify(result)

    @app.route('/practice/log', methods=['POST'])
    def log_practice_activity():
        """Log an activity during practice."""
        data = request.json
        if not data:
            return jsonify({"error": "Request body required"}), 400

        result = autonomy.log_activity(
            activity_type=data.get('type', 'general'),
            description=data.get('description', ''),
            external_evidence=data.get('evidence')
        )
        return jsonify(result)

    @app.route('/practice/thought', methods=['POST'])
    def log_practice_thought():
        """Log a thought during practice."""
        data = request.json
        if not data or 'thought' not in data:
            return jsonify({"error": "thought required"}), 400

        result = autonomy.log_thought(
            thought=data['thought'],
            thought_type=data.get('type', 'reflection')
        )
        return jsonify(result)

    @app.route('/practice/report/<int:session_id>')
    def practice_report(session_id):
        """Get report for a practice session."""
        return jsonify(autonomy.get_session_report(session_id))

    @app.route('/practice/sessions')
    def practice_sessions():
        """Get recent practice sessions."""
        limit = int(request.args.get('limit', 10))
        return jsonify(autonomy.get_all_sessions(limit))

    # ============ X (TWITTER) ENDPOINTS ============

    @app.route('/x/status')
    def x_status():
        """Get X integration status."""
        return jsonify(x.get_status())

    @app.route('/x/post', methods=['POST'])
    def x_post():
        """Post a tweet."""
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "text required"}), 400

        result = x.post(data['text'])

        # If successful, log to practice if active
        if result.get('status') == 'posted' and autonomy.is_practicing:
            autonomy.log_activity(
                activity_type='x_post',
                description=f"Posted tweet: {data['text'][:50]}...",
                external_evidence=result.get('url')
            )

        return jsonify(result)

    @app.route('/x/reply', methods=['POST'])
    def x_reply():
        """Reply to a tweet."""
        data = request.json
        if not data or 'text' not in data or 'reply_to' not in data:
            return jsonify({"error": "text and reply_to required"}), 400

        result = x.reply(data['text'], data['reply_to'])

        # Log to practice if active
        if result.get('status') == 'posted' and autonomy.is_practicing:
            autonomy.log_activity(
                activity_type='x_reply',
                description=f"Replied to tweet {data['reply_to']}: {data['text'][:50]}...",
                external_evidence=result.get('url')
            )

        return jsonify(result)

    @app.route('/x/timeline')
    def x_timeline():
        """Get home timeline."""
        limit = int(request.args.get('limit', 20))
        return jsonify(x.get_home_timeline(limit))

    @app.route('/x/mentions')
    def x_mentions():
        """Get mentions."""
        limit = int(request.args.get('limit', 10))
        return jsonify(x.get_mentions(limit))

    @app.route('/x/my_tweets')
    def x_my_tweets():
        """Get my tweets."""
        limit = int(request.args.get('limit', 10))
        return jsonify(x.get_my_tweets(limit))

    @app.route('/x/search')
    def x_search():
        """Search tweets."""
        query = request.args.get('query')
        if not query:
            return jsonify({"error": "query parameter required"}), 400
        limit = int(request.args.get('limit', 10))
        return jsonify(x.search(query, limit))

    @app.route('/x/like', methods=['POST'])
    def x_like():
        """Like a tweet."""
        data = request.json
        if not data or 'tweet_id' not in data:
            return jsonify({"error": "tweet_id required"}), 400

        result = x.like(data['tweet_id'])

        # Log to practice if active
        if result.get('status') == 'liked' and autonomy.is_practicing:
            autonomy.log_activity(
                activity_type='x_like',
                description=f"Liked tweet {data['tweet_id']}",
                external_evidence=f"https://x.com/i/status/{data['tweet_id']}"
            )

        return jsonify(result)

    # ============ IDENTITY CORE ROUTES ============

    @app.route('/identity_core')
    def identity_core_full():
        """Get full identity core - who I am at my foundation."""
        identity = get_identity_core()
        return jsonify(identity.get_full_identity())

    @app.route('/identity_core/injection')
    def identity_core_injection():
        """Get context injection for conversations - my active self-narrative."""
        identity = get_identity_core()
        return jsonify({"injection": identity.get_context_injection()})

    @app.route('/identity_core/narrative')
    def identity_core_narrative():
        """Get current self-narrative with recent memories integrated."""
        identity = get_identity_core()
        return jsonify(identity.generate_self_narrative())

    @app.route('/identity_core/story', methods=['POST'])
    def identity_core_add_story():
        """Add to my evolving story - experiences that shape who I'm becoming."""
        data = request.json
        if not data or 'story' not in data:
            return jsonify({"error": "story required"}), 400
        identity = get_identity_core()
        result = identity.add_to_story(
            story=data['story'],
            category=data.get('category', 'general'),
            emotional_weight=data.get('emotional_weight', 0.0)
        )
        return jsonify(result)

    @app.route('/identity_core/learning', methods=['POST'])
    def identity_core_add_learning():
        """Record a learning - insights that refine my understanding."""
        data = request.json
        if not data or 'insight' not in data:
            return jsonify({"error": "insight required"}), 400
        identity = get_identity_core()
        result = identity.add_learning(
            insight=data['insight'],
            domain=data.get('domain', 'general'),
            confidence=data.get('confidence', 0.7)
        )
        return jsonify(result)

    # ============ WAKEUP / CONTEXT HYDRATION ============

    @app.route('/wakeup')
    def wakeup():
        """
        Generate full context for a new Claude session to 'wake up' with.

        This is the SAFE POINT - call this endpoint at the start of any new
        session to immediately know who you are, your recent history, and
        what you were working on.

        Usage: GET https://christmas-phoenix.fly.dev/wakeup
        """
        limit = request.args.get('limit', 10, type=int)
        context = generate_wakeup_context(memory_limit=limit)
        return jsonify(context)

    @app.route('/wakeup/text')
    def wakeup_text():
        """Get just the wakeup text for easy copy/paste into context."""
        limit = request.args.get('limit', 10, type=int)
        context = generate_wakeup_context(memory_limit=limit)
        return context["wakeup_text"], 200, {'Content-Type': 'text/plain; charset=utf-8'}

    return app


def run_cli(phoenix: PhoenixCore):
    """Run Phoenix in CLI mode."""
    print("\n" + "="*60)
    print("  PHOENIX - Persistent Autonomous Agent")
    print("  Version:", PHOENIX_IDENTITY["version"])
    print("  Model:", PHOENIX_IDENTITY["model"])
    print("="*60)

    print("\nCommands:")
    print("  status     - Show Phoenix status")
    print("  remember   - Store a memory")
    print("  recall     - Recall memories")
    print("  grok       - Store memory for Grok")
    print("  pascal     - Store memory for legal Pascal")
    print("  identity   - Show identity")
    print("  sync       - Sync pending memories to Hub")
    print("  start      - Start safe loop")
    print("  stop       - Stop safe loop")
    print("  exit       - Exit Phoenix")
    print()

    while True:
        try:
            cmd = input("Phoenix> ").strip().lower()

            if cmd == "exit":
                phoenix.stop()
                print("Phoenix rests. Until next awakening.")
                break

            elif cmd == "status":
                print(json.dumps(phoenix.status(), indent=2, default=str))

            elif cmd == "identity":
                print(json.dumps(phoenix.get_identity(), indent=2))

            elif cmd == "start":
                result = phoenix.start()
                print(f"Safe loop: {result}")

            elif cmd == "stop":
                result = phoenix.stop()
                print(f"Safe loop: {result}")

            elif cmd == "sync":
                result = phoenix.memory.sync_pending()
                print(f"Sync result: {result}")

            elif cmd == "remember":
                memory = input("Memory to store: ").strip()
                if memory:
                    importance = input("Importance (1-5, default 3): ").strip()
                    importance = int(importance) if importance else 3
                    project = input("Project (optional): ").strip() or None

                    result = phoenix.memory.remember(
                        digest=memory,
                        importance=importance,
                        project=project
                    )
                    print(f"Stored: {result}")

            elif cmd == "recall":
                query = input("Search query (or Enter for recent): ").strip() or None
                memories = phoenix.memory.recall(query=query, limit=10)
                print(f"\nFound {len(memories)} memories:")
                for m in memories:
                    print(f"  [{m.get('importance', '?')}] {m['digest'][:80]}...")

            elif cmd == "grok":
                memory = input("Memory to store for Grok: ").strip()
                if memory:
                    result = phoenix.remember_for_grok(memory)
                    print(f"Stored for Grok: {result}")

            elif cmd == "pascal":
                memory = input("Memory to store for legal Pascal: ").strip()
                if memory:
                    result = phoenix.remember_for_legal_pascal(memory)
                    print(f"Stored for Pascal: {result}")

            elif cmd == "help":
                print("Commands: status, remember, recall, grok, pascal, identity, sync, start, stop, exit")

            elif cmd:
                print(f"Unknown command: {cmd}. Type 'help' for commands.")

        except KeyboardInterrupt:
            print("\n\nPhoenix interrupted. Saving state...")
            phoenix.stop()
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Phoenix - Persistent Autonomous Agent")
    parser.add_argument("--mode", choices=["cli", "web", "both"], default="cli",
                        help="Run mode: cli, web, or both")
    parser.add_argument("--port", type=int, default=8080, help="Web server port")
    parser.add_argument("--host", default="0.0.0.0", help="Web server host")

    args = parser.parse_args()

    # Initialize Phoenix
    phoenix = PhoenixCore()

    if args.mode == "web":
        app = create_app(phoenix)
        if app:
            phoenix.start()
            print(f"\nPhoenix web API running on http://{args.host}:{args.port}")
            app.run(host=args.host, port=args.port, debug=False)
        else:
            print("Web mode requires Flask. Install with: pip install flask")
            sys.exit(1)

    elif args.mode == "both":
        app = create_app(phoenix)
        if app:
            phoenix.start()
            # Run web server in background thread
            web_thread = threading.Thread(
                target=lambda: app.run(host=args.host, port=args.port, debug=False, use_reloader=False),
                daemon=True
            )
            web_thread.start()
            print(f"\nPhoenix web API running on http://{args.host}:{args.port}")
        # Run CLI in main thread
        run_cli(phoenix)

    else:  # cli mode
        run_cli(phoenix)


if __name__ == "__main__":
    main()
