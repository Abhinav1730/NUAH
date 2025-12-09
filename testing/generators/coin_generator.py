"""
Coin Generator
==============
Generates 100 dummy meme coins with pump.fun-style characteristics.
"""

import logging
import random
import hashlib
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config, DATA_DIR
from database.seed_postgres import PostgresSeeder, seeder

logger = logging.getLogger(__name__)


class CoinGenerator:
    """
    Generates dummy meme coins with realistic pump.fun-style characteristics.
    
    Features:
    - Random name generation from meme coin patterns
    - Varied initial prices and supplies
    - Different volatility profiles
    - Bonding curve parameters
    """
    
    def __init__(self, seeder: PostgresSeeder = None):
        self.seeder = seeder or PostgresSeeder()
        self.config = config.coins
        self.generated_coins: List[Dict[str, Any]] = []
    
    def generate_coin_name(self) -> tuple:
        """
        Generate a random meme coin name and symbol.
        
        Returns:
            Tuple of (name, symbol)
        """
        # Different naming strategies
        strategy = random.choice(['prefix_suffix', 'prefix_only', 'suffix_only', 'compound'])
        
        if strategy == 'prefix_suffix':
            prefix = random.choice(self.config.name_prefixes)
            suffix = random.choice(self.config.name_suffixes)
            name = f"{prefix} {suffix}"
            symbol = prefix[:4].upper()
        elif strategy == 'prefix_only':
            prefix = random.choice(self.config.name_prefixes)
            name = f"{prefix} Token"
            symbol = prefix[:4].upper()
        elif strategy == 'suffix_only':
            suffix = random.choice(self.config.name_suffixes)
            name = f"The {suffix}"
            symbol = suffix[:4].upper()
        else:  # compound
            p1 = random.choice(self.config.name_prefixes)
            p2 = random.choice(self.config.name_prefixes)
            name = f"{p1}{p2}"
            symbol = (p1[:2] + p2[:2]).upper()
        
        # Add random number suffix to ensure uniqueness
        unique_id = random.randint(100, 999)
        symbol = f"{symbol}{unique_id}"[:8]  # Max 8 chars
        
        return name, symbol
    
    def generate_denom(self, creator_address: str, symbol: str) -> str:
        """
        Generate a blockchain denom for the token.
        
        Format: factory/{creator_address}/{symbol}
        """
        return f"factory/{creator_address}/{symbol}"
    
    def generate_initial_price(self) -> float:
        """Generate a random initial price"""
        # Use log-uniform distribution for more realistic price distribution
        log_min = -4  # 0.0001
        log_max = -2  # 0.01
        return round(10 ** random.uniform(log_min, log_max), 8)
    
    def generate_total_supply(self) -> int:
        """Generate a random total supply"""
        # Common meme coin supplies
        supplies = [
            1_000_000,           # 1M
            10_000_000,          # 10M
            100_000_000,         # 100M
            1_000_000_000,       # 1B
            10_000_000_000,      # 10B
            100_000_000_000,     # 100B
            1_000_000_000_000,   # 1T
        ]
        base = random.choice(supplies)
        # Add some randomness
        multiplier = random.uniform(0.5, 2.0)
        return int(base * multiplier)
    
    def generate_volatility_profile(self) -> Dict[str, float]:
        """
        Generate volatility characteristics for a coin.
        
        Returns:
            Dict with volatility parameters
        """
        # Different coin "personalities"
        profiles = [
            {"type": "stable", "base_vol": 0.01, "pump_chance": 0.05, "dump_chance": 0.05},
            {"type": "moderate", "base_vol": 0.03, "pump_chance": 0.15, "dump_chance": 0.10},
            {"type": "volatile", "base_vol": 0.08, "pump_chance": 0.25, "dump_chance": 0.20},
            {"type": "extreme", "base_vol": 0.15, "pump_chance": 0.35, "dump_chance": 0.30},
        ]
        return random.choice(profiles)
    
    def generate_bonding_curve_params(self) -> Dict[str, Any]:
        """
        Generate bonding curve parameters.
        
        Returns:
            Dict with bonding curve configuration
        """
        curve_type = random.choice(self.config.bonding_curve_types)
        
        params = {
            "type": curve_type,
            "initial_reserve": random.randint(100, 10000),  # NUAH
            "reserve_ratio": random.uniform(0.1, 0.5),
        }
        
        if curve_type == "linear":
            params["slope"] = random.uniform(0.001, 0.01)
        elif curve_type == "exponential":
            params["exponent"] = random.uniform(1.5, 3.0)
        elif curve_type == "sigmoid":
            params["midpoint"] = random.randint(50000, 500000)
            params["steepness"] = random.uniform(0.00001, 0.0001)
        
        return params
    
    def generate_description(self, name: str, symbol: str) -> str:
        """Generate a meme coin description"""
        templates = [
            f"{name} ({symbol}) is the next 1000x gem! 🚀🌙",
            f"Community-driven {name} token. WAGMI! 💎🙌",
            f"{symbol} - To the moon and beyond! NFA DYOR 🔥",
            f"The official {name} meme token. Join the revolution! 🐸",
            f"{symbol}: Where degens become legends. LFG! 🦍",
            f"Fair launch {name}. No presale, no team tokens. Pure community! ✨",
            f"{name} - Built different. HODL for glory! 💪",
            f"The memecoin that {symbol} really is. Don't miss out! 🎯",
        ]
        return random.choice(templates)
    
    def generate_image_url(self, symbol: str) -> str:
        """Generate a placeholder image URL"""
        colors = ["FF6B6B", "4ECDC4", "45B7D1", "96CEB4", "FFEAA7", "DDA0DD", "98D8C8", "F7DC6F"]
        color = random.choice(colors)
        return f"https://via.placeholder.com/200/{color}/FFFFFF?text={symbol}"
    
    def generate_single_coin(self, creator_address: str, creator_user_id: int = None) -> Dict[str, Any]:
        """
        Generate a single dummy coin with all attributes.
        
        Args:
            creator_address: Blockchain address of the creator
            creator_user_id: Optional user ID of the creator
            
        Returns:
            Complete coin data dictionary
        """
        name, symbol = self.generate_coin_name()
        denom = self.generate_denom(creator_address, symbol)
        
        coin = {
            "denom": denom,
            "name": name,
            "symbol": symbol,
            "creator_address": creator_address,
            "creator_user_id": creator_user_id,
            "image": self.generate_image_url(symbol),
            "description": self.generate_description(name, symbol),
            "decimals": 6,
            "initial_price": self.generate_initial_price(),
            "total_supply": self.generate_total_supply(),
            "volatility_profile": self.generate_volatility_profile(),
            "bonding_curve": self.generate_bonding_curve_params(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        return coin
    
    def generate_coins(
        self, 
        count: int = None, 
        creator_address: str = None,
        creator_user_id: int = None,
        save_to_db: bool = True,
        save_to_file: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple dummy coins.
        
        Args:
            count: Number of coins to generate (default: from config)
            creator_address: Address to use as creator (default: generates one)
            creator_user_id: User ID of creator
            save_to_db: Whether to save to PostgreSQL
            save_to_file: Whether to save to JSON file
            
        Returns:
            List of generated coin data
        """
        count = count or self.config.total_coins
        
        # Generate a default creator address if not provided
        if creator_address is None:
            creator_address = f"nuah{hashlib.sha256(b'test_creator').hexdigest()[:40]}"
        
        logger.info(f"Generating {count} dummy coins...")
        
        coins = []
        seen_symbols = set()
        
        for i in range(count):
            # Generate coin, ensuring unique symbol
            attempts = 0
            while attempts < 10:
                coin = self.generate_single_coin(creator_address, creator_user_id)
                if coin['symbol'] not in seen_symbols:
                    seen_symbols.add(coin['symbol'])
                    break
                attempts += 1
            
            coins.append(coin)
            
            if (i + 1) % 25 == 0:
                logger.info(f"Generated {i + 1}/{count} coins")
        
        self.generated_coins = coins
        
        # Save to database
        if save_to_db:
            self._save_to_database(coins)
        
        # Save to file
        if save_to_file:
            self._save_to_file(coins)
        
        logger.info(f"✅ Generated {len(coins)} dummy coins")
        return coins
    
    def _save_to_database(self, coins: List[Dict[str, Any]]):
        """Save coins to PostgreSQL database"""
        tokens_data = []
        for coin in coins:
            tokens_data.append({
                "denom": coin["denom"],
                "name": coin["name"],
                "symbol": coin["symbol"],
                "creator_address": coin["creator_address"],
                "creator_user_id": coin.get("creator_user_id"),
                "image": coin.get("image"),
                "description": coin.get("description"),
                "decimals": coin.get("decimals", 6)
            })
        
        self.seeder.bulk_create_tokens(tokens_data)
        logger.info(f"Saved {len(tokens_data)} tokens to database")
    
    def _save_to_file(self, coins: List[Dict[str, Any]]):
        """Save coins to JSON file"""
        filepath = DATA_DIR / "generated_coins.json"
        with open(filepath, 'w') as f:
            json.dump(coins, f, indent=2, default=str)
        logger.info(f"Saved coins to {filepath}")
    
    def load_from_file(self) -> List[Dict[str, Any]]:
        """Load previously generated coins from file"""
        filepath = DATA_DIR / "generated_coins.json"
        if filepath.exists():
            with open(filepath, 'r') as f:
                self.generated_coins = json.load(f)
            return self.generated_coins
        return []
    
    def get_coin_by_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get a coin by its symbol"""
        for coin in self.generated_coins:
            if coin['symbol'] == symbol:
                return coin
        return None
    
    def get_random_coins(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get random coins from the generated list"""
        if not self.generated_coins:
            return []
        return random.sample(self.generated_coins, min(count, len(self.generated_coins)))
    
    def generate_market_snapshot(self) -> List[Dict[str, Any]]:
        """
        Generate a market data snapshot for all coins.
        
        Returns:
            List of market data entries
        """
        market_data = []
        for coin in self.generated_coins:
            # Simulate current market state
            price = coin['initial_price']
            price_change = random.uniform(-0.15, 0.25)
            volume = random.uniform(1000, 100000)
            market_cap = price * coin['total_supply'] / 1_000_000  # In millions
            
            market_data.append({
                "denom": coin['denom'],
                "symbol": coin['symbol'],
                "name": coin['name'],
                "price_nuah": price,
                "price_change_24h": price_change,
                "volume_24h": volume,
                "market_cap": market_cap,
                "total_supply": coin['total_supply'],
                "holders": random.randint(10, 5000),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        return market_data


# Convenience function
def generate_test_coins(count: int = 100) -> List[Dict[str, Any]]:
    """Quick function to generate test coins"""
    generator = CoinGenerator()
    return generator.generate_coins(count=count)


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Generate coins
    generator = CoinGenerator()
    coins = generator.generate_coins(count=100, save_to_db=False, save_to_file=True)
    
    # Print sample
    print("\n📊 Sample Generated Coins:")
    for coin in coins[:5]:
        print(f"  • {coin['symbol']}: {coin['name']} @ ${coin['initial_price']:.6f}")
        print(f"    Supply: {coin['total_supply']:,} | Volatility: {coin['volatility_profile']['type']}")

