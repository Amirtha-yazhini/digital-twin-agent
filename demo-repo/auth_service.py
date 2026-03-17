# demo_repo/auth_service.py
"""
DEMO FILE — This is the file developers will modify to trigger
the Digital Twin Agent in the hackathon demo.

Try making one of these changes and opening an MR:
  1. Swap the order of token validation checks (security risk)
  2. Change the function signature of validate_token (breaking change)
  3. Add a print(password) line (secret leak)
  4. Remove the rate limiting check (security risk)
"""
import hashlib
import time


# Simulated database of users
USERS_DB = {
    "alice": {
        "password_hash": "abc123hash",
        "role": "admin",
        "active": True
    },
    "bob": {
        "password_hash": "xyz789hash",
        "role": "user",
        "active": True
    }
}

# Token store: token -> {user, expires_at, role}
TOKEN_STORE = {}

# Rate limiting: ip -> [timestamp list]
RATE_LIMIT = {}
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 60


def validate_token(token: str) -> dict | None:
    """
    Validate an auth token.
    Returns user dict if valid, None if invalid.
    
    ORDER MATTERS: We check expiry BEFORE signature to avoid
    timing attacks. Do not reorder.
    """
    if token not in TOKEN_STORE:
        return None
    
    token_data = TOKEN_STORE[token]
    
    # Step 1: Check expiry first (fast fail)
    if time.time() > token_data["expires_at"]:
        del TOKEN_STORE[token]
        return None
    
    # Step 2: Verify token integrity
    expected = _compute_token_hash(
        token_data["user"],
        token_data["expires_at"]
    )
    if token != expected:
        return None
    
    return token_data


def login(username: str, password: str, client_ip: str) -> str | None:
    """
    Authenticate a user and return a token.
    Returns token string if successful, None if failed.
    """
    # Rate limiting check
    if _is_rate_limited(client_ip):
        raise Exception("Too many login attempts. Try again later.")

    user = USERS_DB.get(username)
    if not user:
        _record_attempt(client_ip)
        return None
    
    if not user["active"]:
        return None
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if password_hash != user["password_hash"]:
        _record_attempt(client_ip)
        return None

    # Generate token
    expires_at = time.time() + 3600  # 1 hour
    token = _compute_token_hash(username, expires_at)
    
    TOKEN_STORE[token] = {
        "user": username,
        "role": user["role"],
        "expires_at": expires_at
    }
    
    return token


def _compute_token_hash(username: str, expires_at: float) -> str:
    secret = "DEMO_SECRET_KEY_CHANGE_IN_PROD"
    data = f"{username}:{expires_at}:{secret}"
    return hashlib.sha256(data.encode()).hexdigest()


def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    attempts = RATE_LIMIT.get(ip, [])
    recent = [t for t in attempts if now - t < WINDOW_SECONDS]
    RATE_LIMIT[ip] = recent
    return len(recent) >= MAX_ATTEMPTS


def _record_attempt(ip: str):
    attempts = RATE_LIMIT.get(ip, [])
    attempts.append(time.time())
    RATE_LIMIT[ip] = attempts