/**
 * @file benchmark.ts
 * @description Benchmark job type definitions
 * @author Charm
 * @copyright 2025
 */
export interface BenchmarkJob {
  id: string;
  name: string;
  model?: string;
  target_host?: string;
  api_path?: string;
  request_payload?: string;
  field_mapping?: {
    prompt?: string;
    stream_prefix?: string;
    data_format?: string;
    content?: string;
    reasoning_content?: string;
    end_prefix?: string;
    stop_flag?: string;
    end_condition?: string;
  };
  concurrent_users?: number;
  dataset_id?: string;
  duration: number;
  concurrency?: number;
  headers?: Array<{
    key: string;
    value: string;
  }>;
  cookies?: Array<{
    key: string;
    value: string;
  }>;
  status:
    | 'pending'
    | 'running'
    | 'completed'
    | 'failed'
    | 'stopped'
    | 'created'
    | 'idle';
  created_at: string;
  updated_at: string;
  error_message?: string;
}

export interface Pagination {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiResponse<T> {
  data: T;
  status: number;
  statusText: string;
  pagination?: Pagination;
}
