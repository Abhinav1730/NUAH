"""
PostgreSQL Seeder
=================
Seeds nuahchain-backend PostgreSQL database with test data.
"""

import logging
import secrets
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from .connection import DatabaseManager, db

logger = logging.getLogger(__name__)


class PostgresSeeder:
    """
    Seeds the nuahchain-backend PostgreSQL database with test data.
    Creates users, wallets, tokens, and balances directly in the database.
    """
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or db
    
    def create_user(
        self,
        email: str,
        username: str,
        password_hash: Optional[str] = None
    ) -> int:
        """
        Create a test user in the database.
        
        Returns:
            User ID
        """
        query = """
            INSERT INTO users (email, username, password_hash, created_at, updated_at, is_active)
            VALUES (%s, %s, %s, NOW(), NOW(), TRUE)
            ON CONFLICT (email) DO UPDATE SET updated_at = NOW()
            RETURNING id
        """
        result = self.db.fetch_one(query, (email, username, password_hash))
        return result['id'] if result else None
    
    def create_wallet(
        self,
        user_id: int,
        address: str,
        encrypted_private_key: bytes = None,
        mnemonic_encrypted: bytes = None
    ) -> int:
        """
        Create a wallet for a user.
        
        Returns:
            Wallet ID
        """
        # Generate dummy encrypted key if not provided
        if encrypted_private_key is None:
            encrypted_private_key = secrets.token_bytes(64)
        if mnemonic_encrypted is None:
            mnemonic_encrypted = secrets.token_bytes(128)
        
        query = """
            INSERT INTO wallets (user_id, address, encrypted_private_key, mnemonic_encrypted, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (address) DO UPDATE SET updated_at = NOW()
            RETURNING id
        """
        result = self.db.fetch_one(query, (user_id, address, encrypted_private_key, mnemonic_encrypted))
        return result['id'] if result else None
    
    def create_token(
        self,
        denom: str,
        name: str,
        symbol: str,
        creator_address: str,
        creator_user_id: int = None,
        image: str = None,
        description: str = None,
        decimals: int = 6
    ) -> int:
        """
        Create a token in the database.
        
        Returns:
            Token ID
        """
        query = """
            INSERT INTO tokens (denom, name, symbol, creator_address, creator_user_id, image, description, decimals, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (denom) DO UPDATE SET 
                name = EXCLUDED.name,
                symbol = EXCLUDED.symbol,
                updated_at = NOW()
            RETURNING id
        """
        result = self.db.fetch_one(query, (
            denom, name, symbol, creator_address, creator_user_id, 
            image, description, decimals
        ))
        return result['id'] if result else None
    
    def create_user_balance(
        self,
        user_id: int,
        address: str,
        denom: str,
        amount: str
    ) -> int:
        """
        Create or update a user balance.
        
        Returns:
            Balance ID
        """
        query = """
            INSERT INTO user_balances (user_id, address, denom, amount, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (user_id, denom) DO UPDATE SET 
                amount = EXCLUDED.amount,
                updated_at = NOW()
            RETURNING id
        """
        result = self.db.fetch_one(query, (user_id, address, denom, amount))
        return result['id'] if result else None
    
    def create_balance_history(
        self,
        user_id: int,
        address: str,
        denom: str,
        amount_before: str,
        amount_after: str,
        amount_delta: str,
        tx_hash: str,
        height: int,
        event_type: str = "sync"
    ) -> int:
        """
        Create a balance history entry.
        
        Returns:
            History entry ID
        """
        query = """
            INSERT INTO balance_history 
            (user_id, address, denom, amount_before, amount_after, amount_delta, tx_hash, height, event_type, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """
        result = self.db.fetch_one(query, (
            user_id, address, denom, amount_before, amount_after, 
            amount_delta, tx_hash, height, event_type
        ))
        return result['id'] if result else None
    
    def create_session(
        self,
        user_id: int,
        token: str,
        refresh_token: str,
        expires_hours: int = 24
    ) -> int:
        """
        Create a session for a user.
        
        Returns:
            Session ID
        """
        query = """
            INSERT INTO sessions (user_id, token, refresh_token, expires_at, refresh_expires_at, created_at, last_used_at)
            VALUES (%s, %s, %s, NOW() + INTERVAL '%s hours', NOW() + INTERVAL '%s hours', NOW(), NOW())
            RETURNING id
        """
        result = self.db.fetch_one(query, (user_id, token, refresh_token, expires_hours, expires_hours * 7))
        return result['id'] if result else None
    
    def bulk_create_users(self, users_data: List[Dict[str, Any]]) -> List[int]:
        """
        Bulk create users.
        
        Args:
            users_data: List of dicts with email, username, password_hash
            
        Returns:
            List of user IDs
        """
        user_ids = []
        for user in users_data:
            user_id = self.create_user(
                email=user['email'],
                username=user['username'],
                password_hash=user.get('password_hash')
            )
            if user_id:
                user_ids.append(user_id)
        logger.info(f"Created {len(user_ids)} users")
        return user_ids
    
    def bulk_create_wallets(self, wallets_data: List[Dict[str, Any]]) -> List[int]:
        """
        Bulk create wallets.
        
        Args:
            wallets_data: List of dicts with user_id, address
            
        Returns:
            List of wallet IDs
        """
        wallet_ids = []
        for wallet in wallets_data:
            wallet_id = self.create_wallet(
                user_id=wallet['user_id'],
                address=wallet['address']
            )
            if wallet_id:
                wallet_ids.append(wallet_id)
        logger.info(f"Created {len(wallet_ids)} wallets")
        return wallet_ids
    
    def bulk_create_tokens(self, tokens_data: List[Dict[str, Any]]) -> List[int]:
        """
        Bulk create tokens.
        
        Args:
            tokens_data: List of token dicts
            
        Returns:
            List of token IDs
        """
        token_ids = []
        for token in tokens_data:
            token_id = self.create_token(
                denom=token['denom'],
                name=token['name'],
                symbol=token['symbol'],
                creator_address=token['creator_address'],
                creator_user_id=token.get('creator_user_id'),
                image=token.get('image'),
                description=token.get('description'),
                decimals=token.get('decimals', 6)
            )
            if token_id:
                token_ids.append(token_id)
        logger.info(f"Created {len(token_ids)} tokens")
        return token_ids
    
    def bulk_create_balances(self, balances_data: List[Dict[str, Any]]) -> List[int]:
        """
        Bulk create user balances.
        
        Args:
            balances_data: List of balance dicts
            
        Returns:
            List of balance IDs
        """
        balance_ids = []
        for balance in balances_data:
            balance_id = self.create_user_balance(
                user_id=balance['user_id'],
                address=balance['address'],
                denom=balance['denom'],
                amount=balance['amount']
            )
            if balance_id:
                balance_ids.append(balance_id)
        logger.info(f"Created {len(balance_ids)} balances")
        return balance_ids
    
    def clear_test_data(self, preserve_tables: List[str] = None):
        """
        Clear all test data from the database.
        
        Args:
            preserve_tables: List of table names to preserve
        """
        preserve = preserve_tables or []
        
        tables_to_clear = [
            "balance_history",
            "user_balances", 
            "sessions",
            "telegram_auth",
            "wallets",
            "tokens",
            "users"
        ]
        
        for table in tables_to_clear:
            if table not in preserve:
                try:
                    self.db.truncate_table(table, cascade=True)
                except Exception as e:
                    logger.warning(f"Could not truncate {table}: {e}")
        
        logger.info("Test data cleared")
    
    def get_stats(self) -> Dict[str, int]:
        """Get current database statistics"""
        tables = ["users", "wallets", "tokens", "user_balances", "sessions"]
        stats = {}
        for table in tables:
            try:
                stats[table] = self.db.get_table_count(table)
            except:
                stats[table] = 0
        return stats
    
    def verify_setup(self) -> bool:
        """Verify database tables exist"""
        required_tables = ["users", "wallets", "tokens", "user_balances"]
        for table in required_tables:
            if not self.db.table_exists(table):
                logger.error(f"Required table missing: {table}")
                return False
        return True


# Global seeder instance
seeder = PostgresSeeder()

