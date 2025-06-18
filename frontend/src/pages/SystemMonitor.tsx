/**
 * @file SystemMonitor.tsx
 * @description System monitor page component
 * @author Charm
 * @copyright 2025
 * */
import { Tabs } from 'antd';
import React, { useState } from 'react';
import SystemLogs from '../components/SystemLogs';

const SystemMonitor: React.FC = () => {
  const [activeTab, setActiveTab] = useState('engine-logs');

  // Define tabs using the items attribute
  const tabItems = [
    {
      label: 'Engine Logs',
      key: 'engine-logs',
      children: (
        <SystemLogs
          serviceName='engine'
          displayName='Engine Logs'
          isActive={activeTab === 'engine-logs'}
        />
      ),
    },
    {
      label: 'Backend Service Logs',
      key: 'backend-logs',
      children: (
        <SystemLogs
          serviceName='backend'
          displayName='Backend Service Logs'
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
