// Test script to verify API data fetching
import * as dotenv from 'dotenv';
import { ApiClient } from './services/apiClient';
import axios from 'axios';

// Load environment variables
dotenv.config();

async function testApi() {
  console.log('🧪 Testing n-dollar-server API connection...\n');

  // Check environment variables
  const apiBaseUrl = process.env.API_BASE_URL || 'http://localhost:3000';
  const apiToken = process.env.API_TOKEN;

  if (!apiToken) {
    console.error('❌ Error: API_TOKEN not found in .env file');
    console.error('   Please set API_TOKEN in your .env file');
    process.exit(1);
  }

  console.log(`📡 API Base URL: ${apiBaseUrl}`);
  console.log(`🔑 API Token: ${apiToken.substring(0, 20)}...\n`);

  try {
    // Test 1: Test API connection
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('Test 1: API Connection Test');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    
    const apiClient = new ApiClient();
    const connectionOk = await apiClient.testConnection();
    
    if (connectionOk) {
      console.log('✅ API connection successful\n');
    } else {
      console.log('❌ API connection failed\n');
      process.exit(1);
    }

    // Test 2: Try to fetch user data for user ID 1
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('Test 2: Fetch User Data (User ID: 1)');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    
    try {
      const userData = await apiClient.fetchUserData(1);
      
      if (userData) {
        console.log('✅ User data fetched successfully!\n');
        console.log('📊 User Data Summary:');
        console.log(`   User ID: ${userData.userId}`);
        console.log(`   Username: ${userData.profile.username || 'N/A'}`);
        console.log(`   Email: ${userData.profile.email || 'N/A'}`);
        console.log(`   Public Key: ${userData.profile.public_key.substring(0, 20)}...`);
        console.log(`   Balances: ${userData.balances.length} tokens`);
        console.log(`   Transactions: ${userData.transactions.length} transactions`);
        console.log(`   Bots: ${userData.bots.length} bots`);
        console.log(`   Portfolio Value (N-Dollar): ${userData.portfolio.totalValueNDollar}`);
        console.log(`   Portfolio Value (SOL): ${userData.portfolio.totalValueSOL}`);
        console.log(`   Market Data: ${userData.marketData.length} tokens\n`);
        
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
          console.log(`   Amount: ${sampleTx.token_amount_lamports}`);
          console.log(`   Signature: ${sampleTx.solana_signature.substring(0, 20)}...\n`);
        }
      } else {
        console.log('⚠️ User ID 1 not found. Trying other user IDs...\n');
      }
    } catch (error: any) {
      if (error.response?.status === 404) {
        console.log('⚠️ User ID 1 not found\n');
      } else {
        console.error('❌ Error fetching user data:', error.message);
        if (error.response?.data) {
          console.error('   Response:', JSON.stringify(error.response.data, null, 2));
        }
      }
    }

    // Test 3: Test batch endpoint
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('Test 3: Batch User Data Fetch (User IDs: 1, 2, 3)');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    
    try {
      const batchData = await apiClient.fetchBatchUserData([1, 2, 3]);
      
      if (batchData) {
        console.log(`✅ Batch data fetched successfully!`);
        console.log(`   Total users: ${batchData.total}`);
        console.log(`   Fetched at: ${batchData.fetchedAt}\n`);
        
        if (batchData.users.length > 0) {
          console.log('📋 Users in batch:');
          batchData.users.forEach((user, index) => {
            console.log(`   ${index + 1}. User ID: ${user.userId}, Username: ${user.profile.username || 'N/A'}, Balances: ${user.balances.length}`);
          });
        }
      }
    } catch (error: any) {
      console.error('❌ Error fetching batch data:', error.message);
      if (error.response?.data) {
        console.error('   Response:', JSON.stringify(error.response.data, null, 2));
      }
    }

    // Test 4: Direct API call test
    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('Test 4: Direct API Call Test');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    
    try {
      const response = await axios.get(`${apiBaseUrl}/api/v1/users/data/1`, {
        headers: {
          'Authorization': `Bearer ${apiToken}`,
          'Content-Type': 'application/json',
        },
        timeout: 10000,
      });
      
      console.log('✅ Direct API call successful!');
      console.log(`   Status: ${response.status}`);
      console.log(`   Data keys: ${Object.keys(response.data).join(', ')}\n`);
    } catch (error: any) {
      if (error.response) {
        console.error(`❌ API Error: ${error.response.status} ${error.response.statusText}`);
        if (error.response.data) {
          console.error('   Message:', error.response.data.message || JSON.stringify(error.response.data));
        }
      } else if (error.request) {
        console.error('❌ No response from server. Is n-dollar-server running?');
      } else {
        console.error('❌ Error:', error.message);
      }
    }

    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
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

