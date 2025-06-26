/**
 * @file IconTooltip.tsx
 * @description Reusable icon tooltip component
 * @author Charm
 * @copyright 2025
 */

import { InfoCircleOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import React from 'react';

interface IconTooltipProps {
  /** Tooltip content */
  title: React.ReactNode;
  /** Icon type */
  icon?: React.ReactNode;
  /** Icon placement */
  placement?:
    | 'top'
    | 'bottom'
    | 'left'
    | 'right'
    | 'topLeft'
    | 'topRight'
    | 'bottomLeft'
    | 'bottomRight';
  /** Custom className */
  className?: string;
  /** Custom color */
  color?: string;
}

/**
 * Reusable icon tooltip component
 */
export const IconTooltip: React.FC<IconTooltipProps> = ({
  title,
  icon = <InfoCircleOutlined />,
  placement = 'top',
  className = 'icon-tooltip',
  color,
}) => {
  const iconElement = React.cloneElement(icon as React.ReactElement, {
    className,
    style: {
      ...(icon as React.ReactElement)?.props?.style,
      color: color || (icon as React.ReactElement)?.props?.style?.color,
    },
  });

  return (
    <Tooltip title={title} placement={placement}>
      {iconElement}
    </Tooltip>
  );
};

export default IconTooltip;
