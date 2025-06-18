/**
 * @file index.ts
 * @description Type definitions for the frontend
 * @author Charm
 * @copyright 2025
 */

// Dataset Types
export interface Dataset {
  _id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  file_name: string;
  object_name: string;
  prompt_count: number;
}

// Benchmark Job Types
export enum JobStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  STOPPED = 'stopped',
}

export interface BenchmarkJob {
  _id: string;
  name: string;
  description?: string;
  dataset_id: string;

  // LLM service settings
  llm_service_url: string;
  api_key?: string;
  headers?: Record<string, string>;
  stream: boolean;
  model?: string;

  // Locust settings
  users: number;
  spawn_rate: number;
  run_time?: string;
  headless: boolean;

  // Job status
  status: JobStatus;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
  result_id?: string;
  error_message?: string;

  // Additional parameters
  additional_params?: Record<string, any>;
}

// Results Types
export interface RequestStats {
  total_requests: number;
  success_requests: number;
  failure_requests: number;
  avg_response_time_ms: number;
  min_response_time_ms: number;
  max_response_time_ms: number;
  median_response_time_ms: number;
  p95_response_time_ms: number;
  p99_response_time_ms: number;
  rps: number; // Requests per second
}

export interface TokenStats {
  total_tokens: number;
  completion_tokens: number;
  prompt_tokens: number;
  tokens_per_second: number;
}

export interface BenchmarkResults {
  // General info
  start_time: string;
  end_time: string;
  duration_seconds: number;

  // Request statistics by type
  first_token?: RequestStats;
  generation_time?: RequestStats;
  completed?: RequestStats;

  // Token statistics
  token_stats?: TokenStats;

  // Raw metrics data
  metrics?: Record<string, any>;

  // Exceptions & errors
  errors?: Array<Record<string, any>>;
}

export interface BenchmarkResult {
  _id: string;
  benchmark_job_id: string;
  created_at: string;
  results: BenchmarkResults;
  job_config: BenchmarkJob;
}
