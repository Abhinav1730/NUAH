// Type declarations for sqlite package
declare module 'sqlite' {
  export interface Database {
    run(sql: string, params?: any[]): Promise<{ lastID?: number; changes: number }>;
    get<T = any>(sql: string, params?: any[]): Promise<T | undefined>;
    all<T = any>(sql: string, params?: any[]): Promise<T[]>;
    exec(sql: string): Promise<void>;
    close(): Promise<void>;
  }

  export interface OpenConfig {
    filename: string;
    driver?: any;
    verbose?: boolean;
  }

  export function open(config: OpenConfig | string): Promise<Database>;
}
