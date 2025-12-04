# Production Authentication Guide

## Current Implementation (Single Token)

Currently, the system uses **one API token for all users**:
- `API_TOKEN` in `.env` file
- Same token used for all buy/sell operations
- **Problem**: All trades appear to come from the same account

## Production Requirements

In production, **each user must have their own authentication token** because:
1. **Security**: Users should only trade with their own accounts
2. **Compliance**: Audit trails must show which user executed which trade
3. **Authorization**: n-dollar server needs to verify user identity
4. **Rate Limiting**: Per-user rate limits prevent abuse

---

## Solution Options

### Option 1: Store Tokens in Database (Recommended)

Store each user's JWT token in the SQLite database and retrieve it per user.

#### Implementation Steps:

**1. Add Token Storage to Database Schema**

```sql
-- Add to fetch-data-agent/src/database/schema.ts
ALTER TABLE users ADD COLUMN api_token TEXT;
ALTER TABLE users ADD COLUMN token_expires_at TIMESTAMP;
ALTER TABLE users ADD COLUMN token_refresh_token TEXT;
```

**2. Create Token Manager Service**

Create `trade-agent/src/services/token_manager.py`:

```python
from typing import Optional
import sqlite3
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class UserTokenManager:
    """Manages per-user authentication tokens."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_user_token(self, user_id: int) -> Optional[str]:
        """Retrieve API token for a specific user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT api_token, token_expires_at FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                logger.warning(f"No token found for user {user_id}")
                return None
            
            token, expires_at = row
            if not token:
                return None
            
            # Check if token is expired
            if expires_at:
                try:
                    expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) >= expiry:
                        logger.warning(f"Token expired for user {user_id}")
                        return None
                except ValueError:
                    pass
            
            return token
    
    def set_user_token(self, user_id: int, token: str, expires_at: Optional[str] = None):
        """Store or update user's API token."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE users 
                SET api_token = ?, token_expires_at = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (token, expires_at, datetime.now(timezone.utc).isoformat(), user_id)
            )
            conn.commit()
            logger.info(f"Token updated for user {user_id}")
```

**3. Update NDollarClient to Accept Per-User Tokens**

Modify `trade-agent/src/execution/ndollar_client.py`:

```python
class NDollarClient:
    def __init__(self, base_url: str, default_token: Optional[str] = None, timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.default_token = default_token  # Fallback for users without tokens
        self.timeout = timeout

    def buy(self, token_mint: str, amount: float, user_api_token: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "tokenMintAddress": token_mint,
            "amount": amount,
        }
        api_token = user_api_token or self.default_token
        return self._post("/buy", payload, api_token)

    def sell(self, token_mint: str, amount: float, user_api_token: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "tokenMintAddress": token_mint,
            "amount": amount,
        }
        api_token = user_api_token or self.default_token
        return self._post("/sell", payload, api_token)

    def _post(self, path: str, payload: Dict[str, Any], api_token: Optional[str]) -> Dict[str, Any]:
        if not api_token:
            logger.warning("API token missing, skipping HTTP request")
            return {"success": False, "message": "API token not configured"}

        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        # ... rest of the method
```

**4. Update Trade Pipeline to Use Per-User Tokens**

Modify `trade-agent/src/pipeline/trade_pipeline.py`:

```python
class TradePipeline:
    def __init__(self, settings: Settings):
        # ... existing code ...
        self.token_manager = UserTokenManager(str(settings.sqlite_path))
        self.client = NDollarClient(settings.api_base_url, settings.api_token)

    def _node_execution(self, state: TradeState) -> TradeState:
        decision: Optional[TradeDecision] = state.get("decision")
        if not decision:
            return {}

        # Get user-specific token
        user_token = self.token_manager.get_user_token(decision.user_id)
        if not user_token and not self.settings.api_token:
            logger.error(f"No token available for user {decision.user_id}")
            return {}

        # ... confidence check ...

        elif (
            decision.action in ("buy", "sell")
            and decision.token_mint
            and decision.amount
        ):
            if self.settings.dry_run or not (user_token or self.settings.api_token):
                logger.info("[Dry Run] Would execute ...")
            else:
                # Use user-specific token, fallback to default
                token_to_use = user_token or self.settings.api_token
                if decision.action == "buy":
                    self.client.buy(decision.token_mint, decision.amount, token_to_use)
                else:
                    self.client.sell(decision.token_mint, decision.amount, token_to_use)
```

---

### Option 2: Token Service with User ID in Payload

If n-dollar API accepts `user_id` in the request payload, you can use a service account token:

```python
def buy(self, token_mint: str, amount: float, user_id: int) -> Dict[str, Any]:
    payload = {
        "tokenMintAddress": token_mint,
        "amount": amount,
        "userId": user_id,  # Server identifies user from payload
    }
    # Use service account token
    return self._post("/buy", payload, self.service_token)
```

**Pros:**
- Simpler: No per-user token storage
- Centralized token management

**Cons:**
- Requires n-dollar API to support this pattern
- Less secure (service account has access to all users)

---

### Option 3: OAuth Refresh Token Flow

For long-running services, implement OAuth refresh:

```python
class OAuthTokenManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.token_cache: Dict[int, Tuple[str, datetime]] = {}
    
    def get_user_token(self, user_id: int) -> Optional[str]:
        # Check cache first
        if user_id in self.token_cache:
            token, expires = self.token_cache[user_id]
            if datetime.now(timezone.utc) < expires:
                return token
        
        # Get refresh token from DB
        refresh_token = self._get_refresh_token(user_id)
        if not refresh_token:
            return None
        
        # Refresh the access token
        new_token, expires_in = self._refresh_access_token(refresh_token)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        # Cache and return
        self.token_cache[user_id] = (new_token, expires_at)
        return new_token
```

---

## Recommended Production Architecture

### Database Schema Addition

```sql
-- Migration script for fetch-data-agent
ALTER TABLE users ADD COLUMN api_token TEXT;
ALTER TABLE users ADD COLUMN token_expires_at TIMESTAMP;
ALTER TABLE users ADD COLUMN token_refresh_token TEXT;
ALTER TABLE users ADD COLUMN token_issued_at TIMESTAMP;
CREATE INDEX idx_users_token ON users(user_id, api_token) WHERE api_token IS NOT NULL;
```

### Token Acquisition Flow

1. **User Registration/Login**:
   - User authenticates with n-dollar server
   - n-dollar returns JWT token + refresh token
   - Store in database via `fetch-data-agent` or separate auth service

2. **Token Refresh**:
   - Background job checks token expiry
   - Automatically refreshes tokens before expiry
   - Updates database

3. **Trade Execution**:
   - `trade-agent` retrieves user's token from database
   - Uses token for API calls
   - Logs which user executed which trade

### Security Best Practices

1. **Encrypt Tokens at Rest**:
   ```python
   from cryptography.fernet import Fernet
   
   class EncryptedTokenManager:
       def __init__(self, db_path: str, encryption_key: bytes):
           self.cipher = Fernet(encryption_key)
       
       def get_user_token(self, user_id: int) -> Optional[str]:
           encrypted = self._fetch_encrypted_token(user_id)
           if encrypted:
               return self.cipher.decrypt(encrypted).decode()
           return None
   ```

2. **Token Rotation**:
   - Rotate tokens periodically (e.g., every 30 days)
   - Invalidate old tokens after rotation

3. **Audit Logging**:
   - Log all token access attempts
   - Track token refresh events
   - Monitor for suspicious patterns

4. **Access Control**:
   - Only `trade-agent` should read tokens
   - Separate service for token acquisition/refresh
   - Use environment variables for encryption keys

---

## Implementation Checklist

- [ ] Add `api_token` column to users table
- [ ] Create `UserTokenManager` service
- [ ] Update `NDollarClient` to accept per-user tokens
- [ ] Modify `TradePipeline` to retrieve user tokens
- [ ] Add token refresh mechanism
- [ ] Implement token encryption (optional but recommended)
- [ ] Add token expiry checks
- [ ] Update audit logs to include user_id
- [ ] Test with multiple users
- [ ] Set up token refresh cron job

---

## Migration Path

1. **Phase 1**: Support both single token (env) and per-user tokens (DB)
   - Check DB first, fallback to env token
   - Allows gradual migration

2. **Phase 2**: Migrate existing users
   - Script to acquire tokens for all users
   - Store in database

3. **Phase 3**: Enforce per-user tokens
   - Remove fallback to env token
   - Require token for all trades

---

## Example: Token Acquisition Script

```python
# scripts/acquire_user_tokens.py
import requests
import sqlite3
from typing import List

def acquire_tokens_for_users(user_ids: List[int], n_dollar_auth_url: str):
    """Acquire and store tokens for users."""
    with sqlite3.connect("fetch-data-agent/data/user_data.db") as conn:
        for user_id in user_ids:
            # Call n-dollar auth endpoint (implementation depends on your API)
            response = requests.post(
                f"{n_dollar_auth_url}/auth/token",
                json={"userId": user_id},
                headers={"Authorization": "Bearer SERVICE_ACCOUNT_TOKEN"}
            )
            if response.ok:
                data = response.json()
                conn.execute(
                    """
                    UPDATE users 
                    SET api_token = ?, token_expires_at = ?
                    WHERE user_id = ?
                    """,
                    (data["access_token"], data["expires_at"], user_id)
                )
                conn.commit()
                print(f"✅ Token acquired for user {user_id}")
            else:
                print(f"❌ Failed to acquire token for user {user_id}")
```

---

## Testing Per-User Tokens

```python
# Test that each user uses their own token
def test_per_user_tokens():
    manager = UserTokenManager("test.db")
    
    # User 1
    token1 = manager.get_user_token(1)
    assert token1 == "user1_token"
    
    # User 2
    token2 = manager.get_user_token(2)
    assert token2 == "user2_token"
    assert token1 != token2  # Different tokens
```

---

## Summary

**For Production:**
- ✅ Store tokens in database (per user)
- ✅ Retrieve token per user before trade execution
- ✅ Handle token expiry and refresh
- ✅ Encrypt tokens at rest
- ✅ Audit all token access

**Current (Development):**
- Single token in `.env` file
- Works for testing but not production-ready

The recommended approach is **Option 1** (database storage) as it provides the best security, auditability, and scalability.

