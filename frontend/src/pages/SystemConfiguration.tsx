/**
 * @file SystemConfiguration.tsx
 * @description System Configuration page component
 * @author Charm
 * @copyright 2025
 * */

import { InfoCircleOutlined, SettingOutlined } from '@ant-design/icons';
import {
  App,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Space,
  Tooltip,
  Typography,
} from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import { systemApi } from '../api/services';
import { PageHeader } from '../components/ui/PageHeader';

const { Text } = Typography;

const SystemConfiguration: React.FC = () => {
  const [configs, setConfigs] = useState<any[]>([]);
  const [aiConfigModalVisible, setAiConfigModalVisible] = useState(false);
  const [aiForm] = Form.useForm();
  const { message } = App.useApp();
  const isInitializedRef = useRef(false);

  const fetchConfigs = async () => {
    // 防止重复调用
    if (isInitializedRef.current) {
      return;
    }

    try {
      isInitializedRef.current = true;
      const response = await systemApi.getSystemConfigs();
      if (response.data?.status === 'success') {
        setConfigs(response.data.data || []);
      } else {
        message.error('Failed to load system configurations');
      }
    } catch (err: any) {
      message.error(`Failed to load configurations: ${err.message}`);
    }
  };

  const handleAiConfigSubmit = async (values: any) => {
    try {
      // batch create or update AI service configurations
      const configsToUpdate = [
        {
          config_key: 'ai_service_host',
          config_value: values.host,
          description: 'The host URL for the AI service',
        },
        {
          config_key: 'ai_service_model',
          config_value: values.model,
          description: 'The AI model to use for analysis',
        },
        {
          config_key: 'ai_service_api_key',
          config_value: values.api_key,
          description: 'The API key for authentication',
        },
      ];

      // Use batch operation instead of multiple individual API calls
      await systemApi.batchUpsertSystemConfigs(configsToUpdate);

      message.success('AI service configuration updated successfully');
      setAiConfigModalVisible(false);

      // Update configs
      await fetchConfigs();
    } catch (err: any) {
      message.error(`Failed to save AI service configuration: ${err.message}`);
    }
  };

  const handleConfigureAI = async () => {
    try {
      // update the latest configs
      const response = await systemApi.getSystemConfigs();
      if (response.data?.status === 'success') {
        const latestConfigs = response.data.data || [];

        const hostConfig = latestConfigs.find(
          c => c.config_key === 'ai_service_host'
        );
        const modelConfig = latestConfigs.find(
          c => c.config_key === 'ai_service_model'
        );
        const apiKeyConfig = latestConfigs.find(
          c => c.config_key === 'ai_service_api_key'
        );

        // Reset form to current values
        aiForm.resetFields();
        aiForm.setFieldsValue({
          host: hostConfig?.config_value || '',
          model: modelConfig?.config_value || '',
          api_key: apiKeyConfig?.config_value || '',
        });
        setAiConfigModalVisible(true);
      } else {
        message.error('Failed to load system configurations');
      }
    } catch (err: any) {
      message.error(`Failed to load configurations: ${err.message}`);
    }
  };

  useEffect(() => {
    fetchConfigs();
  }, []);

  const aiServiceConfigs = [
    {
      key: 'ai_service_host',
      label: 'Host',
      placeholder: 'https://api.openai.com',
      description: 'The host URL for the AI service',
    },
    {
      key: 'ai_service_model',
      label: 'Model',
      placeholder: 'gpt-3.5-turbo',
      description: 'The AI model to use for analysis',
    },
    {
      key: 'ai_service_api_key',
      label: 'API Key',
      placeholder: 'Enter your API key',
      description: 'The API key for authentication',
      isPassword: true,
    },
  ];

  return (
    <div className='page-container'>
      <PageHeader
        title=' System Configuration'
        icon={<SettingOutlined />}
        level={3}
        className='text-center w-full'
      />

      <Card className='mb-24'>
        <div className='mb-16'>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 16,
            }}
          >
            <h3>AI Service Configuration</h3>
            <Button
              type='primary'
              icon={<SettingOutlined />}
              onClick={handleConfigureAI}
            >
              Configure
            </Button>
          </div>
          <p style={{ color: '#666', marginBottom: 16 }}>
            These settings are used when performing AI analysis on performance
            results.
          </p>
        </div>

        <Form layout='vertical' style={{ maxWidth: 600 }}>
          {aiServiceConfigs.map(config => {
            const existingConfig = configs.find(
              c => c.config_key === config.key
            );
            return (
              <Form.Item
                key={config.key}
                label={
                  <div
                    style={{ display: 'flex', alignItems: 'center', gap: 8 }}
                  >
                    <span>{config.label}</span>
                    <Tooltip title={config.description}>
                      <InfoCircleOutlined
                        style={{ color: '#999', fontSize: '14px' }}
                      />
                    </Tooltip>
                  </div>
                }
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ flex: 1 }}>
                    {existingConfig ? (
                      config.isPassword ? (
                        <Text style={{ color: '#999' }}>••••••••••••••••</Text>
                      ) : config.key === 'ai_service_host' ? (
                        <Text>
                          {existingConfig.config_value}/chat/completions
                        </Text>
                      ) : (
                        <Text>{existingConfig.config_value}</Text>
                      )
                    ) : (
                      <Text style={{ color: '#999' }}>Not configured</Text>
                    )}
                  </div>
                </div>
              </Form.Item>
            );
          })}
        </Form>
      </Card>

      {/* AI Service Configuration Modal */}
      <Modal
        title='Configuration'
        open={aiConfigModalVisible}
        onCancel={() => {
          aiForm.resetFields();
          setAiConfigModalVisible(false);
        }}
        footer={null}
        width={600}
      >
        <Form form={aiForm} layout='vertical' onFinish={handleAiConfigSubmit}>
          <Form.Item
            label='Host'
            name='host'
            rules={[
              { required: true, message: 'Please enter AI service host URL' },
            ]}
            extra='Enter the base URL for your AI service (e.g., https://api.openai.com)'
          >
            <Input
              placeholder='https://your-api-domain.com'
              addonAfter={
                <Input
                  value='/chat/completions'
                  disabled
                  style={{
                    width: '180px',
                    backgroundColor: '#f5f5f5',
                    border: 'none',
                  }}
                />
              }
            />
          </Form.Item>

          <Form.Item
            label='Model'
            name='model'
            rules={[{ required: true, message: 'Please enter AI model name' }]}
            extra='Enter the model name to use for analysis (e.g., gpt-3.5-turbo, gpt-4)'
          >
            <Input placeholder='gpt-3.5-turbo' />
          </Form.Item>

          <Form.Item
            label='API Key'
            name='api_key'
            rules={[{ required: true, message: 'Please enter API key' }]}
            extra='Enter your API key for authentication'
          >
            {/* <Input.Password placeholder='Enter your API key' visibilityToggle /> */}
            <Input.Password
              placeholder='Enter your API key without `Bearer` prefix'
              visibilityToggle={false}
              onCopy={e => e.preventDefault()}
              onCut={e => e.preventDefault()}
            />
          </Form.Item>

          <Form.Item>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Space>
                <Button
                  onClick={() => {
                    aiForm.resetFields();
                    setAiConfigModalVisible(false);
                  }}
                >
                  Cancel
                </Button>
                <Button type='primary' htmlType='submit'>
                  Save
                </Button>
              </Space>
            </div>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default SystemConfiguration;
