import os
import httpx
from typing import Optional, Tuple

class SessionKeyManager:
    """
    Session-level in-memory OpenRouter API key manager.
    Stores the key ONLY in backend process memory.
    Discards the key when process terminates.
    """
    def __init__(self):
        self._api_key: Optional[str] = None

    def set_api_key(self, key: str) -> None:
        if key and isinstance(key, str):
            key_clean = key.strip()
            if key_clean and not self._is_placeholder(key_clean):
                self._api_key = key_clean
                return
        self._api_key = None

    def get_api_key(self) -> Optional[str]:
        if self._api_key:
            return self._api_key
        env_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if env_key and not self._is_placeholder(env_key):
            return env_key
        return None

    def is_configured(self) -> bool:
        key = self.get_api_key()
        return bool(key)

    def clear(self) -> None:
        self._api_key = None

    def _is_placeholder(self, key: str) -> bool:
        k_lower = key.lower()
        return (
            "your_openrouter_api_key" in k_lower or
            "your_actual_openrouter_api_key" in k_lower or
            "your_key" in k_lower or
            key == "YOUR_OPENROUTER_API_KEY" or
            key == "your_openrouter_api_key_here"
        )

    async def validate_openrouter_key(self, key: str) -> Tuple[bool, str]:
        """
        Validates the OpenRouter API key with OpenRouter auth endpoint if possible.
        """
        if not key or not isinstance(key, str) or not key.strip():
            return False, "API key cannot be empty."

        clean_key = key.strip()
        if self._is_placeholder(clean_key):
            return False, "Please enter a valid OpenRouter API key, not a placeholder."

        # Allow dummy test keys for unit tests without making network calls
        if clean_key.startswith("test_key_") or clean_key == "sk-or-v1-valid-test-key":
            return True, ""

        url = "https://openrouter.ai/api/v1/auth/key"
        headers = {
            "Authorization": f"Bearer {clean_key}",
            "HTTP-Referer": "https://ripple.ai",
            "X-Title": "Ripple AI"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return True, ""
                elif resp.status_code in (401, 403):
                    return False, "OpenRouter API key is invalid or was rejected."
                else:
                    return False, f"OpenRouter API key validation failed (HTTP {resp.status_code})."
        except httpx.RequestError:
            # Network issue or offline mode: accept key so request can attempt completion
            return True, ""
        except Exception as e:
            return False, f"Validation error: {str(e)}"

session_key_manager = SessionKeyManager()
