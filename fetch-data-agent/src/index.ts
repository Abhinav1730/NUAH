// Main entry point for fetch-data-agent
import * as dotenv from 'dotenv';
import { Scheduler } from './scheduler';
import { UserDataService } from './services/userDataService';
import { getDatabase, closeDatabase } from './database/sqlite';

// Load environment variables
dotenv.config();

// Handle graceful shutdown
process.on('SIGINT', async () => {
  console.log('\n🛑 Received SIGINT, shutting down gracefully...');
  await closeDatabase();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('\n🛑 Received SIGTERM, shutting down gracefully...');
  await closeDatabase();
  process.exit(0);
});

async function main() {
  console.log('🚀 Starting fetch-data-agent...\n');

  // Check environment variables
  if (!process.env.API_TOKEN) {
    console.error('❌ Error: API_TOKEN environment variable is required');
    console.error('   Please set API_TOKEN in your .env file');
    process.exit(1);
  }

  if (!process.env.API_BASE_URL) {
    console.warn('⚠️ Warning: API_BASE_URL not set, using default: http://localhost:3000');
  }

  // Initialize database
  console.log('🔍 Initializing database...');
  const db = await getDatabase();
  console.log('✅ Database initialized\n');

  // Initialize services
  const userDataService = new UserDataService(db);
  
  // Test API connection
  console.log('🔍 Testing API connection...');
  const connectionOk = await userDataService.testConnection();
  
  if (!connectionOk) {
    console.error('❌ Error: Cannot connect to API. Please check your API_BASE_URL and API_TOKEN');
    await closeDatabase();
    process.exit(1);
  }
  
  console.log('✅ API connection successful\n');

  // Initialize scheduler
  const scheduler = new Scheduler(userDataService);

  // Check if we should run immediately
  const runImmediately = process.argv.includes('--run-now');
  
  // Check for user IDs to fetch (from env or command line)
  const userIdsEnv = process.env.USER_IDS;
  const userIdsArg = process.argv.find(arg => arg.startsWith('--user-ids='));
  const userIdsParam = userIdsArg ? userIdsArg.split('=')[1] : userIdsEnv;
  
  if (userIdsParam) {
    const userIds = userIdsParam.split(',').map(id => parseInt(id.trim(), 10)).filter(id => !isNaN(id));
    if (userIds.length > 0) {
      console.log(`🔄 Fetching data for specific users: ${userIds.join(', ')}...\n`);
      try {
        await userDataService.fetchSpecificUsers(userIds);
        console.log('\n✅ Initial fetch completed');
      } catch (error: any) {
        console.error('\n❌ Initial fetch failed:', error.message);
        await closeDatabase();
        process.exit(1);
      }
    }
  } else if (runImmediately) {
    console.log('🔄 Running fetch immediately...\n');
    try {
      await scheduler.runNow();
      console.log('\n✅ Initial fetch completed');
    } catch (error: any) {
      console.error('\n❌ Initial fetch failed:', error.message);
      await closeDatabase();
      process.exit(1);
    }
  }

  // Start scheduler
  scheduler.start();

  console.log('\n✅ fetch-data-agent is running. Press Ctrl+C to stop.\n');
}

main().catch(async (error) => {
  console.error('❌ Fatal error:', error);
  await closeDatabase();
  process.exit(1);
});
