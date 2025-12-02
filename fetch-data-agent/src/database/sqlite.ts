// SQLite database connection and utilities
import { open, Database } from 'sqlite';
import sqlite3 from 'sqlite3';
import * as path from 'path';
import * as fs from 'fs';
import { createSchema } from './schema';

let dbInstance: Database | null = null;

export const getDatabase = async (): Promise<Database> => {
  if (dbInstance) {
    return dbInstance;
  }

  const dbPath = process.env.DB_PATH || './data/user_data.db';
  const dbDir = path.dirname(dbPath);

  // Create directory if it doesn't exist
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  // Open database connection
  // sqlite package requires driver to be specified
  dbInstance = await open({
    filename: dbPath,
    driver: sqlite3.Database
  });
  
  // Enable WAL mode for better concurrency
  await dbInstance.exec('PRAGMA journal_mode = WAL');
  
  // Create schema
  await createSchema(dbInstance);

  console.log(`✅ Connected to SQLite database: ${dbPath}`);
  
  return dbInstance;
};

export const closeDatabase = async (): Promise<void> => {
  if (dbInstance) {
    await dbInstance.close();
    dbInstance = null;
    console.log('✅ Database connection closed');
  }
};

export type { Database };
