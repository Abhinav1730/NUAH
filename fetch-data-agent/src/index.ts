import * as dotenv from 'dotenv';
import { Scheduler } from './scheduler';
import { UserDataService } from './services/userDataService';
import { getDatabase, closeDatabase } from './database/sqlite';

// Load environment variables
dotenv.config();

// Graceful shutdown
const shutdown = async (code = 0) => {
  try {
    await closeDatabase();
  } finally {
    process.exit(code);
  }
};

process.on('SIGINT', () => shutdown(0));
process.on('SIGTERM', () => shutdown(0));

async function main() {
  console.log('🚀 Starting fetch-data-agent...\n');

  if (!process.env.NUAHCHAIN_API_TOKEN && !process.env.API_TOKEN) {
    console.error('❌ NUAHCHAIN_API_TOKEN (or API_TOKEN) is required');
    process.exit(1);
  }

  if (!process.env.NUAHCHAIN_API_BASE_URL && !process.env.API_BASE_URL) {
    console.warn('⚠️ NUAHCHAIN_API_BASE_URL not set; defaulting to http://localhost:8080');
  }

  console.log('🔍 Initializing database...');
  const db = await getDatabase();
  console.log('✅ Database initialized\n');

  const userDataService = new UserDataService(db);
  const scheduler = new Scheduler(userDataService);

  // Optional immediate run
  const runImmediately = process.argv.includes('--run-now');
  if (runImmediately) {
    try {
      await scheduler.runNow();
    } catch {
      await shutdown(1);
    }
  }

  // Start scheduler
  scheduler.start();
  console.log('\n✅ fetch-data-agent is running. Press Ctrl+C to stop.\n');
}

main().catch(async (err) => {
  console.error('❌ Fatal error:', err);
  await shutdown(1);
});

