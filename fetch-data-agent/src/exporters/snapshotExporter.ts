import { promises as fs } from 'fs';
import path from 'path';
import { parse } from 'protobufjs';
import type { Type } from 'protobufjs';

import { UserData, PortfolioToken as SnapshotToken } from '../types/userData.types';

const SNAPSHOT_PROTO = `
syntax = "proto3";
package nuah;

message Profile {
  uint32 id = 1;
  string username = 2;
  string email = 3;
  string public_key = 4;
  string solana_address = 5;
  string cosmos_address = 6;
  string telegram_id = 7;
  int64 farcaster_fid = 8;
  string farcaster_username = 9;
  string farcaster_display_name = 10;
  string farcaster_pfp_url = 11;
  string google_sub = 12;
  string google_name = 13;
  string google_picture = 14;
  string wallet_signup_chain = 15;
  uint32 referral_slots = 16;
  uint32 free_token_creations = 17;
  string created_at = 18;
  string updated_at = 19;
}

message Balance {
  string token_mint = 1;
  string balance = 2;
  string updated_at = 3;
}

message Transaction {
  string transaction_type = 1;
  string token_mint = 2;
  string amount = 3;
  string signature = 4;
  string timestamp = 5;
  string ndollar_amount = 6;
  string ndollar_mint_address = 7;
  string destination_address = 8;
  string counterparty_token_mint_address = 9;
  string counterparty_amount_lamports = 10;
}

message PortfolioToken {
  string mint_address = 1;
  string balance = 2;
  string value_ndollar = 3;
  string value_sol = 4;
  string name = 5;
  string symbol = 6;
  string image_url = 7;
}

message Portfolio {
  repeated PortfolioToken tokens = 1;
  string total_value_ndollar = 2;
  string total_value_sol = 3;
  uint32 count = 4;
}

message Bot {
  string bot_id = 1;
  string name = 2;
  string strategy = 3;
  string risk_level = 4;
  double max_position_size = 5;
  double stop_loss_percent = 6;
  double take_profit_percent = 7;
  bool is_active = 8;
  string config_json = 9;
}

message MarketData {
  string token_mint = 1;
  string name = 2;
  string symbol = 3;
  string price_ndollar = 4;
  string price_sol = 5;
  string price_change_24h = 6;
  string volume_24h_sol = 7;
  string market_cap_ndollar = 8;
  string updated_at = 9;
}

message UserSnapshot {
  uint32 user_id = 1;
  string schema_version = 2;
  string generated_at = 3;
  string source_agent = 4;
  Profile profile = 5;
  repeated Balance balances = 6;
  repeated Transaction transactions = 7;
  Portfolio portfolio = 8;
  repeated Bot bots = 9;
  repeated MarketData market_data = 10;
}
`;

type ExporterOptions = {
  outputDir?: string;
  schemaVersion?: string;
  sourceAgent?: string;
};

export class SnapshotExporter {
  private readonly outputDir: string;
  private readonly schemaVersion: string;
  private readonly sourceAgent: string;
  private readonly typePromise: Promise<Type>;

  constructor(options?: ExporterOptions) {
    this.outputDir =
      options?.outputDir ??
      path.resolve(process.env.SNAPSHOT_OUTPUT_DIR ?? path.join(process.cwd(), 'data', 'snapshots'));
    this.schemaVersion = options?.schemaVersion ?? process.env.SNAPSHOT_SCHEMA_VERSION ?? '1.0.0';
    this.sourceAgent = options?.sourceAgent ?? 'fetch-data-agent';
    this.typePromise = Promise.resolve().then(() => parse(SNAPSHOT_PROTO).root.lookupType('nuah.UserSnapshot'));
  }

  async writeSnapshots(userData: UserData): Promise<void> {
    const generatedAt = new Date().toISOString();
    await fs.mkdir(this.outputDir, { recursive: true });

    const jsonEnvelope = {
      schemaVersion: this.schemaVersion,
      generatedAt,
      sourceAgent: this.sourceAgent,
      snapshot: userData,
    };

    const baseName = `user_${userData.userId}`;
    const jsonPath = path.join(this.outputDir, `${baseName}.json`);
    const toonPath = path.join(this.outputDir, `${baseName}.toon`);

    await fs.writeFile(jsonPath, JSON.stringify(jsonEnvelope, null, 2), 'utf-8');
    await this.writeToonFile(toonPath, userData, generatedAt);
  }

  private async writeToonFile(filePath: string, userData: UserData, generatedAt: string): Promise<void> {
    const type = await this.typePromise;
    const messagePayload = {
      user_id: userData.userId,
      schema_version: this.schemaVersion,
      generated_at: generatedAt,
      source_agent: this.sourceAgent,
      profile: this.serializeProfile(userData),
      balances: userData.balances?.map((balance) => ({
        token_mint: balance.token_mint ?? '',
        balance: balance.balance ?? '0',
        updated_at: this.asIsoString(balance.updated_at),
      })) ?? [],
      transactions: userData.transactions?.map((tx) => ({
        transaction_type: tx.transaction_type ?? '',
        token_mint: tx.token_mint_address ?? '',
        amount: tx.token_amount_lamports ?? '',
        signature: tx.solana_signature ?? '',
        timestamp: this.asIsoString(tx.transaction_timestamp),
        ndollar_amount: tx.ndollar_amount ?? '',
        ndollar_mint_address: tx.ndollar_mint_address ?? '',
        destination_address: tx.destination_address ?? '',
        counterparty_token_mint_address: tx.counterparty_token_mint_address ?? '',
        counterparty_amount_lamports: tx.counterparty_amount_lamports ?? '',
      })) ?? [],
      portfolio: this.serializePortfolio(userData.portfolio),
      bots: userData.bots?.map((bot) => ({
        bot_id: bot.id ?? '',
        name: bot.name ?? '',
        strategy: bot.strategy ?? '',
        risk_level: bot.risk_level ?? '',
        max_position_size: bot.max_position_size ?? 0,
        stop_loss_percent: bot.stop_loss_percent ?? 0,
        take_profit_percent: bot.take_profit_percent ?? 0,
        is_active: !!bot.is_active,
        config_json: JSON.stringify(bot.parameters ?? {}),
      })) ?? [],
      market_data: userData.marketData?.map((market) => ({
        token_mint: market.token_mint ?? '',
        name: market.name ?? '',
        symbol: market.symbol ?? '',
        price_ndollar: market.price_ndollar ?? '',
        price_sol: market.price_sol ?? '',
        price_change_24h: market.price_change_24h ?? '',
        volume_24h_sol: market.volume_24h_sol ?? '',
        market_cap_ndollar: market.market_cap_ndollar ?? '',
        updated_at: generatedAt,
      })) ?? [],
    };

    const errMsg = type.verify(messagePayload);
    if (errMsg) {
      throw new Error(`Snapshot protobuf verification failed: ${errMsg}`);
    }
    const buffer = type.encode(messagePayload).finish();
    await fs.writeFile(filePath, buffer);
  }

  private serializeProfile(userData: UserData) {
    const profile = userData.profile;
    return {
      id: profile.id ?? 0,
      username: profile.username ?? '',
      email: profile.email ?? '',
      public_key: profile.public_key ?? '',
      solana_address: profile.solana_address ?? '',
      cosmos_address: profile.cosmos_address ?? '',
      telegram_id: profile.telegram_id ?? '',
      farcaster_fid: profile.farcaster_fid ?? 0,
      farcaster_username: profile.farcaster_username ?? '',
      farcaster_display_name: profile.farcaster_display_name ?? '',
      farcaster_pfp_url: profile.farcaster_pfp_url ?? '',
      google_sub: profile.google_sub ?? '',
      google_name: profile.google_name ?? '',
      google_picture: profile.google_picture ?? '',
      wallet_signup_chain: profile.wallet_signup_chain ?? '',
      referral_slots: profile.referral_slots ?? 0,
      free_token_creations: profile.free_token_creations ?? 0,
      created_at: this.asIsoString(profile.created_at),
      updated_at: this.asIsoString(profile.updated_at),
    };
  }

  private serializePortfolio(portfolio: UserData['portfolio']) {
    if (!portfolio) {
      return { tokens: [], total_value_ndollar: '0', total_value_sol: '0', count: 0 };
    }

    return {
      tokens:
        portfolio.tokens?.map((token: SnapshotToken) => ({
          mint_address: (token as Record<string, string | undefined>).mint_address ??
            (token as Record<string, string | undefined>).token_mint ??
            '',
          balance: token.balance ?? '0',
          value_ndollar: token.value_ndollar ?? '0',
          value_sol: token.value_sol ?? '0',
          name: token.name ?? '',
          symbol: token.symbol ?? '',
          image_url: token.image_url ?? '',
        })) ?? [],
      total_value_ndollar: portfolio.totalValueNDollar ?? '0',
      total_value_sol: portfolio.totalValueSOL ?? '0',
      count: portfolio.count ?? 0,
    };
  }

  private asIsoString(value?: Date | string | null): string {
    if (!value) {
      return '';
    }
    if (value instanceof Date) {
      return value.toISOString();
    }
    return new Date(value).toISOString();
  }
}

