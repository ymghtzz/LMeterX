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
      label: <span className='text-bold text-xl'>Test Tasks</span>,
    },
    {
      key: '/result-comparison',
      icon: <BarChartOutlined />,
      label: <span className='text-bold text-xl'>Model Arena</span>,
    },
    {
      key: '/system-monitor',
      icon: <MonitorOutlined />,
      label: <span className='text-bold text-xl'>Monitor Hub</span>,
    },
  ];

  return (
    <Sider width={210} className='custom-sider'>
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
          className='custom-menu'
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </ConfigProvider>
    </Sider>
  );
};

export default Sidebar;
