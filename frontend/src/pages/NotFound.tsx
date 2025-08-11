/**
 * @file NotFound.tsx
 * @description Not found page component
 * @author Charm
 * @copyright 2025
 * */
import { Button, Result } from 'antd';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

const NotFound: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <Result
      status='404'
      title={t('pages.notFound.title')}
      subTitle={t('pages.notFound.description')}
      extra={
        <Button type='primary' onClick={() => navigate('/')}>
          {t('pages.notFound.backHome')}
        </Button>
      }
    />
  );
};

export default NotFound;
