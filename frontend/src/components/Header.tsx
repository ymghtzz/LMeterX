/**
 * @file Header.tsx
 * @description Header component
 * @author Charm
 * @copyright 2025
 * */
import { Layout } from 'antd';
import React from 'react';
import { useNavigate } from 'react-router-dom';

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
    </AntdHeader>
  );
};

export default Header;
