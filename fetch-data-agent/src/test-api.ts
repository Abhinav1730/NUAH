// Test script to verify API data fetching from nuahchain-backend
import * as dotenv from 'dotenv';
import { ApiClient } from './services/apiClient';
import axios from 'axios';

// Load environment variables
dotenv.config();

async function testApi() {
  console.log('🧪 Testing nuahchain-backend API connection...\n');

  // Check environment variables
  const apiBaseUrl = process.env.NUAHCHAIN_API_BASE_URL || process.env.API_BASE_URL || 'http://localhost:8080';
  const apiToken = process.env.NUAHCHAIN_API_TOKEN || process.env.API_TOKEN;

  if (!apiToken) {
    console.error('❌ Error: NUAHCHAIN_API_TOKEN (or API_TOKEN) not found in environment');
    console.error('   Please set NUAHCHAIN_API_TOKEN in your .env file');
    console.error('   You can generate a token by running: go run ./cmd/seed_test_data in nuahchain-backend');
    process.exit(1);
  }

  console.log(`📡 API Base URL: ${apiBaseUrl}`);
  console.log(`🔑 API Token: ${apiToken.substring(0, 30)}...\n`);

  try {
    // Test 1: Health check
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('Test 1: Health Check');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    try {
      const healthResponse = await axios.get(`${apiBaseUrl}/health`, { timeout: 5000 });
      console.log('✅ Server is healthy!');
      console.log(`   Status: ${JSON.stringify(healthResponse.data)}\n`);
    } catch (error: any) {
      console.error('❌ Health check failed:', error.message);
      console.error('   Make sure nuahchain-backend server is running on', apiBaseUrl);
      process.exit(1);
    }

    // Test 2: Test API connection via ApiClient
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('Test 2: API Client Connection Test');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    const apiClient = new ApiClient();
    const connectionOk = await apiClient.testConnection();

    if (connectionOk) {
      console.log('✅ API connection successful\n');
    } else {
      console.log('❌ API connection failed\n');
      process.exit(1);
    }

    // Test 3: Fetch /api/auth/me
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('Test 3: Fetch Current User (/api/auth/me)');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    try {
      const meResponse = await axios.get(`${apiBaseUrl}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${apiToken}`,
          'Content-Type': 'application/json',
        },
        timeout: 10000,
      });
      
      console.log('✅ User profile fetched successfully!');
      console.log('📊 User Info:');
      console.log(`   User ID: ${meResponse.data.user?.id || 'N/A'}`);
      console.log(`   Email: ${meResponse.data.user?.email || 'N/A'}`);
      console.log(`   Username: ${meResponse.data.user?.username || 'N/A'}`);
      console.log(`   Wallet Address: ${meResponse.data.wallet?.address || 'N/A'}\n`);
    } catch (error: any) {
      console.error('❌ Error fetching user profile:', error.response?.data || error.message);
    }

    // Test 4: Fetch user profile via /api/users/me
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('Test 4: Fetch User Profile (/api/users/me)');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    try {
      const profileResponse = await axios.get(`${apiBaseUrl}/api/users/me`, {
        headers: {
          'Authorization': `Bearer ${apiToken}`,
          'Content-Type': 'application/json',
        },
        timeout: 10000,
      });
      
      console.log('✅ User profile fetched successfully!');
      console.log('📊 Profile Data:', JSON.stringify(profileResponse.data, null, 2).substring(0, 500));
      console.log('\n');
    } catch (error: any) {
      console.error('❌ Error fetching profile:', error.response?.data || error.message);
    }

    // Test 5: Fetch balances
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('Test 5: Fetch User Balances (/api/users/balances)');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    try {
      const balancesResponse = await axios.get(`${apiBaseUrl}/api/users/balances`, {
        headers: {
          'Authorization': `Bearer ${apiToken}`,
          'Content-Type': 'application/json',
        },
        timeout: 10000,
      });
      
      console.log('✅ Balances fetched successfully!');
      const balances = balancesResponse.data?.balances || [];
      console.log(`📦 Found ${balances.length} token balances`);
      
      if (balances.length > 0) {
        console.log('   Sample balances:');
        balances.slice(0, 5).forEach((b: any, i: number) => {
          console.log(`   ${i + 1}. ${b.denom}: ${b.amount}`);
        });
      }
      console.log('\n');
    } catch (error: any) {
      console.error('❌ Error fetching balances:', error.response?.data || error.message);
    }

    // Test 6: Fetch marketplace tokens (includes our test coins)
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('Test 6: Fetch Marketplace Tokens (/api/tokens/market)');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    try {
      const marketResponse = await axios.get(`${apiBaseUrl}/api/tokens/market`, {
        params: { limit: 10, offset: 0 },
        headers: {
          'Content-Type': 'application/json',
        },
        timeout: 10000,
      });
      
      console.log('✅ Marketplace tokens fetched successfully!');
      const tokens = marketResponse.data?.tokens || [];
      console.log(`🪙 Found ${tokens.length} tokens in marketplace`);
      
      if (tokens.length > 0) {
        console.log('   Tokens:');
        tokens.forEach((t: any, i: number) => {
          console.log(`   ${i + 1}. ${t.name} (${t.symbol}) - ${t.denom}`);
        });
      } else {
        console.log('   No tokens found in marketplace yet.');
      }
      console.log('\n');
    } catch (error: any) {
      console.error('❌ Error fetching marketplace:', error.response?.data || error.message);
    }

    // Test 7: Full user data fetch via ApiClient
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('Test 7: Full User Data Fetch via ApiClient');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    try {
      const userData = await apiClient.fetchUserData(1);
      
      if (userData) {
        console.log('✅ User data fetched successfully!\n');
        console.log('📊 User Data Summary:');
        console.log(`   User ID: ${userData.userId}`);
        console.log(`   Username: ${userData.profile.username || 'N/A'}`);
        console.log(`   Email: ${userData.profile.email || 'N/A'}`);
        console.log(`   Cosmos Address: ${userData.profile.cosmos_address || 'N/A'}`);
        console.log(`   Balances: ${userData.balances.length} tokens`);
        console.log(`   Transactions: ${userData.transactions.length} transactions`);
        console.log(`   Market Data: ${userData.marketData.length} tokens`);
        console.log(`   Portfolio Value (N-Dollar): ${userData.portfolio.totalValueNDollar}`);
        console.log(`   Fetched At: ${userData.fetchedAt}\n`);

        // Show sample balance
        if (userData.balances.length > 0) {
          console.log('📦 Sample Balance:');
          const sampleBalance = userData.balances[0];
          console.log(`   Token: ${sampleBalance.token_mint}`);
          console.log(`   Balance: ${sampleBalance.balance}\n`);
        }

        // Show sample transaction
        if (userData.transactions.length > 0) {
          console.log('💸 Sample Transaction:');
          const sampleTx = userData.transactions[0];
          console.log(`   Type: ${sampleTx.transaction_type}`);
          console.log(`   Token: ${sampleTx.token_mint_address}`);
          console.log(`   Amount: ${sampleTx.token_amount_lamports}\n`);
        }

        // Show market data
        if (userData.marketData.length > 0) {
          console.log('📈 Market Data Sample:');
          userData.marketData.slice(0, 3).forEach((m, i) => {
            console.log(`   ${i + 1}. ${m.name} (${m.symbol}): ${m.price_ndollar} N$`);
          });
          console.log('');
        }
      } else {
        console.log('⚠️ No user data returned\n');
      }
    } catch (error: any) {
      console.error('❌ Error fetching user data:', error.message);
      if (error.response?.data) {
        console.error('   Response:', JSON.stringify(error.response.data, null, 2));
      }
    }

    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('✅ All tests completed!');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  } catch (error: any) {
    console.error('\n❌ Test failed:', error.message);
    console.error('   Stack:', error.stack);
    process.exit(1);
  }
}

// Run tests
testApi().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

