/**
 * @file Sidebar.tsx
 * @description Sidebar component
 * @author Charm
 * @copyright 2025
 * */

import {
  BarChartOutlined,
  ExperimentOutlined,
  MonitorOutlined,
} from '@ant-design/icons';
import { ConfigProvider, Layout, Menu } from 'antd';
import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const { Sider } = Layout;

const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: '/jobs',
      icon: <ExperimentOutlined />,
      label: (
        <span style={{ fontWeight: 'bold', fontSize: '18px' }}>Test Tasks</span>
      ),
    },
    {
      key: '/result-comparison',
      icon: <BarChartOutlined />,
      label: (
        <span style={{ fontWeight: 'bold', fontSize: '18px' }}>
          Model Arena
        </span>
      ),
    },
    {
      key: '/system-monitor',
      icon: <MonitorOutlined />,
      label: (
        <span style={{ fontWeight: 'bold', fontSize: '18px' }}>
          Monitor Hub
        </span>
      ),
    },
  ];

  return (
    <Sider
      width={210}
      style={{
        background: '#fff',
        height: '100%',
        borderRight: '1px solid #f0f0f0',
      }}
    >
      <ConfigProvider
        theme={{
          components: {
            Menu: {
              itemSelectedBg: '#fff',
              itemSelectedColor: '#1890ff',
            },
          },
        }}
      >
        <Menu
          mode='inline'
          selectedKeys={[location.pathname]}
          style={{
            height: '100%',
            borderRight: 0,
            background: '#fff',
            paddingTop: '20px',
          }}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </ConfigProvider>
    </Sider>
  );
};

export default Sidebar;
