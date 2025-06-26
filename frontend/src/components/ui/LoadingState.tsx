/**
 * @file LoadingState.tsx
 * @description Reusable loading state components
 * @author Charm
 * @copyright 2025
 */

import { Spin, Typography } from 'antd';
import React from 'react';

const { Text } = Typography;

interface LoadingSpinnerProps {
  /** Loading text */
  text?: string;
  /** Spinner size */
  size?: 'small' | 'default' | 'large';
  /** Show text below spinner */
  showText?: boolean;
  /** Custom className */
  className?: string;
}

/**
 * Simple loading spinner component
 */
export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  text = 'Loading...',
  size = 'default',
  showText = true,
  className,
}) => {
  return (
    <div className={`text-center p-24 ${className || ''}`}>
      <Spin size={size} />
      {showText && <Text className='loading-text'>{text}</Text>}
    </div>
  );
};

interface LoadingContainerProps {
  /** Loading state */
  loading: boolean;
  /** Loading text */
  loadingText?: string;
  /** Children to render when not loading */
  children: React.ReactNode;
  /** Spinner size */
  size?: 'small' | 'default' | 'large';
  /** Custom className for loading state */
  className?: string;
}

/**
 * Container that shows loading state or children
 */
export const LoadingContainer: React.FC<LoadingContainerProps> = ({
  loading,
  loadingText = 'Loading...',
  children,
  size = 'default',
  className,
}) => {
  if (loading) {
    return (
      <LoadingSpinner text={loadingText} size={size} className={className} />
    );
  }

  return children as React.ReactElement;
};

interface InlineLoadingProps {
  /** Loading state */
  loading: boolean;
  /** Loading text */
  text?: string;
  /** Spinner size */
  size?: 'small' | 'default' | 'large';
  /** Custom className */
  className?: string;
}

/**
 * Inline loading indicator
 */
export const InlineLoading: React.FC<InlineLoadingProps> = ({
  loading,
  text = 'Loading',
  size = 'small',
  className,
}) => {
  if (!loading) return null;

  return (
    <span className={`flex align-center ${className || ''}`}>
      <Spin size={size} />
      {text && <Text className='ml-8'>{text}</Text>}
    </span>
  );
};

export default {
  LoadingSpinner,
  LoadingContainer,
  InlineLoading,
};
