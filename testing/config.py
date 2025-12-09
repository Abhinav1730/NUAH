"""
Testing Framework Configuration
================================
Central configuration for the NUAH trading agent testing suite.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
TESTING_DIR = Path(__file__).parent
DATA_DIR = TESTING_DIR / "data"
REPORTS_DIR = TESTING_DIR / "reports"


@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration for nuahchain-backend"""
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database: str = os.getenv("POSTGRES_DB", "serverdb")
    user: str = os.getenv("POSTGRES_USER", "postgres")
    password: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    
    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class APIConfig:
    """nuahchain-backend API configuration"""
    base_url: str = os.getenv("API_BASE_URL", "http://localhost:8080")
    timeout: int = 30


@dataclass
class CoinGeneratorConfig:
    """Configuration for dummy coin generation"""
    total_coins: int = 100
    
    # Coin naming patterns (pump.fun style meme coins)
    name_prefixes: List[str] = field(default_factory=lambda: [
        "DOGE", "PEPE", "SHIB", "WOJAK", "CHAD", "BASED", "MOON", "ROCKET",
        "DIAMOND", "APE", "FROG", "CAT", "PANDA", "ELON", "TRUMP", "BIDEN",
        "BONK", "WIF", "POPCAT", "BRETT", "MOG", "NEIRO", "TURBO", "FLOKI",
        "MEME", "PUMP", "DUMP", "HODL", "WAGMI", "NGMI", "GM", "GN",
        "BULL", "BEAR", "LAMBO", "REKT", "SHILL", "FUD", "FOMO", "COPE"
    ])
    
    name_suffixes: List[str] = field(default_factory=lambda: [
        "INU", "COIN", "TOKEN", "MOON", "ROCKET", "GOLD", "CASH", "KING",
        "LORD", "MASTER", "PRO", "MAX", "ULTRA", "MEGA", "SUPER", "HYPER",
        "2.0", "3.0", "AI", "GPT", "BOT", "DAO", "FI", "SWAP"
    ])
    
    # Price configuration (in NUAH - base currency)
    initial_price_min: float = 0.0001  # $0.0001
    initial_price_max: float = 0.01    # $0.01
    
    # Supply configuration
    total_supply_min: int = 1_000_000_000      # 1 billion
    total_supply_max: int = 1_000_000_000_000  # 1 trillion
    
    # Bonding curve parameters
    bonding_curve_types: List[str] = field(default_factory=lambda: [
        "linear", "exponential", "sigmoid"
    ])


@dataclass
class UserGeneratorConfig:
    """Configuration for test user generation"""
    total_users: int = 1000
    agent_user_ids: List[int] = field(default_factory=lambda: [1, 2, 3, 4, 5])
    
    # Portfolio configuration
    min_initial_balance_nuah: float = 100.0      # $100 in NUAH
    max_initial_balance_nuah: float = 10000.0    # $10,000 in NUAH
    
    # User risk profiles
    risk_profiles: Dict[str, float] = field(default_factory=lambda: {
        "conservative": 0.3,   # 30% of users
        "moderate": 0.5,       # 50% of users
        "aggressive": 0.2      # 20% of users
    })
    
    # Coins per user
    min_coins_per_user: int = 1
    max_coins_per_user: int = 15


@dataclass
class PriceSimulatorConfig:
    """Configuration for price simulation"""
    simulation_duration_hours: int = 24
    time_interval_minutes: int = 1  # Price update every 1 minute (faster for pump.fun style)
    
    # Price movement patterns (pump.fun style - FAST movements!)
    # On pump.fun, most action happens within minutes, not hours
    patterns: Dict[str, Dict] = field(default_factory=lambda: {
        "micro_pump": {
            "gain_min": 0.1,     # +10%
            "gain_max": 0.3,     # +30%
            "duration_hours": 0.15,  # 5-15 minutes
            "probability": 0.20
        },
        "mid_pump": {
            "gain_min": 0.3,     # +30%
            "gain_max": 1.0,     # +100%
            "duration_hours": 0.5,   # 15-45 minutes
            "probability": 0.15
        },
        "mega_pump": {
            "gain_min": 1.0,     # +100%
            "gain_max": 5.0,     # +500%
            "duration_hours": 1.5,   # 30 min - 2 hours
            "probability": 0.05
        },
        "organic_growth": {
            "gain_min": 0.05,    # +5%
            "gain_max": 0.20,    # +20%
            "duration_hours": 3,     # 2-6 hours
            "probability": 0.12
        },
        "sideways": {
            "gain_min": -0.08,   # -8%
            "gain_max": 0.08,    # +8%
            "duration_hours": 2,     # 1-4 hours
            "probability": 0.13
        },
        "dump": {
            "gain_min": -0.5,    # -50%
            "gain_max": -0.2,    # -20%
            "duration_hours": 0.25,  # 5-20 minutes (fast!)
            "probability": 0.15
        },
        "rug_pull": {
            "gain_min": -0.95,   # -95%
            "gain_max": -0.8,    # -80%
            "duration_hours": 0.05,  # 1-5 minutes (instant!)
            "probability": 0.05
        },
        "dead_cat_bounce": {
            "gain_min": -0.3,    # Net -30% (pumps then dumps harder)
            "gain_max": -0.1,    # Net -10%
            "duration_hours": 0.4,   # 10-30 minutes
            "probability": 0.05
        },
        "fomo_spike": {
            "gain_min": 0.5,     # +50%
            "gain_max": 2.0,     # +200%
            "duration_hours": 0.1,   # 5-10 minutes (very fast!)
            "probability": 0.10
        }
    })
    
    # Volatility settings
    base_volatility: float = 0.02  # 2% random noise
    high_volatility_multiplier: float = 3.0


@dataclass 
class AgentTestConfig:
    """Configuration for agent testing"""
    agent_user_ids: List[int] = field(default_factory=lambda: [1, 2, 3, 4, 5])
    
    # Trade agent settings
    dry_run: bool = True
    confidence_threshold: float = 0.7
    max_trades_per_day: int = 5
    max_position_percent: float = 0.25  # Max 25% of portfolio per trade
    
    # Evaluation metrics
    track_metrics: List[str] = field(default_factory=lambda: [
        "prediction_accuracy",
        "win_rate",
        "total_pnl",
        "sharpe_ratio",
        "max_drawdown",
        "trade_count",
        "avg_holding_period"
    ])


@dataclass
class TestingConfig:
    """Master configuration combining all configs"""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: APIConfig = field(default_factory=APIConfig)
    coins: CoinGeneratorConfig = field(default_factory=CoinGeneratorConfig)
    users: UserGeneratorConfig = field(default_factory=UserGeneratorConfig)
    price_sim: PriceSimulatorConfig = field(default_factory=PriceSimulatorConfig)
    agent_test: AgentTestConfig = field(default_factory=AgentTestConfig)


# Global config instance
config = TestingConfig()


def ensure_directories():
    """Create necessary directories if they don't exist"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (TESTING_DIR / "logs").mkdir(parents=True, exist_ok=True)


# Initialize directories on import
ensure_directories()

