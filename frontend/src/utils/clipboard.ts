/**
 * @file clipboard.ts
 * @description Clipboard utility functions
 * @author Charm
 * @copyright 2025
 */

import { message } from 'antd';

/**
 * Copy text to clipboard with user feedback
 * @param text - Text to copy
 * @param successMessage - Success message (default: 'Copied')
 * @param errorMessage - Error message (default: 'Copy failed, please copy manually')
 * @returns Promise<boolean> - True if successful
 */
export const copyToClipboard = async (
  text: string,
  successMessage: string = 'Copied',
  errorMessage: string = 'Copy failed, please copy manually'
): Promise<boolean> => {
  if (!text) {
    message.warning('No content to copy');
    return false;
  }

  try {
    // Try modern clipboard API first
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      message.success(successMessage);
      return true;
    }

    // Fallback for older browsers
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.opacity = '0';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';

    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    const result = document.execCommand('copy');
    document.body.removeChild(textArea);

    if (result) {
      message.success(successMessage);
      return true;
    }
    throw new Error('execCommand failed');
  } catch (error) {
    // Failed to copy text
    message.error(errorMessage);
    return false;
  }
};

/**
 * Copy text to clipboard without user feedback (silent)
 * @param text - Text to copy
 * @returns Promise<boolean> - True if successful
 */
export const copyToClipboardSilent = async (text: string): Promise<boolean> => {
  if (!text) return false;

  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }

    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.opacity = '0';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';

    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    const result = document.execCommand('copy');
    document.body.removeChild(textArea);

    return result;
  } catch (error) {
    // Failed to copy text silently
    return false;
  }
};

/**
 * Check if clipboard API is available
 * @returns boolean - True if clipboard API is available
 */
export const isClipboardSupported = (): boolean => {
  return !!(navigator.clipboard && window.isSecureContext);
};

/**
 * Read text from clipboard (if supported)
 * @returns Promise<string | null> - Clipboard text or null if failed
 */
export const readFromClipboard = async (): Promise<string | null> => {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      const text = await navigator.clipboard.readText();
      return text;
    }

    // Fallback is not possible for reading from clipboard
    // Clipboard read not supported in this environment
    return null;
  } catch (error) {
    // Failed to read from clipboard
    return null;
  }
};

export default {
  copyToClipboard,
  copyToClipboardSilent,
  isClipboardSupported,
  readFromClipboard,
};
