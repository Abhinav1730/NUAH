// Service for storing and retrieving data from SQLite
import sqlite from 'sqlite';
import { Database } from '../database/sqlite';
import { UserData } from '../types/userData.types';

export class DataService {
  private db: Database;

  constructor(db: Database) {
    this.db = db;
  }

  /**
   * Store or update user data in SQLite
   */
  async storeUserData(userData: UserData): Promise<void> {
    const now = new Date().toISOString();

    // Begin transaction
    await this.db.run('BEGIN TRANSACTION');
    
    try {
      // Upsert user profile
      await this.db.run(`
        INSERT INTO users (
          user_id, username, email, public_key, solana_address, cosmos_address,
          telegram_id, farcaster_fid, farcaster_username, farcaster_display_name,
          farcaster_pfp_url, google_sub, google_name, google_picture,
          wallet_signup_chain, referral_slots, free_token_creations,
          created_at, updated_at, last_fetched_at, data_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
          username = excluded.username,
          email = excluded.email,
          public_key = excluded.public_key,
          solana_address = excluded.solana_address,
          cosmos_address = excluded.cosmos_address,
          telegram_id = excluded.telegram_id,
          farcaster_fid = excluded.farcaster_fid,
          farcaster_username = excluded.farcaster_username,
          farcaster_display_name = excluded.farcaster_display_name,
          farcaster_pfp_url = excluded.farcaster_pfp_url,
          google_sub = excluded.google_sub,
          google_name = excluded.google_name,
          google_picture = excluded.google_picture,
          wallet_signup_chain = excluded.wallet_signup_chain,
          referral_slots = excluded.referral_slots,
          free_token_creations = excluded.free_token_creations,
          updated_at = excluded.updated_at,
          last_fetched_at = excluded.last_fetched_at,
          data_json = excluded.data_json
      `, [
        userData.userId,
        userData.profile.username,
        userData.profile.email,
        userData.profile.public_key,
        userData.profile.solana_address,
        userData.profile.cosmos_address,
        userData.profile.telegram_id,
        userData.profile.farcaster_fid,
        userData.profile.farcaster_username,
        userData.profile.farcaster_display_name,
        userData.profile.farcaster_pfp_url,
        userData.profile.google_sub,
        userData.profile.google_name,
        userData.profile.google_picture,
        userData.profile.wallet_signup_chain,
        userData.profile.referral_slots,
        userData.profile.free_token_creations,
        userData.profile.created_at,
        userData.profile.updated_at,
        now,
        JSON.stringify(userData)
      ]);

      // Delete old balances and insert new ones
      await this.db.run('DELETE FROM user_balances WHERE user_id = ?', [userData.userId]);
      for (const balance of userData.balances) {
        await this.db.run(`
          INSERT INTO user_balances (user_id, token_mint, balance, updated_at, last_fetched_at)
          VALUES (?, ?, ?, ?, ?)
        `, [
          userData.userId,
          balance.token_mint,
          balance.balance,
          balance.updated_at,
          now
        ]);
      }

      // Insert new transactions (skip duplicates by signature)
      for (const tx of userData.transactions) {
        await this.db.run(`
          INSERT OR IGNORE INTO user_transactions (
            user_id, transaction_id, transaction_type, token_mint, amount, signature,
            timestamp, ndollar_amount, ndollar_mint_address, destination_address,
            counterparty_token_mint_address, counterparty_amount_lamports, last_fetched_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `, [
          userData.userId,
          tx.id || null,
          tx.transaction_type,
          tx.token_mint_address,
          tx.token_amount_lamports,
          tx.solana_signature,
          tx.transaction_timestamp || null,
          tx.ndollar_amount || null,
          tx.ndollar_mint_address || null,
          tx.destination_address || null,
          tx.counterparty_token_mint_address || null,
          tx.counterparty_amount_lamports || null,
          now
        ]);
      }

      // Store portfolio snapshot
      await this.db.run(`
        INSERT INTO user_portfolios (
          user_id, total_value_ndollar, total_value_sol, token_count, snapshot_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
      `, [
        userData.userId,
        userData.portfolio.totalValueNDollar,
        userData.portfolio.totalValueSOL,
        userData.portfolio.count,
        JSON.stringify(userData.portfolio),
        now
      ]);

      // Delete old bots and insert new ones
      await this.db.run('DELETE FROM user_bots WHERE user_id = ?', [userData.userId]);
      for (const bot of userData.bots) {
        await this.db.run(`
          INSERT INTO user_bots (user_id, bot_id, bot_config_json, is_active, last_fetched_at)
          VALUES (?, ?, ?, ?, ?)
        `, [
          userData.userId,
          bot.id,
          JSON.stringify(bot),
          bot.is_active ? 1 : 0,
          now
        ]);
      }

      // Store market data
      for (const market of userData.marketData) {
        await this.db.run(`
          INSERT INTO market_data (
            token_mint, name, symbol, price_ndollar, price_sol,
            price_change_24h, volume_24h_sol, market_cap_ndollar, updated_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
          ON CONFLICT(token_mint) DO UPDATE SET
            name = excluded.name,
            symbol = excluded.symbol,
            price_ndollar = excluded.price_ndollar,
            price_sol = excluded.price_sol,
            price_change_24h = excluded.price_change_24h,
            volume_24h_sol = excluded.volume_24h_sol,
            market_cap_ndollar = excluded.market_cap_ndollar,
            updated_at = excluded.updated_at
        `, [
          market.token_mint,
          market.name,
          market.symbol,
          market.price_ndollar,
          market.price_sol,
          market.price_change_24h,
          market.volume_24h_sol,
          market.market_cap_ndollar,
          now
        ]);
      }

      await this.db.run('COMMIT');
      console.log(`✅ Stored data for user ${userData.userId}`);
    } catch (error) {
      await this.db.run('ROLLBACK');
      throw error;
    }
  }

  /**
   * Get list of user IDs that need to be fetched
   * For now, returns all user IDs from database
   * Can be extended to filter by last_fetched_at
   */
  async getUsersToFetch(): Promise<number[]> {
    // SQLite doesn't support NULLS FIRST, so we use COALESCE to handle NULLs
    const users = await this.db.all(`
      SELECT user_id FROM users 
      ORDER BY COALESCE(last_fetched_at, '1970-01-01') ASC
    `) as Array<{ user_id: number }>;
    return users.map((u) => u.user_id);
  }

  /**
   * Get count of users in database
   */
  async getUserCount(): Promise<number> {
    const result = await this.db.get('SELECT COUNT(*) as count FROM users') as { count: number };
    return result.count;
  }

  /**
   * Get users with active bots
   */
  async getUsersWithActiveBots(): Promise<number[]> {
    const users = await this.db.all(`
      SELECT DISTINCT user_id 
      FROM user_bots 
      WHERE is_active = 1
    `) as Array<{ user_id: number }>;
    return users.map((u) => u.user_id);
  }
}
