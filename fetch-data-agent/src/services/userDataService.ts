// Main service for fetching and storing user data
import { ApiClient } from './apiClient';
import { DataService } from './dataService';
import { UserData } from '../types/userData.types';
import { Database } from '../database/sqlite';

export class UserDataService {
  private apiClient: ApiClient;
  private dataService: DataService;
  private batchSize: number;

  constructor(db: Database) {
    this.apiClient = new ApiClient();
    this.dataService = new DataService(db);
    this.batchSize = parseInt(process.env.BATCH_SIZE || '10', 10);
  }

  /**
   * Fetch and store data for a single user
   */
  async fetchAndStoreUser(userId: number): Promise<boolean> {
    try {
      console.log(`📥 Fetching data for user ${userId}...`);
      const userData = await this.apiClient.fetchUserData(userId);
      
      if (!userData) {
        console.log(`⚠️ No data found for user ${userId}`);
        return false;
      }

      await this.dataService.storeUserData(userData);
      console.log(`✅ Successfully stored data for user ${userId}`);
      return true;
    } catch (error: any) {
      console.error(`❌ Error fetching/storing data for user ${userId}:`, error.message);
      return false;
    }
  }

  /**
   * Fetch and store data for multiple users in batch
   */
  async fetchAndStoreBatch(userIds: number[]): Promise<number> {
    if (userIds.length === 0) {
      return 0;
    }

    // Split into batches to avoid overwhelming the API
    const batches: number[][] = [];
    for (let i = 0; i < userIds.length; i += this.batchSize) {
      batches.push(userIds.slice(i, i + this.batchSize));
    }

    let successCount = 0;

    for (const batch of batches) {
      try {
        console.log(`📥 Fetching batch of ${batch.length} users...`);
        const batchData = await this.apiClient.fetchBatchUserData(batch);
        
        if (batchData && batchData.users) {
          // Store each user from batch
          for (const userData of batchData.users) {
            try {
              // For batch data, we need to fetch full data or construct it
              // For now, let's fetch full data for each user in batch
              await this.fetchAndStoreUser(userData.userId);
              successCount++;
            } catch (error: any) {
              console.error(`Error storing user ${userData.userId} from batch:`, error.message);
            }
          }
        }
      } catch (error: any) {
        console.error(`Error fetching batch:`, error.message);
        // Fallback: fetch users individually
        for (const userId of batch) {
          const success = await this.fetchAndStoreUser(userId);
          if (success) successCount++;
        }
      }
    }

    return successCount;
  }

  /**
   * Fetch all users (initial fetch or full refresh)
   * This would need a way to get all user IDs from the API
   * For now, we'll fetch users that are already in the database
   */
  async fetchAllUsers(): Promise<void> {
    console.log('🔄 Starting full user data fetch...');
    
    // Get users from database
    const userIds = await this.dataService.getUsersToFetch();
    
    if (userIds.length === 0) {
      console.log('⚠️ No users found in database. You may need to manually add user IDs.');
      return;
    }

    console.log(`📊 Found ${userIds.length} users to fetch`);
    
    // Fetch in batches
    const successCount = await this.fetchAndStoreBatch(userIds);
    
    console.log(`✅ Fetch completed: ${successCount}/${userIds.length} users updated`);
  }

  /**
   * Fetch users with active bots (priority users)
   */
  async fetchActiveTraders(): Promise<void> {
    console.log('🔄 Fetching data for active traders...');
    
    const userIds = await this.dataService.getUsersWithActiveBots();
    
    if (userIds.length === 0) {
      console.log('ℹ️ No users with active bots found');
      return;
    }

    console.log(`📊 Found ${userIds.length} active traders`);
    const successCount = await this.fetchAndStoreBatch(userIds);
    console.log(`✅ Active traders fetch completed: ${successCount}/${userIds.length} users updated`);
  }

  /**
   * Fetch specific users by IDs (for initial setup)
   */
  async fetchSpecificUsers(userIds: number[]): Promise<void> {
    console.log(`🔄 Fetching data for ${userIds.length} specific users...`);
    const successCount = await this.fetchAndStoreBatch(userIds);
    console.log(`✅ Fetch completed: ${successCount}/${userIds.length} users updated`);
  }

  /**
   * Test API connection
   */
  async testConnection(): Promise<boolean> {
    return await this.apiClient.testConnection();
  }
}
