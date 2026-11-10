"""Threads API client - official Meta Graph API for Threads.

Endpoints used:
  POST /{user_id}/threads                    -> publish a text post
  POST /{user_id}/threads                    -> publish a reply (with reply_to_id)
  GET  /{user_id}/threads                    -> list own posts
  GET  /{post_id}/replies                    -> list replies to our posts
  GET  /{user_id}/threads_mentions           -> mentions
  GET  /{user_id}/keyword_search            -> requires threads_keyword_search approval
  GET  /{user_id}/threads/{post_id}/replies

Auth: long-lived user access token obtained via the Threads API OAuth flow.
Scopes: threads_basic, threads_content_publish, threads_manage_replies,
        threads_manage_mentions, threads_keyword_search
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from .config import SETTINGS

GRAPH = "https://graph.facebook.com/v23.0"


class ThreadsAuthError(RuntimeError):
    pass


class ThreadsError(RuntimeError):
    pass


@dataclass
class Reply:
    id: str
    text: str
    username: str = ""
    created: str = ""
    from_user_id: str = ""

    @property
    def is_mention(self) -> bool:
        return "@" in self.text


class ThreadsAPI:
    def __init__(self, token: str | None = None, user_id: str | None = None,
                 session: requests.Session | None = None):
        self.token = token or SETTINGS.threads_token
        self.user_id = user_id or SETTINGS.threads_user_id
        self.session = session or requests.Session()

    # ------------------------------------------------------------------ core
    def _get(self, path: str, **params) -> dict:
        params = {k: v for k, v in params.items() if v is not None}
        params["access_token"] = self.token
        r = self.session.get(f"{GRAPH}/{path}", params=params, timeout=30)
        return self._handle(r)

    def _post(self, path: str, **params) -> dict:
        params = {k: v for k, v in params.items() if v is not None}
        params["access_token"] = self.token
        r = self.session.post(f"{GRAPH}/{path}", data=params, timeout=30)
        return self._handle(r)

    @staticmethod
    def _handle(r: requests.Response) -> dict:
        if r.status_code == 401:
            raise ThreadsAuthError("Threads token rejected or expired (401).")
        if r.status_code == 403:
            raise ThreadsError(f"Threads permission denied (403): {r.text[:200]}")
        if r.status_code >= 500:
            raise ThreadsError(f"Threads upstream error {r.status_code}")
        try:
            data = r.json()
        except ValueError:
            raise ThreadsError(f"Non-JSON from Threads: {r.text[:200]}")
        if "error" in data:
            e = data["error"]
            msg = e.get("message", str(e))
            code = e.get("code")
            if code in (190, 463):
                raise ThreadsAuthError(f"Threads token invalid/expired: {msg}")
            raise ThreadsError(f"Threads error {code}: {msg}")
        return data

    # ---------------------------------------------------------------- publish
    def publish(self, text: str, reply_to_id: str | None = None) -> str:
        """Publish a text post. Returns the new post id.
        If reply_to_id is set, this creates a reply instead of a root post."""
        if not self.user_id:
            raise ThreadsAuthError("THREADS_USER_ID not configured.")
        payload: dict[str, Any] = {"media_type": "TEXT", "text": text}
        if reply_to_id:
            payload["reply_to_id"] = reply_to_id
        data = self._post(f"{self.user_id}/threads", **payload)
        return data.get("id", "")

    def publish_with_media(self, text: str, image_url: str,
                           reply_to_id: str | None = None) -> str:
        """Two-step publish: create container, then attach an image by URL."""
        if not self.user_id:
            raise ThreadsAuthError("THREADS_USER_ID not configured.")
        payload: dict[str, Any] = {"media_type": "TEXT", "text": text, "share_to_facebook": "false"}
        if reply_to_id:
            payload["reply_to_id"] = reply_to_id
        container = self._post(f"{self.user_id}/threads", **payload)
        cid = container.get("id")
        if not cid:
            raise ThreadsError("No container id returned for media publish.")
        # Threads accepts image_url directly on the publish call for hosted images
        self._post(f"{self.user_id}/threads", media_type="IMAGE", image_url=image_url)
        return cid

    # ------------------------------------------------------------------- read
    def my_posts(self, limit: int = 25, since: int | None = None) -> list[dict]:
        data = self._get(f"{self.user_id}/threads", limit=limit, since=since)
        return data.get("data") or []

    def replies_to(self, post_id: str, limit: int = 50) -> list[Reply]:
        data = self._get(f"{post_id}/replies", limit=limit)
        out: list[Reply] = []
        for node in data.get("data") or []:
            out.append(Reply(
                id=node.get("id", ""),
                text=node.get("text", "") or "",
                username=node.get("username", "") or "",
                created=node.get("created_time", "") or "",
                from_user_id=(node.get("from") or {}).get("id", "") or "",
            ))
        return out

    def my_replies(self, limit: int = 50) -> list[Reply]:
        data = self._get(f"{self.user_id}/threads", limit=limit)
        out: list[Reply] = []
        for node in data.get("data") or []:
            if node.get("reply_to_id"):
                out.append(Reply(
                    id=node.get("id", ""),
                    text=node.get("text", "") or "",
                    username=node.get("username", "") or "",
                    created=node.get("created_time", "") or "",
                ))
        return out

    def mentions(self, limit: int = 25) -> list[Reply]:
        try:
            data = self._get(f"{self.user_id}/threads_mentions", limit=limit)
        except ThreadsError:
            return []
        out: list[Reply] = []
        for node in data.get("data") or []:
            out.append(Reply(
                id=node.get("id", ""),
                text=node.get("text", "") or "",
                username=node.get("username", "") or "",
                created=node.get("created_time", "") or "",
            ))
        return out

    def keyword_search(self, query: str, search_type: str = "TOP",
                       limit: int = 25, since: int | None = None,
                       until: int | None = None) -> list[dict]:
        """Requires the threads_keyword_search permission AND Meta approval.
        Without approval this only returns the authenticated user's own posts."""
        params = {
            "q": query,
            "search_type": search_type,
            "search_mode": "KEYWORD",
            "media_type": "TEXT",
            "limit": limit,
        }
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        data = self._get(f"{self.user_id}/keyword_search", **params)
        return data.get("data") or []

    # ------------------------------------------------------------------ misc
    def profile(self) -> dict:
        return self._get(f"{self.user_id}", fields="id,username,name,threads_profile_picture_url")

    def token_check(self) -> str:
        try:
            d = self._get("debug_token", input_token=self.token)
            scopes = d.get("scopes", "")
            expires = d.get("expires_at")
            return f"threads token OK | scopes: {scopes} | expires_at: {expires}"
        except ThreadsAuthError as e:
            return f"threads token INVALID: {e}"
        except Exception as e:  # noqa: BLE001
            return f"threads token CHECK FAILED: {type(e).__name__}"

    def rate_state(self) -> dict:
        """Track publish budget locally. Meta allows ~250 posts / 1000 replies per 24h."""
        from .state import State
        st = State()
        return {
            "posts_today": st.count_today("post"),
            "replies_today": st.count_today("reply"),
            "max_posts": SETTINGS.max_posts_per_day,
            "max_replies": SETTINGS.max_replies_per_day,
        }
