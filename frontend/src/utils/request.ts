/**
 * @file request.ts
 * @description Request utility for the frontend
 * @author Charm
 * @copyright 2025
 */
import { message } from 'antd';
import axios from 'axios';

// Create axios instance
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000, // Increase to 30 seconds
  headers: {
    'Content-Type': 'application/json',
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    Pragma: 'no-cache',
    Expires: '0',
  },
});

// Add request interceptor
request.interceptors.request.use(
  config => {
    // Add timestamp to prevent caching
    if (config.method === 'get') {
      config.params = {
        ...config.params,
        _t: new Date().getTime(),
      };
    }
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Add response interceptor
request.interceptors.response.use(
  response => {
    return response.data;
  },
  error => {
    // Handle timeout error
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      message.error('Request timeout, please try again later');
    } else if (error.response) {
      // Handle HTTP error status codes
      switch (error.response.status) {
        case 404:
          message.error('Requested resource not found');
          break;
        case 500:
          message.error('Internal server error');
          break;
        default:
          message.error(`Request failed: ${error.message}`);
      }
    } else {
      message.error(`Request error: ${error.message}`);
    }

    // Show detailed error in console
    console.error('Request error:', error);

    return Promise.reject(error);
  }
);

export default request;
