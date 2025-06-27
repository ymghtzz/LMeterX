/**
 * @file PageHeader.tsx
 * @description Reusable page header component
 * @author Charm
 * @copyright 2025
 */

import { Typography } from 'antd';
import React from 'react';

const { Title, Text } = Typography;

interface PageHeaderProps {
  /** Page title */
  title: React.ReactNode;
  /** Page description */
  description?: React.ReactNode;
  /** Icon for the title */
  icon?: React.ReactNode;
  /** Title level (1-5) */
  level?: 1 | 2 | 3 | 4 | 5;
  /** Extra content on the right */
  extra?: React.ReactNode;
  /** Custom className */
  className?: string;
}

/**
 * Reusable page header component
 */
export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  icon,
  level = 3,
  extra,
  className = 'page-header',
}) => {
  return (
    <div className={className}>
      <div className='flex justify-between align-center'>
        <div>
          <Title level={level}>
            {icon && <span className='mr-8'>{icon}</span>}
            {title}
          </Title>
          {description && <Text type='secondary'>{description}</Text>}
        </div>
        {extra && <div>{extra}</div>}
      </div>
    </div>
  );
};

export default PageHeader;
