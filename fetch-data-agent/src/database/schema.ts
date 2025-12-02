// SQLite database schema for user data
import { Database } from 'sqlite';

export const createSchema = async (db: Database): Promise<void> => {
  // Users table - user profiles
  await db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER UNIQUE NOT NULL,
      username TEXT,
      email TEXT,
      public_key TEXT NOT NULL,
      solana_address TEXT,
      cosmos_address TEXT,
      telegram_id TEXT,
      farcaster_fid INTEGER,
      farcaster_username TEXT,
      farcaster_display_name TEXT,
      farcaster_pfp_url TEXT,
      google_sub TEXT,
      google_name TEXT,
      google_picture TEXT,
      wallet_signup_chain TEXT,
      referral_slots INTEGER DEFAULT 0,
      free_token_creations INTEGER DEFAULT 0,
      created_at TIMESTAMP,
      updated_at TIMESTAMP,
      last_fetched_at TIMESTAMP,
      data_json TEXT
    )
  `);

  // User balances table
  await db.exec(`
    CREATE TABLE IF NOT EXISTS user_balances (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      token_mint TEXT NOT NULL,
      balance TEXT NOT NULL,
      updated_at TIMESTAMP,
      last_fetched_at TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
      UNIQUE(user_id, token_mint)
    )
  `);

  // User transactions table
  await db.exec(`
    CREATE TABLE IF NOT EXISTS user_transactions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      transaction_id INTEGER,
      transaction_type TEXT,
      token_mint TEXT,
      amount TEXT,
      signature TEXT UNIQUE,
      timestamp TIMESTAMP,
      ndollar_amount TEXT,
      ndollar_mint_address TEXT,
      destination_address TEXT,
      counterparty_token_mint_address TEXT,
      counterparty_amount_lamports TEXT,
      last_fetched_at TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
  `);

  // User portfolios table
  await db.exec(`
    CREATE TABLE IF NOT EXISTS user_portfolios (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      total_value_ndollar TEXT,
      total_value_sol TEXT,
      token_count INTEGER,
      snapshot_json TEXT,
      created_at TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
  `);

  // User bots table
  await db.exec(`
    CREATE TABLE IF NOT EXISTS user_bots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      bot_id TEXT NOT NULL,
      bot_config_json TEXT,
      is_active INTEGER DEFAULT 0,
      last_fetched_at TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
      UNIQUE(user_id, bot_id)
    )
  `);

  // Market data table
  await db.exec(`
    CREATE TABLE IF NOT EXISTS market_data (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      token_mint TEXT UNIQUE NOT NULL,
      name TEXT,
      symbol TEXT,
      price_ndollar TEXT,
      price_sol TEXT,
      price_change_24h TEXT,
      volume_24h_sol TEXT,
      market_cap_ndollar TEXT,
      updated_at TIMESTAMP
    )
  `);

  // Create indexes for better query performance
  await db.exec(`
    CREATE INDEX IF NOT EXISTS idx_user_balances_user_token 
    ON user_balances(user_id, token_mint)
  `);

  await db.exec(`
    CREATE INDEX IF NOT EXISTS idx_user_transactions_user_time 
    ON user_transactions(user_id, timestamp)
  `);

  await db.exec(`
    CREATE INDEX IF NOT EXISTS idx_user_bots_active 
    ON user_bots(user_id, is_active)
  `);

  await db.exec(`
    CREATE INDEX IF NOT EXISTS idx_user_transactions_signature 
    ON user_transactions(signature)
  `);

  console.log('✅ Database schema created successfully');
};
