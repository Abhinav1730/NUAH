// Types for user data structures
export interface UserProfile {
  id: number;
  username: string | null;
  email: string | null;
  public_key: string;
  solana_address: string | null;
  cosmos_address: string | null;
  telegram_id: string | null;
  farcaster_fid: number | null;
  farcaster_username: string | null;
  farcaster_display_name: string | null;
  farcaster_pfp_url: string | null;
  google_sub: string | null;
  google_name: string | null;
  google_picture: string | null;
  wallet_signup_chain: string | null;
  referral_slots: number;
  free_token_creations: number;
  created_at: Date;
  updated_at: Date;
}

export interface UserBalance {
  token_mint: string;
  balance: string;
  updated_at: Date;
}

export interface UserTransaction {
  id?: number;
  transaction_type: string;
  token_mint_address: string;
  token_amount_lamports: string;
  solana_signature: string;
  transaction_timestamp?: Date;
  ndollar_amount?: string | null;
  ndollar_mint_address?: string | null;
  destination_address?: string | null;
  counterparty_token_mint_address?: string | null;
  counterparty_amount_lamports?: string | null;
}

export interface PortfolioToken {
  mint_address: string;
  balance: string;
  name: string | null;
  symbol: string | null;
  image_url: string | null;
  price_ndollar: string;
  price_sol: string;
  value_ndollar: string;
  value_sol: string;
}

export interface UserPortfolio {
  tokens: PortfolioToken[];
  totalValueNDollar: string;
  totalValueSOL: string;
  count: number;
}

export interface BotConfig {
  id: string;
  name: string;
  description?: string;
  strategy: string;
  parameters: Record<string, any>;
  risk_level: 'low' | 'medium' | 'high';
  max_position_size: number;
  stop_loss_percent: number;
  take_profit_percent: number;
  allowed_tokens: string[];
  trading_hours?: [number, number];
  max_trades_per_day?: number;
  is_active: boolean;
  positions: any[];
  created_at: Date;
  updated_at: Date;
}

export interface MarketData {
  token_mint: string;
  name: string;
  symbol: string;
  price_ndollar: string;
  price_sol: string;
  price_change_24h: string;
  volume_24h_sol: string;
  market_cap_ndollar: string;
}

export interface UserData {
  userId: number;
  profile: UserProfile;
  balances: UserBalance[];
  transactions: UserTransaction[];
  portfolio: UserPortfolio;
  bots: BotConfig[];
  marketData: MarketData[];
  fetchedAt: string;
}

export interface BatchUserData {
  users: Array<{
    userId: number;
    profile: Partial<UserProfile>;
    balances: UserBalance[];
    bots: Array<Partial<BotConfig>>;
  }>;
  total: number;
  fetchedAt: string;
}



