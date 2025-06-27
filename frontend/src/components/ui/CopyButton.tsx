/**
 * @file CopyButton.tsx
 * @description Reusable copy button component
 * @author Charm
 * @copyright 2025
 */

import { CopyOutlined } from '@ant-design/icons';
import { Button, Tooltip } from 'antd';
import React from 'react';

import { copyToClipboard } from '@/utils/clipboard';

interface CopyButtonProps {
  /** Text to copy */
  text: string;
  /** Button size */
  size?: 'small' | 'middle' | 'large';
  /** Button type */
  type?: 'text' | 'link' | 'default' | 'primary' | 'dashed';
  /** Tooltip title */
  tooltip?: string;
  /** Success message */
  successMessage?: string;
  /** Error message */
  errorMessage?: string;
  /** Custom icon */
  icon?: React.ReactNode;
  /** Disabled state */
  disabled?: boolean;
  /** Click handler (for additional logic) */
  onCopy?: (text: string, success: boolean) => void;
  /** Custom className */
  className?: string;
}

/**
 * Reusable copy button component
 */
export const CopyButton: React.FC<CopyButtonProps> = ({
  text,
  size = 'small',
  type = 'text',
  tooltip = 'Copy',
  successMessage,
  errorMessage,
  icon = <CopyOutlined />,
  disabled = false,
  onCopy,
  className,
}) => {
  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();

    if (!text || disabled) return;

    const success = await copyToClipboard(text, successMessage, errorMessage);
    onCopy?.(text, success);
  };

  const button = (
    <Button
      type={type}
      size={size}
      icon={icon}
      onClick={handleCopy}
      disabled={disabled || !text}
      className={`copy-button ${className || ''}`}
      style={{
        padding: '0 4px',
        minWidth: 'auto',
        height: 'auto',
        lineHeight: 1,
      }}
    />
  );

  return tooltip ? <Tooltip title={tooltip}>{button}</Tooltip> : button;
};

export default CopyButton;
