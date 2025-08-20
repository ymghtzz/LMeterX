/**
 * @file Header.tsx
 * @description Header component
 * @author Charm
 * @copyright 2025
 * */
import { GithubOutlined } from '@ant-design/icons';
import { Button, Layout } from 'antd';
import React from 'react';
import { useNavigate } from 'react-router-dom';
import LanguageSwitcher from './LanguageSwitcher';

const { Header: AntdHeader } = Layout;

const Header: React.FC = () => {
  const navigate = useNavigate();

  const headerStyle: React.CSSProperties = {
    background: '#fff',
    padding: '0 24px',
    borderBottom: '1px solid #f0f0f0',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: '64px',
    position: 'sticky',
    top: 0,
    zIndex: 10,
  };

  const logoStyle: React.CSSProperties = {
    height: '45px',
    cursor: 'pointer',
    marginTop: '45px',
    marginBottom: '10px',
  };

  const githubButtonStyle: React.CSSProperties = {
    marginRight: '12px',
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  };

  return (
    <AntdHeader style={headerStyle}>
      <div className='logo'>
        <img
          src='/logo.png'
          alt='logo_alt'
          style={logoStyle}
          onClick={() => navigate('/jobs')}
        />
      </div>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <Button
          type='text'
          icon={<GithubOutlined />}
          style={githubButtonStyle}
          href='https://github.com/MigoXLab/LMeterX'
          target='_blank'
          rel='noopener noreferrer'
        >
          GitHub
        </Button>
        <LanguageSwitcher />
      </div>
    </AntdHeader>
  );
};

export default Header;
