/**
 * @file StatusTag.tsx
 * @description Reusable status tag component
 * @author Charm
 * @copyright 2025
 */

import { Tag } from 'antd';
import React from 'react';

import { TASK_STATUS_MAP } from '@/utils/constants';

interface StatusTagProps {
  /** Status value */
  status: string;
  /** Custom status mapping (overrides default) */
  statusMap?: Record<string, { color: string; text: string }>;
  /** Show unknown status as default tag */
  showUnknown?: boolean;
  /** Custom className */
  className?: string;
}

/**
 * Reusable status tag component with predefined styling
 */
export const StatusTag: React.FC<StatusTagProps> = ({
  status,
  statusMap = TASK_STATUS_MAP,
  showUnknown = true,
  className,
}) => {
  const statusKey = status?.toLowerCase();
  const statusInfo = statusMap[statusKey as keyof typeof statusMap];

  if (!statusInfo && !showUnknown) {
    return null;
  }

  const finalStatusInfo = statusInfo || {
    color: 'default',
    text: status || 'Unknown',
  };

  return (
    <Tag color={finalStatusInfo.color as any} className={className}>
      {finalStatusInfo.text}
    </Tag>
  );
};

export default StatusTag;
