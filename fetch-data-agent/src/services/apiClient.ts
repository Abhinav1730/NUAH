// API client for fetching data from n-dollar-server
import axios, { AxiosInstance } from 'axios';
import { UserData, BatchUserData } from '../types/userData.types';

export class ApiClient {
  private client: AxiosInstance;
  private baseUrl: string;
  private token: string;

  constructor() {
    this.baseUrl = process.env.API_BASE_URL || 'http://localhost:3000';
    this.token = process.env.API_TOKEN || '';

    if (!this.token) {
      throw new Error('API_TOKEN environment variable is required');
    }

    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: 30000, // 30 seconds
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`,
      },
    });

    // Add response interceptor for error handling
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

  /**
   * Fetch user data for a specific user
   */
  async fetchUserData(userId: number): Promise<UserData | null> {
    try {
      const response = await this.client.get<UserData>(`/api/v1/users/data/${userId}`);
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        console.log(`User ${userId} not found`);
        return null;
      }
      console.error(`Error fetching data for user ${userId}:`, error.message);
      throw error;
    }
  }

  /**
   * Fetch user data in batch
   */
  async fetchBatchUserData(userIds: number[]): Promise<BatchUserData | null> {
    try {
      const userIdsParam = userIds.join(',');
      const response = await this.client.get<BatchUserData>('/api/v1/users/data/batch', {
        params: { userIds: userIdsParam },
      });
      return response.data;
    } catch (error: any) {
      console.error('Error fetching batch user data:', error.message);
      throw error;
    }
  }

  /**
   * Test API connection
   */
  async testConnection(): Promise<boolean> {
    try {
      // Try to fetch a user (will fail if auth is wrong, but that's ok for testing)
      await this.client.get('/api/v1/users/data/1', { timeout: 5000 });
      return true;
    } catch (error: any) {
      // 404 is ok, means API is reachable
      if (error.response?.status === 404 || error.response?.status === 401) {
        return true;
      }
      console.error('API connection test failed:', error.message);
      return false;
    }
  }
}



