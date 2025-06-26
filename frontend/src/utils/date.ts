/**
 * @file date.ts
 * @description Date and time utility functions
 * @author Charm
 * @copyright 2025
 */

import dayjs from 'dayjs';
import 'dayjs/locale/en';
import relativeTime from 'dayjs/plugin/relativeTime';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

// Configure dayjs plugins
dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(relativeTime);
dayjs.locale('en');

// Date format constants
export const DATE_FORMATS = {
  FULL: 'YYYY-MM-DD HH:mm:ss',
  DATE_ONLY: 'YYYY-MM-DD',
  TIME_ONLY: 'HH:mm:ss',
  FILE_SAFE: 'YYYY-MM-DD-HH-mm-ss',
  ISO: 'YYYY-MM-DDTHH:mm:ss.SSSZ',
} as const;

/**
 * Format date to standard display format
 * @param date - Date string or Date object
 * @param format - Format string (default: FULL)
 * @returns Formatted date string or '-' if invalid
 */
export const formatDate = (
  date: string | Date | null | undefined,
  format: string = DATE_FORMATS.FULL
): string => {
  if (!date) return '-';

  try {
    const dayjsDate = dayjs(date);
    return dayjsDate.isValid() ? dayjsDate.format(format) : '-';
  } catch (error) {
    // Invalid date format
    return '-';
  }
};

/**
 * Get relative time from now (e.g., "2 hours ago")
 * @param date - Date string or Date object
 * @returns Relative time string or '-' if invalid
 */
export const getRelativeTime = (
  date: string | Date | null | undefined
): string => {
  if (!date) return '-';

  try {
    const dayjsDate = dayjs(date);
    return dayjsDate.isValid() ? dayjsDate.fromNow() : '-';
  } catch (error) {
    // Invalid date for relative time
    return '-';
  }
};

/**
 * Get timestamp value for sorting
 * @param date - Date string or Date object
 * @returns Timestamp number or 0 if invalid
 */
export const getTimestamp = (
  date: string | Date | null | undefined
): number => {
  if (!date) return 0;

  try {
    const dayjsDate = dayjs(date);
    return dayjsDate.isValid() ? dayjsDate.valueOf() : 0;
  } catch (error) {
    // Invalid date for timestamp
    return 0;
  }
};

/**
 * Create file-safe timestamp for downloads
 * @returns File-safe timestamp string
 */
export const createFileTimestamp = (): string => {
  return dayjs().format(DATE_FORMATS.FILE_SAFE);
};

/**
 * Check if date is today
 * @param date - Date string or Date object
 * @returns True if date is today
 */
export const isToday = (date: string | Date | null | undefined): boolean => {
  if (!date) return false;

  try {
    const dayjsDate = dayjs(date);
    return dayjsDate.isValid() ? dayjsDate.isSame(dayjs(), 'day') : false;
  } catch (error) {
    // Invalid date for today check
    return false;
  }
};

/**
 * Get duration between two dates
 * @param startDate - Start date
 * @param endDate - End date (default: now)
 * @returns Duration in milliseconds
 */
export const getDuration = (
  startDate: string | Date,
  endDate: string | Date = new Date()
): number => {
  try {
    const start = dayjs(startDate);
    const end = dayjs(endDate);

    if (!start.isValid() || !end.isValid()) return 0;

    return end.diff(start);
  } catch (error) {
    // Invalid dates for duration calculation
    return 0;
  }
};

/**
 * Format duration in human readable format
 * @param milliseconds - Duration in milliseconds
 * @returns Human readable duration string
 */
export const formatDuration = (milliseconds: number): string => {
  if (milliseconds <= 0) return '0s';

  const seconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days}d ${hours % 24}h`;
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
  return `${seconds}s`;
};

export default {
  formatDate,
  getRelativeTime,
  getTimestamp,
  createFileTimestamp,
  isToday,
  getDuration,
  formatDuration,
  DATE_FORMATS,
};
