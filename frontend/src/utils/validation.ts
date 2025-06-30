/**
 * @file validation.ts
 * @description Form validation utility functions
 * @author Charm
 * @copyright 2025
 */

import type { Rule } from 'antd/es/form';

/**
 * Validate JSON string
 * @param value - String value to validate
 * @returns Error message or undefined if valid
 */
export const validateJson = (value: string): string | undefined => {
  if (!value?.trim()) return undefined;

  try {
    JSON.parse(value);
    return undefined;
  } catch (error) {
    return 'Please enter valid JSON';
  }
};

/**
 * Validate URL format
 * @param value - URL string to validate
 * @returns Error message or undefined if valid
 */
export const validateUrl = (value: string): string | undefined => {
  if (!value?.trim()) return undefined;

  try {
    const url = new URL(value);
    // Use url to avoid unused variable warning
    return url ? undefined : 'Please enter a valid URL';
  } catch (error) {
    return 'Please enter a valid URL';
  }
};

/**
 * Validate API path format
 * @param value - API path to validate
 * @returns Error message or undefined if valid
 */
export const validateApiPath = (value: string): string | undefined => {
  if (!value?.trim()) return 'Please enter API path';

  if (!value.startsWith('/')) {
    return 'API path must start with /';
  }

  return undefined;
};

/**
 * Validate positive number
 * @param value - Number to validate
 * @param fieldName - Field name for error message
 * @returns Error message or undefined if valid
 */
export const validatePositiveNumber = (
  value: number | string | undefined,
  fieldName: string = 'Value'
): string | undefined => {
  const num = typeof value === 'string' ? parseFloat(value) : value;

  if (num === undefined || num === null || Number.isNaN(num)) {
    return `Please enter ${fieldName.toLowerCase()}`;
  }

  if (num <= 0) {
    return `${fieldName} must be greater than 0`;
  }

  return undefined;
};

/**
 * Validation rules for common form fields
 */
export const VALIDATION_RULES = {
  // Required field
  required: (message: string): Rule => ({
    required: true,
    message,
  }),

  // Required string with whitespace check
  requiredString: (message: string): Rule => ({
    required: true,
    whitespace: true,
    message,
  }),

  // JSON validation
  json: (required: boolean = false): Rule => ({
    required,
    validator: (_, value) => {
      const error = validateJson(value);
      return error ? Promise.reject(new Error(error)) : Promise.resolve();
    },
  }),

  // URL validation
  url: (required: boolean = false): Rule => ({
    required,
    validator: (_, value) => {
      if (!required && !value) return Promise.resolve();
      const error = validateUrl(value);
      return error ? Promise.reject(new Error(error)) : Promise.resolve();
    },
  }),

  // API path validation
  apiPath: (): Rule => ({
    required: true,
    validator: (_, value) => {
      const error = validateApiPath(value);
      return error ? Promise.reject(new Error(error)) : Promise.resolve();
    },
  }),

  // Positive number validation
  positiveNumber: (fieldName: string): Rule => ({
    required: true,
    validator: (_, value) => {
      const error = validatePositiveNumber(value, fieldName);
      return error ? Promise.reject(new Error(error)) : Promise.resolve();
    },
  }),

  // Email validation
  email: (required: boolean = false): Rule => ({
    required,
    type: 'email',
    message: 'Please enter a valid email address',
  }),

  // Min/Max length validation
  length: (min?: number, max?: number): Rule => ({
    min,
    max,
    message: `Length must be ${min ? `at least ${min}` : ''}${
      min && max ? ' and ' : ''
    }${max ? `at most ${max}` : ''} characters`,
  }),

  // Pattern validation
  pattern: (pattern: RegExp, message: string): Rule => ({
    pattern,
    message,
  }),

  // Custom validator
  custom: (
    validator: (rule: any, value: any) => Promise<void> | void,
    message?: string
  ): Rule => ({
    validator: async (rule, value) => {
      try {
        await validator(rule, value);
      } catch (error) {
        throw new Error(message || 'Validation failed');
      }
    },
  }),
} as const;

/**
 * Validate form values before submission
 * @param values - Form values object
 * @param schema - Validation schema
 * @returns Array of validation errors
 */
export const validateFormValues = (
  values: Record<string, any>,
  schema: Record<string, (value: any) => string | undefined>
): Array<{ field: string; message: string }> => {
  const errors: Array<{ field: string; message: string }> = [];

  Object.entries(schema).forEach(([field, validator]) => {
    const value = values[field];
    const error = validator(value);

    if (error) {
      errors.push({ field, message: error });
    }
  });

  return errors;
};

/**
 * Check if form is ready for testing (basic validation)
 * @param values - Form values
 * @returns True if form is valid for testing
 */
export const isFormValidForTest = (values: Record<string, any>): boolean => {
  const requiredFields = [
    'name',
    'target_host',
    'duration',
    'concurrent_users',
  ];

  return requiredFields.every(field => {
    const value = values[field];
    return value !== undefined && value !== null && value !== '';
  });
};

/**
 * Sanitize input value
 * @param value - Input value
 * @param maxLength - Maximum length (optional)
 * @returns Sanitized value
 */
export const sanitizeInput = (value: string, maxLength?: number): string => {
  if (!value) return '';

  let sanitized = value.trim();

  if (maxLength && sanitized.length > maxLength) {
    sanitized = sanitized.substring(0, maxLength);
  }

  return sanitized;
};

export default {
  validateJson,
  validateUrl,
  validateApiPath,
  validatePositiveNumber,
  validateFormValues,
  isFormValidForTest,
  sanitizeInput,
  VALIDATION_RULES,
};
