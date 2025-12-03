// CRON scheduler for fetching user data
import cron from 'node-cron';
import { UserDataService } from './services/userDataService';

export class Scheduler {
  private userDataService: UserDataService;
  private cronJob: cron.ScheduledTask | null = null;
  private intervalMinutes: number;

  constructor(userDataService: UserDataService) {
    this.userDataService = userDataService;
    this.intervalMinutes = parseInt(process.env.FETCH_INTERVAL_MINUTES || '20', 10);
  }

  /**
   * Start the scheduler
   */
  start(): void {
    console.log(`🚀 Starting scheduler (interval: ${this.intervalMinutes} minutes)...`);

    // Convert minutes to cron expression
    // Every X minutes: `*/X * * * *`
    const cronExpression = `*/${this.intervalMinutes} * * * *`;

    this.cronJob = cron.schedule(cronExpression, async () => {
      console.log(`\n⏰ [${new Date().toISOString()}] Scheduled fetch triggered`);
      
      try {
        // First, fetch active traders (priority)
        await this.userDataService.fetchActiveTraders();
        
        // Then, fetch all other users
        await this.userDataService.fetchAllUsers();
        
        console.log(`✅ [${new Date().toISOString()}] Scheduled fetch completed\n`);
      } catch (error: any) {
        console.error(`❌ [${new Date().toISOString()}] Scheduled fetch failed:`, error.message);
      }
    }, {
      scheduled: true,
      timezone: 'UTC',
    });

    console.log(`✅ Scheduler started. Will run every ${this.intervalMinutes} minutes.`);
  }

  /**
   * Stop the scheduler
   */
  stop(): void {
    if (this.cronJob) {
      this.cronJob.stop();
      this.cronJob = null;
      console.log('🛑 Scheduler stopped');
    }
  }

  /**
   * Run fetch immediately (for testing)
   */
  async runNow(): Promise<void> {
    console.log('🔄 Running fetch immediately...');
    try {
      await this.userDataService.fetchActiveTraders();
      await this.userDataService.fetchAllUsers();
      console.log('✅ Immediate fetch completed');
    } catch (error: any) {
      console.error('❌ Immediate fetch failed:', error.message);
      throw error;
    }
  }
}
