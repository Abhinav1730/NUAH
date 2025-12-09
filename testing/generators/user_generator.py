"""
User Generator
==============
Generates 1000 test users with wallets, balances, and preferences.
"""

import logging
import random
import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config, DATA_DIR
from database.seed_postgres import PostgresSeeder, seeder

logger = logging.getLogger(__name__)


class UserGenerator:
    """
    Generates test users with realistic profiles for the trading simulation.
    
    Features:
    - 1000 test users with unique emails/usernames
    - Auto-generated wallets with addresses
    - Varied initial balances and risk profiles
    - 5 designated agent-managed users
    """
    
    def __init__(self, seeder: PostgresSeeder = None):
        self.seeder = seeder or PostgresSeeder()
        self.config = config.users
        self.generated_users: List[Dict[str, Any]] = []
        self.generated_wallets: List[Dict[str, Any]] = []
    
    def generate_username(self, index: int) -> str:
        """Generate a unique username"""
        prefixes = [
            "trader", "crypto", "degen", "moon", "diamond", "whale",
            "ape", "hodler", "bull", "rocket", "gem", "alpha"
        ]
        suffixes = [
            "master", "king", "lord", "hunter", "hands", "pro",
            "guru", "wizard", "ninja", "boss", "chad", "legend"
        ]
        
        if index <= 5:
            # Special names for agent users
            return f"agent_user_{index}"
        
        prefix = random.choice(prefixes)
        suffix = random.choice(suffixes)
        number = random.randint(1, 9999)
        
        return f"{prefix}_{suffix}_{number}"
    
    def generate_email(self, username: str) -> str:
        """Generate an email from username"""
        domains = ["test.nuah.io", "testmail.com", "demo.nuah.io"]
        domain = random.choice(domains)
        return f"{username}@{domain}"
    
    def generate_wallet_address(self, user_id: int) -> str:
        """Generate a deterministic wallet address"""
        # Create a deterministic address based on user_id
        seed = f"test_user_{user_id}_{secrets.token_hex(8)}"
        address_hash = hashlib.sha256(seed.encode()).hexdigest()[:40]
        return f"nuah{address_hash}"
    
    def generate_password_hash(self) -> str:
        """Generate a dummy password hash (bcrypt format)"""
        # This is a bcrypt hash of "testpassword123"
        # In real use, you'd want proper password hashing
        return "$2a$10$dummy.hash.for.testing.purposes.only.not.secure"
    
    def assign_risk_profile(self) -> str:
        """Assign a risk profile based on configured distribution"""
        profiles = list(self.config.risk_profiles.keys())
        weights = list(self.config.risk_profiles.values())
        return random.choices(profiles, weights=weights, k=1)[0]
    
    def generate_initial_balance(self, risk_profile: str) -> float:
        """Generate initial NUAH balance based on risk profile"""
        min_bal = self.config.min_initial_balance_nuah
        max_bal = self.config.max_initial_balance_nuah
        
        # Risk profile affects starting capital
        multipliers = {
            "conservative": (0.5, 1.5),
            "moderate": (0.8, 2.0),
            "aggressive": (1.2, 3.0)
        }
        
        mult_range = multipliers.get(risk_profile, (0.8, 2.0))
        base = random.uniform(min_bal, max_bal)
        multiplier = random.uniform(*mult_range)
        
        return round(base * multiplier, 2)
    
    def generate_user_preferences(self, risk_profile: str) -> Dict[str, Any]:
        """Generate trading preferences based on risk profile"""
        preferences = {
            "conservative": {
                "max_position_ndollar": random.uniform(50, 200),
                "max_trades_per_day": random.randint(1, 3),
                "risk_level": "low",
                "stop_loss_percent": 0.05,
                "take_profit_percent": 0.10
            },
            "moderate": {
                "max_position_ndollar": random.uniform(200, 500),
                "max_trades_per_day": random.randint(3, 5),
                "risk_level": "medium",
                "stop_loss_percent": 0.10,
                "take_profit_percent": 0.25
            },
            "aggressive": {
                "max_position_ndollar": random.uniform(500, 2000),
                "max_trades_per_day": random.randint(5, 10),
                "risk_level": "high",
                "stop_loss_percent": 0.20,
                "take_profit_percent": 0.50
            }
        }
        
        return preferences.get(risk_profile, preferences["moderate"])
    
    def generate_single_user(self, index: int, is_agent_user: bool = False) -> Dict[str, Any]:
        """
        Generate a single test user with all attributes.
        
        Args:
            index: User index (1-based)
            is_agent_user: Whether this user is managed by the trading agent
            
        Returns:
            Complete user data dictionary
        """
        username = self.generate_username(index)
        email = self.generate_email(username)
        risk_profile = self.assign_risk_profile()
        
        user = {
            "index": index,
            "username": username,
            "email": email,
            "password_hash": self.generate_password_hash(),
            "risk_profile": risk_profile,
            "initial_balance_nuah": self.generate_initial_balance(risk_profile),
            "preferences": self.generate_user_preferences(risk_profile),
            "is_agent_user": is_agent_user,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        return user
    
    def generate_users(
        self,
        count: int = None,
        agent_user_ids: List[int] = None,
        save_to_db: bool = True,
        save_to_file: bool = True
    ) -> tuple:
        """
        Generate test users and their wallets.
        
        Args:
            count: Number of users to generate (default: from config)
            agent_user_ids: List of user indices to mark as agent-managed
            save_to_db: Whether to save to PostgreSQL
            save_to_file: Whether to save to JSON file
            
        Returns:
            Tuple of (users_list, wallets_list)
        """
        count = count or self.config.total_users
        agent_user_ids = agent_user_ids or self.config.agent_user_ids
        
        logger.info(f"Generating {count} test users ({len(agent_user_ids)} agent users)...")
        
        users = []
        wallets = []
        
        for i in range(1, count + 1):
            is_agent = i in agent_user_ids
            user = self.generate_single_user(i, is_agent_user=is_agent)
            users.append(user)
            
            if (i) % 200 == 0:
                logger.info(f"Generated {i}/{count} users")
        
        self.generated_users = users
        
        # Save to database and create wallets
        if save_to_db:
            user_ids = self._save_users_to_database(users)
            wallets = self._create_wallets(users, user_ids)
            self.generated_wallets = wallets
        
        # Save to file
        if save_to_file:
            self._save_to_file(users, wallets)
        
        logger.info(f"✅ Generated {len(users)} users with {len(wallets)} wallets")
        return users, wallets
    
    def _save_users_to_database(self, users: List[Dict[str, Any]]) -> List[int]:
        """Save users to PostgreSQL and return user IDs"""
        users_data = []
        for user in users:
            users_data.append({
                "email": user["email"],
                "username": user["username"],
                "password_hash": user["password_hash"]
            })
        
        user_ids = self.seeder.bulk_create_users(users_data)
        
        # Update users with their database IDs
        for i, user_id in enumerate(user_ids):
            if i < len(users):
                users[i]["user_id"] = user_id
        
        return user_ids
    
    def _create_wallets(self, users: List[Dict[str, Any]], user_ids: List[int]) -> List[Dict[str, Any]]:
        """Create wallets for users"""
        wallets_data = []
        wallets = []
        
        for i, (user, user_id) in enumerate(zip(users, user_ids)):
            address = self.generate_wallet_address(user_id)
            wallet = {
                "user_id": user_id,
                "address": address,
                "user_index": user["index"]
            }
            wallets.append(wallet)
            wallets_data.append({
                "user_id": user_id,
                "address": address
            })
            
            # Update user with wallet address
            user["wallet_address"] = address
        
        self.seeder.bulk_create_wallets(wallets_data)
        return wallets
    
    def _save_to_file(self, users: List[Dict[str, Any]], wallets: List[Dict[str, Any]]):
        """Save users and wallets to JSON files"""
        users_filepath = DATA_DIR / "generated_users.json"
        with open(users_filepath, 'w') as f:
            json.dump(users, f, indent=2, default=str)
        logger.info(f"Saved users to {users_filepath}")
        
        wallets_filepath = DATA_DIR / "generated_wallets.json"
        with open(wallets_filepath, 'w') as f:
            json.dump(wallets, f, indent=2, default=str)
        logger.info(f"Saved wallets to {wallets_filepath}")
    
    def load_from_file(self) -> tuple:
        """Load previously generated users and wallets from files"""
        users_filepath = DATA_DIR / "generated_users.json"
        wallets_filepath = DATA_DIR / "generated_wallets.json"
        
        users = []
        wallets = []
        
        if users_filepath.exists():
            with open(users_filepath, 'r') as f:
                users = json.load(f)
                self.generated_users = users
        
        if wallets_filepath.exists():
            with open(wallets_filepath, 'r') as f:
                wallets = json.load(f)
                self.generated_wallets = wallets
        
        return users, wallets
    
    def get_agent_users(self) -> List[Dict[str, Any]]:
        """Get all agent-managed users"""
        return [u for u in self.generated_users if u.get("is_agent_user")]
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by database ID"""
        for user in self.generated_users:
            if user.get("user_id") == user_id:
                return user
        return None
    
    def get_user_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Get user by generation index"""
        for user in self.generated_users:
            if user.get("index") == index:
                return user
        return None
    
    def get_wallet_by_user_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get wallet by user ID"""
        for wallet in self.generated_wallets:
            if wallet.get("user_id") == user_id:
                return wallet
        return None


class PortfolioGenerator:
    """
    Generates initial portfolios (coin holdings) for users.
    """
    
    def __init__(self, seeder: PostgresSeeder = None):
        self.seeder = seeder or PostgresSeeder()
        self.config = config.users
    
    def assign_coins_to_users(
        self,
        users: List[Dict[str, Any]],
        coins: List[Dict[str, Any]],
        save_to_db: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Assign random coin holdings to users.
        
        Args:
            users: List of user data
            coins: List of coin data
            save_to_db: Whether to save balances to database
            
        Returns:
            List of balance entries
        """
        logger.info(f"Assigning coins to {len(users)} users from {len(coins)} available coins...")
        
        all_balances = []
        
        for user in users:
            user_id = user.get("user_id")
            wallet_address = user.get("wallet_address")
            
            if not user_id or not wallet_address:
                continue
            
            # Determine how many coins this user holds
            num_coins = random.randint(
                self.config.min_coins_per_user,
                min(self.config.max_coins_per_user, len(coins))
            )
            
            # Select random coins
            user_coins = random.sample(coins, num_coins)
            
            # Create NUAH balance (base currency)
            nuah_balance = user.get("initial_balance_nuah", 1000.0)
            all_balances.append({
                "user_id": user_id,
                "address": wallet_address,
                "denom": "unuah",  # Base currency
                "amount": str(int(nuah_balance * 1_000_000))  # Micro-units
            })
            
            # Allocate remaining balance to coins
            remaining_value = nuah_balance * random.uniform(0.3, 0.7)  # 30-70% in coins
            
            for coin in user_coins:
                # Random allocation for this coin
                allocation = remaining_value / num_coins * random.uniform(0.5, 1.5)
                price = coin.get("initial_price", 0.001)
                amount = int(allocation / price * 1_000_000)  # Micro-units
                
                all_balances.append({
                    "user_id": user_id,
                    "address": wallet_address,
                    "denom": coin["denom"],
                    "amount": str(amount)
                })
            
            # Store holdings in user object
            user["holdings"] = [c["symbol"] for c in user_coins]
        
        # Save to database
        if save_to_db and all_balances:
            self.seeder.bulk_create_balances(all_balances)
            logger.info(f"Created {len(all_balances)} balance entries")
        
        return all_balances


# Convenience function
def generate_test_users(count: int = 1000) -> tuple:
    """Quick function to generate test users"""
    generator = UserGenerator()
    return generator.generate_users(count=count)


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Generate users
    generator = UserGenerator()
    users, wallets = generator.generate_users(count=100, save_to_db=False, save_to_file=True)
    
    # Print sample
    print("\n👥 Sample Generated Users:")
    for user in users[:5]:
        print(f"  • {user['username']}: {user['email']}")
        print(f"    Risk: {user['risk_profile']} | Balance: ${user['initial_balance_nuah']:.2f}")
        print(f"    Agent User: {'✅' if user['is_agent_user'] else '❌'}")
    
    print(f"\n🤖 Agent Users: {[u['username'] for u in generator.get_agent_users()]}")

