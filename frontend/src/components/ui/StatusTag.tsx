/**
 * @file StatusTag.tsx
 * @description Reusable status tag component
 * @author Charm
 * @copyright 2025
 */

import { Tag } from 'antd';
import React from 'react';
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation();
  const statusKey = status?.toLowerCase();
  const statusInfo = statusMap[statusKey as keyof typeof statusMap];

  if (!statusInfo && !showUnknown) {
    return null;
  }

  // Use translation for status text
  const translatedText = t(`status.${statusKey}`, status || 'Unknown');

  const finalStatusInfo = statusInfo || {
    color: 'default',
    text: translatedText,
  };

  return (
    <Tag color={finalStatusInfo.color as any} className={className}>
      {translatedText}
    </Tag>
  );
};

export default StatusTag;
