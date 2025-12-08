import axios, { AxiosInstance } from 'axios';
import {
  BatchUserData,
  MarketData,
  PortfolioToken,
  UserBalance,
  UserData,
  UserPortfolio,
  UserProfile,
  UserTransaction,
} from '../types/userData.types';

type BalanceHistory = {
  denom: string;
  amount_before?: string | null;
  amount_after: string;
  amount_delta: string;
  tx_hash: string;
  height: number;
  event_type?: string | null;
  created_at?: string;
};

type BalanceResponse = {
  address: string;
  denom: string;
  amount: string;
  updated_at?: string;
};

type MarketplaceToken = {
  denom: string;
  name: string;
  symbol: string;
  image?: string;
  description?: string;
  creator?: string;
  current_price?: string;
  tokens_sold?: string;
  curve_completed?: boolean;
  decimals?: number;
  stats?: {
    volume_24h?: string;
    volatility_24h?: string;
    holders?: number;
  };
};

type UserMeResponse = {
  id: number;
  email?: string | null;
  username?: string | null;
  wallet?: {
    address?: string;
  };
  public_key?: string;
  solana_address?: string | null;
  cosmos_address?: string | null;
  created_at?: string;
  updated_at?: string;
};

export class ApiClient {
  private client: AxiosInstance;
  private baseUrl: string;
  private token: string;

  constructor() {
    this.baseUrl = process.env.NUAHCHAIN_API_BASE_URL || process.env.API_BASE_URL || 'http://localhost:8080';
    this.token = process.env.NUAHCHAIN_API_TOKEN || process.env.API_TOKEN || '';

    if (!this.token) {
      throw new Error('NUAHCHAIN_API_TOKEN (or API_TOKEN) environment variable is required');
    }

    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.token}`,
      },
    });

    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response) {
          console.error(`API Error [${error.response.status}]:`, error.response.data);
        } else if (error.request) {
          console.error('API Request Error:', error.message);
        } else {
          console.error('API Error:', error.message);
        }
        return Promise.reject(error);
      }
    );
  }

  async fetchUserData(userId: number): Promise<UserData | null> {
    void userId; // backend derives user from JWT
    const [profile, balances, history, marketData] = await Promise.all([
      this.getProfile(),
      this.getBalances(),
      this.getBalanceHistory(100),
      this.getMarketplaceTokens(500),
    ]);

    const portfolio = this.buildPortfolio(balances, marketData);
    const transactions = this.mapHistoryToTransactions(history);

    return {
      userId: profile.id,
      profile,
      balances,
      transactions,
      portfolio,
      bots: [],
      marketData,
      fetchedAt: new Date().toISOString(),
    };
  }

  async fetchBatchUserData(userIds: number[]): Promise<BatchUserData | null> {
    const users: BatchUserData['users'] = [];
    for (const id of userIds) {
      const data = await this.fetchUserData(id);
      if (data) {
        users.push({
          userId: data.userId,
          profile: data.profile,
          balances: data.balances,
          bots: [],
        });
      }
    }
    return {
      users,
      total: users.length,
      fetchedAt: new Date().toISOString(),
    };
  }

  async testConnection(): Promise<boolean> {
    try {
      await this.client.get('/health', { timeout: 5000 });
      return true;
    } catch (error: any) {
      console.error('API connection test failed:', error.message);
      return false;
    }
  }

  // ---- Private helpers ----

  private async getProfile(): Promise<UserProfile> {
    const res = await this.client.get<UserMeResponse>('/api/users/me');
    const p = res.data;
    return {
      id: p.id,
      username: p.username ?? null,
      email: p.email ?? null,
      public_key: p.public_key ?? '',
      solana_address: p.solana_address ?? null,
      cosmos_address: p.cosmos_address ?? p.wallet?.address ?? null,
      telegram_id: null,
      farcaster_fid: null,
      farcaster_username: null,
      farcaster_display_name: null,
      farcaster_pfp_url: null,
      google_sub: null,
      google_name: null,
      google_picture: null,
      wallet_signup_chain: null,
      referral_slots: 0,
      free_token_creations: 0,
      created_at: p.created_at ? new Date(p.created_at) : new Date(),
      updated_at: p.updated_at ? new Date(p.updated_at) : new Date(),
    };
  }

  private async getBalances(): Promise<UserBalance[]> {
    const res = await this.client.get<{ balances: BalanceResponse[] }>('/api/users/balances');
    const balances = res.data?.balances ?? [];
    return balances.map((b) => ({
      token_mint: this.denomToTokenMint(b.denom),
      balance: b.amount,
      updated_at: b.updated_at ? new Date(b.updated_at) : new Date(),
    }));
  }

  private async getBalanceHistory(limit: number): Promise<BalanceHistory[]> {
    const res = await this.client.get<{ history: BalanceHistory[] }>('/api/users/balances/history', {
      params: { limit },
    });
    return res.data?.history ?? [];
  }

  private async getMarketplaceTokens(limit: number): Promise<MarketData[]> {
    const res = await this.client.get<{ tokens: MarketplaceToken[] }>('/api/tokens/market', {
      params: { limit, offset: 0 },
    });
    const tokens = res.data?.tokens ?? [];
    return tokens.map((t) => ({
      token_mint: this.denomToTokenMint(t.denom),
      name: t.name,
      symbol: t.symbol,
      price_ndollar: t.current_price ?? '0',
      price_sol: '',
      price_change_24h: t.stats?.volatility_24h ?? '',
      volume_24h_sol: t.stats?.volume_24h ?? '',
      market_cap_ndollar: '',
    }));
  }

  private buildPortfolio(balances: UserBalance[], marketData: MarketData[]): UserPortfolio {
    const priceMap = new Map<string, number>();
    for (const m of marketData) {
      const price = parseFloat(m.price_ndollar || '0');
      priceMap.set(m.token_mint, Number.isFinite(price) ? price : 0);
    }

    const tokens: PortfolioToken[] = balances.map((b) => {
      const balanceNum = parseFloat(b.balance || '0');
      const price = priceMap.get(b.token_mint) ?? 0;
      const value = balanceNum * price;
      return {
        mint_address: b.token_mint,
        balance: b.balance,
        name: '',
        symbol: '',
        image_url: null,
        price_ndollar: price.toString(),
        price_sol: '',
        value_ndollar: value.toString(),
        value_sol: '',
      };
    });

    const totalValue = tokens.reduce((sum, t) => sum + parseFloat(t.value_ndollar || '0'), 0);

    return {
      tokens,
      totalValueNDollar: totalValue.toString(),
      totalValueSOL: '0',
      count: tokens.length,
    };
  }

  private mapHistoryToTransactions(history: BalanceHistory[]): UserTransaction[] {
    return history.map((h) => ({
      transaction_type: h.event_type || 'balance_change',
      token_mint_address: this.denomToTokenMint(h.denom),
      token_amount_lamports: h.amount_delta,
      solana_signature: h.tx_hash,
      transaction_timestamp: h.created_at ? new Date(h.created_at) : undefined,
    }));
  }

  private denomToTokenMint(denom: string): string {
    return denom;
  }
}

