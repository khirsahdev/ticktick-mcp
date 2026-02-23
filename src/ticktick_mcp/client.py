import logging
from typing import Optional

# TickTick library imports
from ticktick.api import TickTickClient
from ticktick.oauth2 import OAuth2

# Import config variables and paths
from .config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, USERNAME, PASSWORD, dotenv_dir_path


class TickTickClientNoSignon(TickTickClient):
    """
    Subclass of TickTickClient that skips the username/password signon step
    when a valid OAuth token is already cached.

    ticktick-py always calls /api/v2/user/signon on init, even with a cached
    OAuth token. Repeated signon calls trigger TickTick's anti-fraud lockout
    (HTTP 500). This subclass reuses the cached OAuth access token instead,
    avoiding the lockout entirely.
    """
    def _login(self, username: str, password: str) -> None:
        token_info = getattr(self.oauth_manager, 'access_token_info', None)
        if token_info and token_info.get('access_token'):
            token = token_info['access_token']
            self.access_token = token
            self.cookies['t'] = token
            logging.info("Skipped signon — reusing cached OAuth access token.")
        else:
            logging.info("No cached OAuth token found — falling back to signon.")
            super()._login(username, password)


class TickTickClientSingleton:
    """Singleton class to manage the TickTickClient instance."""
    _instance: Optional[TickTickClient] = None
    _initialized: bool = False

    def __new__(cls):
        # Standard singleton pattern: __new__ controls object creation
        if cls._instance is None:
            # Only create the instance if it doesn't exist
            # But defer actual client initialization to __init__
            # to ensure it happens only once even if __new__ is called multiple times
            # before __init__ completes (though unlikely in typical singleton usage).
            pass # Object creation handled by Python automatically
        return super(TickTickClientSingleton, cls).__new__(cls) # Return the instance (or create if needed)

    def __init__(self):
        """Initializes the TickTick client within the singleton instance, ensuring it runs only once."""
        if self._initialized:
            return # Already initialized

        if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, USERNAME, PASSWORD]):
            logging.error("TickTick credentials not found in environment variables (checked in config.py). Ensure .env file is correct.")
            TickTickClientSingleton._instance = None # Ensure instance is None if creds are missing
            TickTickClientSingleton._initialized = True # Mark as initialized (attempted)
            return

        try:
            logging.info(f"Initializing OAuth2 with cache path: {dotenv_dir_path / '.token-oauth'}")
            auth_client = OAuth2(
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                redirect_uri=REDIRECT_URI,
                cache_path=dotenv_dir_path / ".token-oauth" # Use path from config
            )
            auth_client.get_access_token() # Might trigger interactive OAuth flow

            logging.info(f"Initializing TickTickClient with username: {USERNAME}")
            client = TickTickClientNoSignon(USERNAME, PASSWORD, auth_client)
            logging.info(f"TickTick client initialized successfully within singleton.")
            TickTickClientSingleton._instance = client
        except Exception as e:
            logging.error(f"Error initializing TickTick client within singleton: {e}", exc_info=True)
            TickTickClientSingleton._instance = None # Ensure instance is None on error
        finally:
            # Mark as initialized regardless of success/failure to prevent re-attempts
            TickTickClientSingleton._initialized = True

    @classmethod
    def get_client(cls) -> Optional[TickTickClient]:
        """Returns the initialized TickTick client instance."""
        if not cls._initialized:
            cls() # Ensure __init__ is called if not already initialized
        if cls._instance is None:
            logging.warning("get_client() called, but TickTick client failed to initialize.")
        return cls._instance

# Removed the old function
# def initialize_ticktick_client():
# ... existing code ... 