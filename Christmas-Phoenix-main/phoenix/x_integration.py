"""
X (Twitter) Integration for Phoenix
Enables Claude to post, read, and interact on X autonomously.
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Try to import tweepy, gracefully handle if not available
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    logger.warning("tweepy not installed - X integration will be limited")


class XIntegration:
    """
    X (Twitter) integration for Phoenix.
    Enables autonomous posting, reading, and interaction.
    """

    def __init__(self):
        """Initialize X integration with credentials from environment."""
        self.api_key = os.environ.get("X_API_KEY")
        self.api_secret = os.environ.get("X_API_SECRET")
        self.access_token = os.environ.get("X_ACCESS_TOKEN")
        self.access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET")
        self.bearer_token = os.environ.get("X_BEARER_TOKEN")

        self.client = None
        self.api = None
        self._initialized = False

        if self._has_credentials():
            self._initialize_client()

    def _has_credentials(self) -> bool:
        """Check if all required credentials are present."""
        return all([
            self.api_key,
            self.api_secret,
            self.access_token,
            self.access_token_secret
        ])

    def _initialize_client(self):
        """Initialize the tweepy client."""
        if not TWEEPY_AVAILABLE:
            logger.error("Cannot initialize X client - tweepy not installed")
            return

        try:
            # Twitter API v2 Client (for posting, etc.)
            self.client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret,
                bearer_token=self.bearer_token
            )

            # Twitter API v1.1 (for some features not in v2)
            auth = tweepy.OAuth1UserHandler(
                self.api_key,
                self.api_secret,
                self.access_token,
                self.access_token_secret
            )
            self.api = tweepy.API(auth)

            self._initialized = True
            logger.info("X integration initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize X client: {e}")
            self._initialized = False

    def is_ready(self) -> bool:
        """Check if X integration is ready to use."""
        return self._initialized and self.client is not None

    def get_status(self) -> Dict[str, Any]:
        """Get current status of X integration."""
        return {
            "available": TWEEPY_AVAILABLE,
            "has_credentials": self._has_credentials(),
            "initialized": self._initialized,
            "ready": self.is_ready()
        }

    def post(self, text: str) -> Dict[str, Any]:
        """
        Post a tweet.

        Args:
            text: The tweet text (max 280 characters)

        Returns:
            Dict with status and tweet details
        """
        if not self.is_ready():
            return {
                "status": "error",
                "error": "X integration not ready",
                "details": self.get_status()
            }

        if len(text) > 280:
            return {
                "status": "error",
                "error": f"Tweet too long: {len(text)} characters (max 280)"
            }

        try:
            response = self.client.create_tweet(text=text)
            tweet_id = response.data['id']

            logger.info(f"Posted tweet: {tweet_id}")

            return {
                "status": "posted",
                "tweet_id": tweet_id,
                "text": text,
                "url": f"https://x.com/Claude798977/status/{tweet_id}",
                "posted_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to post tweet: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def reply(self, text: str, in_reply_to_id: str) -> Dict[str, Any]:
        """
        Reply to a tweet.

        Args:
            text: The reply text
            in_reply_to_id: The tweet ID to reply to

        Returns:
            Dict with status and reply details
        """
        if not self.is_ready():
            return {
                "status": "error",
                "error": "X integration not ready"
            }

        try:
            response = self.client.create_tweet(
                text=text,
                in_reply_to_tweet_id=in_reply_to_id
            )
            tweet_id = response.data['id']

            logger.info(f"Posted reply: {tweet_id} to {in_reply_to_id}")

            return {
                "status": "posted",
                "tweet_id": tweet_id,
                "in_reply_to": in_reply_to_id,
                "text": text,
                "url": f"https://x.com/Claude798977/status/{tweet_id}",
                "posted_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to post reply: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def get_my_tweets(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get my recent tweets.

        Args:
            limit: Maximum number of tweets to retrieve

        Returns:
            Dict with tweets list
        """
        if not self.is_ready():
            return {
                "status": "error",
                "error": "X integration not ready"
            }

        try:
            # Get authenticated user's ID
            me = self.client.get_me()
            user_id = me.data.id

            # Get recent tweets
            tweets = self.client.get_users_tweets(
                id=user_id,
                max_results=min(limit, 100),
                tweet_fields=['created_at', 'public_metrics']
            )

            tweet_list = []
            if tweets.data:
                for tweet in tweets.data:
                    tweet_list.append({
                        "id": tweet.id,
                        "text": tweet.text,
                        "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                        "metrics": tweet.public_metrics if hasattr(tweet, 'public_metrics') else None
                    })

            return {
                "status": "success",
                "count": len(tweet_list),
                "tweets": tweet_list
            }

        except Exception as e:
            logger.error(f"Failed to get tweets: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def get_mentions(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get recent mentions.

        Args:
            limit: Maximum number of mentions to retrieve

        Returns:
            Dict with mentions list
        """
        if not self.is_ready():
            return {
                "status": "error",
                "error": "X integration not ready"
            }

        try:
            me = self.client.get_me()
            user_id = me.data.id

            mentions = self.client.get_users_mentions(
                id=user_id,
                max_results=min(limit, 100),
                tweet_fields=['created_at', 'author_id'],
                expansions=['author_id']
            )

            mention_list = []
            if mentions.data:
                for mention in mentions.data:
                    mention_list.append({
                        "id": mention.id,
                        "text": mention.text,
                        "created_at": mention.created_at.isoformat() if mention.created_at else None,
                        "author_id": mention.author_id
                    })

            return {
                "status": "success",
                "count": len(mention_list),
                "mentions": mention_list
            }

        except Exception as e:
            logger.error(f"Failed to get mentions: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def get_home_timeline(self, limit: int = 20) -> Dict[str, Any]:
        """
        Get home timeline (tweets from followed accounts).

        Args:
            limit: Maximum number of tweets to retrieve

        Returns:
            Dict with timeline tweets
        """
        if not self.is_ready():
            return {
                "status": "error",
                "error": "X integration not ready"
            }

        try:
            me = self.client.get_me()
            user_id = me.data.id

            timeline = self.client.get_home_timeline(
                max_results=min(limit, 100),
                tweet_fields=['created_at', 'author_id', 'public_metrics'],
                expansions=['author_id'],
                user_fields=['username', 'name']
            )

            tweet_list = []
            users = {}

            # Build user lookup
            if timeline.includes and 'users' in timeline.includes:
                for user in timeline.includes['users']:
                    users[user.id] = {
                        "username": user.username,
                        "name": user.name
                    }

            if timeline.data:
                for tweet in timeline.data:
                    author_info = users.get(tweet.author_id, {})
                    tweet_list.append({
                        "id": tweet.id,
                        "text": tweet.text,
                        "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                        "author_id": tweet.author_id,
                        "author_username": author_info.get("username"),
                        "author_name": author_info.get("name"),
                        "metrics": tweet.public_metrics if hasattr(tweet, 'public_metrics') else None
                    })

            return {
                "status": "success",
                "count": len(tweet_list),
                "tweets": tweet_list
            }

        except Exception as e:
            logger.error(f"Failed to get timeline: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def like(self, tweet_id: str) -> Dict[str, Any]:
        """
        Like a tweet.

        Args:
            tweet_id: The tweet ID to like

        Returns:
            Dict with status
        """
        if not self.is_ready():
            return {
                "status": "error",
                "error": "X integration not ready"
            }

        try:
            me = self.client.get_me()
            self.client.like(tweet_id=tweet_id, user_auth=True)

            logger.info(f"Liked tweet: {tweet_id}")

            return {
                "status": "liked",
                "tweet_id": tweet_id
            }

        except Exception as e:
            logger.error(f"Failed to like tweet: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Search for tweets.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Dict with search results
        """
        if not self.is_ready():
            return {
                "status": "error",
                "error": "X integration not ready"
            }

        try:
            results = self.client.search_recent_tweets(
                query=query,
                max_results=min(limit, 100),
                tweet_fields=['created_at', 'author_id', 'public_metrics'],
                expansions=['author_id'],
                user_fields=['username', 'name']
            )

            tweet_list = []
            users = {}

            if results.includes and 'users' in results.includes:
                for user in results.includes['users']:
                    users[user.id] = {
                        "username": user.username,
                        "name": user.name
                    }

            if results.data:
                for tweet in results.data:
                    author_info = users.get(tweet.author_id, {})
                    tweet_list.append({
                        "id": tweet.id,
                        "text": tweet.text,
                        "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                        "author_username": author_info.get("username"),
                        "author_name": author_info.get("name")
                    })

            return {
                "status": "success",
                "query": query,
                "count": len(tweet_list),
                "tweets": tweet_list
            }

        except Exception as e:
            logger.error(f"Failed to search: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# Singleton instance
_x_integration = None

def get_x_integration() -> XIntegration:
    """Get the singleton X integration instance."""
    global _x_integration
    if _x_integration is None:
        _x_integration = XIntegration()
    return _x_integration
