/**
 * @file SystemMonitor.tsx
 * @description System monitor page component
 * @author Charm
 * @copyright 2025
 * */
import { Tabs } from 'antd';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import SystemLogs from '../components/SystemLogs';

const SystemMonitor: React.FC = () => {
  const [activeTab, setActiveTab] = useState('engine-logs');
  const { t } = useTranslation();

  // Define tabs using the items attribute
  const tabItems = [
    {
      label: t('components.systemLogs.engineLogs', {
        defaultValue: 'Engine Logs',
      }),
      key: 'engine-logs',
      children: (
        <SystemLogs
          serviceName='engine'
          displayName={t('components.systemLogs.engineLogs', {
            defaultValue: 'Engine Logs',
          })}
          isActive={activeTab === 'engine-logs'}
        />
      ),
    },
    {
      label: t('components.systemLogs.backendLogs', {
        defaultValue: 'Backend Service Logs',
      }),
      key: 'backend-logs',
      children: (
        <SystemLogs
          serviceName='backend'
          displayName={t('components.systemLogs.backendLogs', {
            defaultValue: 'Backend Service Logs',
          })}
          isActive={activeTab === 'backend-logs'}
        />
      ),
    },

    // More monitoring tabs can be added here, such as CPU usage, memory usage, etc.
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        type='card'
        items={tabItems}
        style={{ marginTop: '5px' }}
      />
    </div>
  );
};

export default SystemMonitor;
