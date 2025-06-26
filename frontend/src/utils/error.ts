/**
 * @file error.ts
 * @description Error handling utility functions
 * @author Charm
 * @copyright 2025
 */

import { message } from 'antd';

/**
 * Error types for better error handling
 */
export enum ErrorType {
  NETWORK = 'NETWORK',
  VALIDATION = 'VALIDATION',
  AUTHENTICATION = 'AUTHENTICATION',
  AUTHORIZATION = 'AUTHORIZATION',
  NOT_FOUND = 'NOT_FOUND',
  SERVER_ERROR = 'SERVER_ERROR',
  UNKNOWN = 'UNKNOWN',
}

/**
 * Structured error interface
 */
export interface AppError {
  type: ErrorType;
  message: string;
  details?: any;
  code?: string | number;
  timestamp: Date;
}

/**
 * Create a structured error
 */
export const createError = (
  type: ErrorType,
  message: string,
  details?: any,
  code?: string | number
): AppError => ({
  type,
  message,
  details,
  code,
  timestamp: new Date(),
});

/**
 * Get error type from HTTP status code
 */
export const getErrorTypeFromStatus = (status: number): ErrorType => {
  switch (status) {
    case 400:
      return ErrorType.VALIDATION;
    case 401:
      return ErrorType.AUTHENTICATION;
    case 403:
      return ErrorType.AUTHORIZATION;
    case 404:
      return ErrorType.NOT_FOUND;
    case 500:
    case 502:
    case 503:
    case 504:
      return ErrorType.SERVER_ERROR;
    default:
      if (status >= 400 && status < 500) {
        return ErrorType.VALIDATION;
      }
      if (status >= 500) {
        return ErrorType.SERVER_ERROR;
      }
      return ErrorType.UNKNOWN;
  }
};

/**
 * Parse error from API response
 */
export const parseApiError = (error: any): AppError => {
  if (error.response) {
    // HTTP error response
    const { status } = error.response;
    const { data } = error.response;
    const type = getErrorTypeFromStatus(status);

    return createError(
      type,
      data?.message || error.message || 'An error occurred',
      data,
      status
    );
  }

  if (error.request) {
    // Network error
    return createError(
      ErrorType.NETWORK,
      'Network error. Please check your connection.',
      error.request
    );
  }

  // Other error
  return createError(
    ErrorType.UNKNOWN,
    error.message || 'An unexpected error occurred',
    error
  );
};

/**
 * Default error messages for different error types
 */
export const DEFAULT_ERROR_MESSAGES = {
  [ErrorType.NETWORK]:
    'Network connection failed. Please check your internet connection.',
  [ErrorType.VALIDATION]: 'Please check your input and try again.',
  [ErrorType.AUTHENTICATION]: 'Authentication failed. Please log in again.',
  [ErrorType.AUTHORIZATION]:
    "You don't have permission to perform this action.",
  [ErrorType.NOT_FOUND]: 'The requested resource was not found.',
  [ErrorType.SERVER_ERROR]: 'Server error. Please try again later.',
  [ErrorType.UNKNOWN]: 'An unexpected error occurred. Please try again.',
} as const;

/**
 * Show error message using Ant Design message component
 */
export const showErrorMessage = (
  error: AppError | Error | string,
  duration: number = 5
): void => {
  let errorMessage: string;

  if (typeof error === 'string') {
    errorMessage = error;
  } else if (error instanceof Error) {
    errorMessage = error.message;
  } else {
    errorMessage = error.message || DEFAULT_ERROR_MESSAGES[error.type];
  }

  message.error(errorMessage, duration);
};

/**
 * Show success message
 */
export const showSuccessMessage = (
  text: string,
  duration: number = 3
): void => {
  message.success(text, duration);
};

/**
 * Show warning message
 */
export const showWarningMessage = (
  text: string,
  duration: number = 4
): void => {
  message.warning(text, duration);
};

/**
 * Show info message
 */
export const showInfoMessage = (text: string, duration: number = 3): void => {
  message.info(text, duration);
};

/**
 * Log error to console with structured format
 */
export const logError = (error: AppError, context?: string): void => {
  const logData = {
    context,
    type: error.type,
    message: error.message,
    code: error.code,
    timestamp: error.timestamp,
    details: error.details,
  };

  console.error('Application error logged:', logData);

  // Here you could also send to error reporting service
  // errorReportingService.captureError(logData);
};

/**
 * Handle async operation with error catching
 */
export const withErrorHandling = async <T>(
  operation: () => Promise<T>,
  errorContext?: string,
  showError: boolean = true
): Promise<T | null> => {
  try {
    return await operation();
  } catch (error) {
    const appError = parseApiError(error);
    logError(appError, errorContext);

    if (showError) {
      showErrorMessage(appError);
    }

    return null;
  }
};

/**
 * Retry operation with exponential backoff
 */
export const retryOperation = async <T>(
  operation: () => Promise<T>,
  maxRetries: number = 3,
  initialDelay: number = 1000
): Promise<T> => {
  let lastError: any;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      // eslint-disable-next-line no-await-in-loop
      return await operation();
    } catch (error) {
      lastError = error;

      if (attempt === maxRetries) {
        throw lastError;
      }

      // Exponential backoff: delay *= 2
      const delay = initialDelay * 2 ** attempt;
      // eslint-disable-next-line no-await-in-loop
      await new Promise<void>(resolve => {
        setTimeout(() => resolve(), delay);
      });
    }
  }

  throw lastError;
};

/**
 * Check if error is of specific type
 */
export const isErrorType = (error: any, type: ErrorType): boolean => {
  return error?.type === type;
};

/**
 * Check if error is network error
 */
export const isNetworkError = (error: any): boolean => {
  return isErrorType(error, ErrorType.NETWORK);
};

/**
 * Check if error is validation error
 */
export const isValidationError = (error: any): boolean => {
  return isErrorType(error, ErrorType.VALIDATION);
};

/**
 * Check if error is authentication error
 */
export const isAuthenticationError = (error: any): boolean => {
  return isErrorType(error, ErrorType.AUTHENTICATION);
};

export default {
  ErrorType,
  createError,
  parseApiError,
  showErrorMessage,
  showSuccessMessage,
  showWarningMessage,
  showInfoMessage,
  logError,
  withErrorHandling,
  retryOperation,
  isErrorType,
  isNetworkError,
  isValidationError,
  isAuthenticationError,
};
