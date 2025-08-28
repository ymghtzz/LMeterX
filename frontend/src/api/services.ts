/**
 * @file services.ts
 * @description API services for the frontend
 * @author Charm
 * @copyright 2025
 * */

import { BenchmarkJob, BenchmarkResult, Dataset } from '../types';
import api, { uploadFiles } from './apiClient';

// Dataset API methods
export const datasetApi = {
  // Get all datasets
  getAllDatasets: () => api.get<Dataset[]>('/datasets'),

  // Get a specific dataset by ID
  getDataset: (id: string) => api.get<Dataset>(`/datasets/${id}`),

  // Create a new dataset
  createDataset: (formData: FormData) =>
    api.uploadFile<Dataset>('/datasets', formData),

  // Update a dataset
  updateDataset: (id: string, data: Partial<Dataset>) =>
    api.put<Dataset>(`/datasets/${id}`, data),

  // Delete a dataset
  deleteDataset: (id: string) => api.delete<void>(`/datasets/${id}`),
};

// Benchmark Job API methods
export const benchmarkJobApi = {
  // Get all benchmark jobs
  getAllJobs: (status?: string, limit?: number, skip?: number) => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (limit) params.append('limit', limit.toString());
    if (skip) params.append('skip', skip.toString());

    return api.get<BenchmarkJob[]>(`/tasks?${params.toString()}`);
  },

  // Get a specific benchmark job by ID
  getJob: (id: string) => api.get<BenchmarkJob>(`/tasks/${id}`),

  // Get only the status of a specific benchmark job by ID (lightweight)
  getJobStatus: (id: string) =>
    api.get<{
      id: string;
      name: string;
      status: string;
      error_message?: string;
      updated_at?: string;
    }>(`/tasks/${id}/status`),

  // Create a new benchmark job
  createJob: (
    data: Omit<
      BenchmarkJob,
      'id' | 'created_at' | 'updated_at' | 'status' | 'result_id'
    >
  ) => api.post<BenchmarkJob>('/tasks', data),

  // Update a benchmark job
  updateJob: (id: string, data: Partial<BenchmarkJob>) =>
    api.put<BenchmarkJob>(`/tasks/${id}`, data),

  // Delete a benchmark job
  deleteJob: (id: string) => api.delete<void>(`/tasks/${id}`),

  // Stop a running benchmark job
  stopJob: (id: string) => api.post<BenchmarkJob>(`/tasks/stop/${id}`),

  // Test API endpoint
  testApiEndpoint: (data: any) => api.post<any>('/tasks/test', data),
};

// Results API methods
export const resultApi = {
  // Get all results
  getAllResults: (benchmarkJobId?: string, limit?: number, skip?: number) => {
    const params = new URLSearchParams();
    if (benchmarkJobId) params.append('benchmark_job_id', benchmarkJobId);
    if (limit) params.append('limit', limit.toString());
    if (skip) params.append('skip', skip.toString());

    return api.get<BenchmarkResult[]>(`/results?${params.toString()}`);
  },

  // Get a specific result by ID
  getResult: (id: string) => api.get<BenchmarkResult>(`/results/${id}`),

  // Get the result for a specific benchmark job
  getJobResult: (jobId: string) => api.get<any>(`/tasks/${jobId}/results`),
};

// Performance Comparison API methods
export const comparisonApi = {
  // Get available model tasks for comparison
  getAvailableModelTasks: () =>
    api.get<{
      data: Array<{
        model_name: string;
        concurrent_users: number;
        task_id: string;
        task_name: string;
        created_at: string;
      }>;
      status: string;
      error?: string;
    }>('/tasks/comparison/available'),

  // Compare performance metrics for selected tasks
  comparePerformance: (selectedTasks: string[]) =>
    api.post<{
      data: Array<{
        task_id: string;
        model_name: string;
        concurrent_users: number;
        task_name: string;
        ttft: number;
        total_tps: number;
        completion_tps: number;
        avg_total_token_per_req: number;
        avg_completion_token_per_req: number;
        avg_response_time: number;
        rps: number;
      }>;
      status: string;
      error?: string;
    }>('/tasks/comparison', { selected_tasks: selectedTasks }),
};

// Get log content (supports incremental fetching)
export const logApi = {
  getServiceLogContent: (
    serviceName: string,
    offset: number = 0,
    tail: number = 0
  ) => api.get<any>(`/logs/${serviceName}`, { params: { offset, tail } }),

  getTaskLogContent: (taskId: string, offset: number = 0, tail: number = 0) =>
    api.get<any>(`/logs/task/${taskId}`, { params: { offset, tail } }),
};

// Analysis API methods
export const analysisApi = {
  // Perform AI analysis on task results (single or multiple tasks)
  analyzeTasks: (taskIds: string[], language?: string) =>
    api.post<{
      task_ids: string[];
      analysis_report: string;
      status: string;
      error_message?: string;
      created_at: string;
    }>(
      '/analyze',
      {
        task_ids: taskIds,
        language: language || 'en',
      },
      {
        timeout: 300000, // 5 minutes timeout for AI analysis
      }
    ),

  // Get analysis result for a task
  getAnalysis: (taskId: string) =>
    api.get<{
      data?: {
        task_ids: string[];
        analysis_report: string;
        status: string;
        error_message?: string;
        created_at: string;
      };
      status: string;
      error?: string;
    }>(`/analyze/${taskId}`, {
      timeout: 300000, // 5 minutes timeout for getting analysis result
    }),
};

// System Configuration API methods
export const systemApi = {
  // Get all system configurations
  getSystemConfigs: () => api.get<any>('/system'),

  // Create a new system configuration
  createSystemConfig: (config: {
    config_key: string;
    config_value: string;
    description?: string;
  }) => api.post<any>('/system', config),

  // Update a system configuration
  updateSystemConfig: (
    configKey: string,
    config: {
      config_key: string;
      config_value: string;
      description?: string;
    }
  ) => api.put<any>(`/system/${configKey}`, config),

  // Batch create or update system configurations
  batchUpsertSystemConfigs: (
    configs: Array<{
      config_key: string;
      config_value: string;
      description?: string;
    }>
  ) => api.post<any>('/system/batch', { configs }),

  // Delete a system configuration
  deleteSystemConfig: (configKey: string) =>
    api.delete<any>(`/system/${configKey}`),

  // Get AI service configuration
  getAIServiceConfig: () => api.get<any>('/system/ai-service'),
} as const;

// Define the upload service
export const uploadCertificateFiles = async (
  certFile: File | null,
  keyFile: File | null,
  taskId: string,
  certType: string = 'combined'
) => {
  if (!taskId) {
    taskId = `temp-${Date.now()}`;
  }

  // Process upload based on certificate type
  if (certType === 'combined' && certFile) {
    // Combined certificate mode
    const formData = new FormData();
    formData.append('files', certFile);
    return uploadFiles(formData, 'cert', taskId, certType);
  }
  if (certType === 'separate') {
    // Separate upload mode
    let certConfig = {};

    // If there is a certificate file, upload it first
    if (certFile) {
      const certFormData = new FormData();
      certFormData.append('files', certFile);
      const certResult = await uploadFiles(
        certFormData,
        'cert',
        taskId,
        'cert_file'
      );
      certConfig = certResult.cert_config;
    }

    // If there is a key file, upload it
    if (keyFile) {
      const keyFormData = new FormData();
      keyFormData.append('files', keyFile);
      const keyResult = await uploadFiles(
        keyFormData,
        'cert',
        taskId,
        'key_file'
      );
      certConfig = keyResult.cert_config; // Use the final configuration
    }

    return { cert_config: certConfig };
  }

  throw new Error('Invalid certificate type or file');
};

// Upload dataset file
export const uploadDatasetFile = async (datasetFile: File, taskId: string) => {
  if (!taskId) {
    taskId = `temp-${Date.now()}`;
  }

  const formData = new FormData();
  formData.append('files', datasetFile);
  return uploadFiles(formData, 'dataset', taskId);
};
