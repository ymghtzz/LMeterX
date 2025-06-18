/**
 * @file CreateJobForm.tsx
 * @description Create job form component
 * @author Charm
 * @copyright 2025
 * */
import {
  ApiOutlined,
  InfoCircleOutlined,
  MinusCircleOutlined,
  PlusOutlined,
  RocketOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import {
  App,
  Button,
  Card,
  Col,
  Collapse,
  Form,
  Input,
  InputNumber,
  Radio,
  Row,
  Space,
  theme,
  Tooltip,
  Upload,
} from 'antd';
import type { FormInstance } from 'antd/es/form';
import React, { useEffect, useRef, useState } from 'react';

import { uploadCertificateFiles } from '@/api/services';
import { BenchmarkJob } from '@/types/benchmark';

interface CreateJobFormProps {
  onSubmit: (values: any) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
  initialData?: Partial<BenchmarkJob> | null;
}

const CreateJobFormContent: React.FC<CreateJobFormProps> = ({
  onSubmit,
  onCancel,
  loading,
  initialData,
}) => {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const concurrentUsers = Form.useWatch('concurrent_users', form);
  const formRef = useRef<FormInstance>(null);
  const [submitting, setSubmitting] = useState(loading || false);
  const { token } = theme.useToken();
  const [tempTaskId] = useState(`temp-${Date.now()}`);
  const [formConnected, setFormConnected] = useState(false);

  // add state to track if auto sync spawn_rate
  const [autoSyncSpawnRate, setAutoSyncSpawnRate] = useState(true);
  const [isCopyMode, setIsCopyMode] = useState(false);

  useEffect(() => {
    setFormConnected(true);
  }, []);

  // when concurrent_users changes and autoSyncSpawnRate is true, auto update spawn_rate
  useEffect(() => {
    if (autoSyncSpawnRate && formConnected) {
      if (concurrentUsers && typeof concurrentUsers === 'number') {
        form.setFieldsValue({ spawn_rate: concurrentUsers });
      }
    }
  }, [concurrentUsers, autoSyncSpawnRate, form, formConnected]);

  // listen to concurrent_users field changes
  const handleConcurrentUsersChange = (value: number) => {
    if (autoSyncSpawnRate && value) {
      form.setFieldsValue({ spawn_rate: value });
    }
  };

  // when user manually changes spawn_rate, close auto sync
  const handleSpawnRateChange = () => {
    setAutoSyncSpawnRate(false);
  };

  // update submitting state using loading prop
  useEffect(() => {
    setSubmitting(loading || false);
  }, [loading]);

  // Effect to populate form when initialData is provided (for copy mode)
  useEffect(() => {
    if (initialData && formConnected) {
      setIsCopyMode(true);
      console.log('CreateJobForm: Received initialData:', initialData);

      const dataToFill: any = { ...initialData };

      if (
        dataToFill.stream_mode !== undefined &&
        dataToFill.stream_mode !== null
      ) {
        const streamValue = String(dataToFill.stream_mode);
        if (streamValue === '1') {
          dataToFill.stream_mode = true; // "stream"
        } else if (streamValue === '0') {
          dataToFill.stream_mode = false; // "non-stream"
        }
      }

      // use temp_task_id
      dataToFill.temp_task_id = tempTaskId;

      // handle headers
      const currentHeaders = initialData.headers
        ? JSON.parse(JSON.stringify(initialData.headers))
        : [];

      // ensure Content-Type exists and is fixed
      const contentTypeHeader = currentHeaders.find(
        (h: { key: string }) => h.key === 'Content-Type'
      );
      if (contentTypeHeader) {
        contentTypeHeader.value = 'application/json';
        contentTypeHeader.fixed = true;
      } else {
        currentHeaders.unshift({
          key: 'Content-Type',
          value: 'application/json',
          fixed: true,
        });
      }

      // ensure Authorization exists (even if the value is empty)
      const authHeader = currentHeaders.find(
        (h: { key: string }) => h.key === 'Authorization'
      );
      if (!authHeader) {
        currentHeaders.push({ key: 'Authorization', value: '', fixed: false });
      }
      dataToFill.headers = currentHeaders;

      // clean fields that should not be copied directly or provided by the user
      delete dataToFill.id;
      delete dataToFill.status;
      delete dataToFill.created_at;
      delete dataToFill.updated_at;
      // actual certificate file needs to be uploaded again

      form.setFieldsValue(dataToFill);

      if (
        dataToFill.concurrent_users &&
        dataToFill.spawn_rate &&
        dataToFill.concurrent_users === dataToFill.spawn_rate
      ) {
        setAutoSyncSpawnRate(true);
      } else {
        setAutoSyncSpawnRate(false);
      }

      if ((initialData as any).cert_config) {
        message.info(
          'Task configuration copied. Note: Client certificates (if any) need to be re-uploaded.',
          5
        );
      }
    } else if (formConnected) {
      setIsCopyMode(false);
      form.resetFields();
      const currentConcurrentUsers =
        form.getFieldValue('concurrent_users') || 1;
      form.setFieldsValue({
        temp_task_id: tempTaskId,
        spawn_rate: currentConcurrentUsers,
      });
      setAutoSyncSpawnRate(true);
    }
  }, [initialData, form, formConnected, tempTaskId]);

  // handle certificate file upload
  const handleCertFileUpload = async (options: any) => {
    const { file, onSuccess, onError } = options;
    try {
      form.setFieldsValue({
        temp_task_id: tempTaskId,
        cert_file: file,
      });
      message.success(`${file.name} file selected`);
      onSuccess();
    } catch (error) {
      console.error('Upload failed:', error);
      message.error(`${file.name} upload failed`);
      onError();
    }
  };

  // handle private key file upload
  const handleKeyFileUpload = async (options: any) => {
    const { file, onSuccess, onError } = options;
    try {
      form.setFieldsValue({
        temp_task_id: tempTaskId,
        key_file: file,
      });
      message.success(`${file.name} file selected`);
      onSuccess();
    } catch (error) {
      console.error('Upload failed:', error);
      message.error(`${file.name} upload failed`);
      onError();
    }
  };

  // handle combined certificate file upload
  const handleCombinedCertUpload = async (options: any) => {
    const { file, onSuccess, onError } = options;
    try {
      form.setFieldsValue({
        temp_task_id: tempTaskId,
        cert_file: file,
        key_file: null,
      });
      message.success(`${file.name} file selected`);
      onSuccess();
    } catch (error) {
      console.error('Upload failed:', error);
      message.error(`${file.name} upload failed`);
      onError();
    }
  };

  const handleSubmit = async () => {
    if (submitting) return;

    try {
      setSubmitting(true);
      const values = await form.validateFields();

      if (values.cert_file) {
        try {
          const certType = form.getFieldValue('cert_type') || 'combined';

          const result = await uploadCertificateFiles(
            values.cert_file,
            certType === 'separate' ? values.key_file : null,
            tempTaskId,
            certType
          );

          values.cert_config = result.cert_config;

          // delete file objects from form to avoid serialization issues
          delete values.cert_file;
          delete values.key_file;

          // keep temp_task_id for backend association
          values.temp_task_id = tempTaskId;
        } catch (error) {
          console.error('Certificate upload failed:', error);
          message.error('Certificate upload failed, please try again');
          setSubmitting(false);
          return;
        }
      }

      await onSubmit(values);
    } catch (error) {
      console.error('Validation failed:', error);
      setSubmitting(false); // Only reset state here when error occurs
    }
  };

  // create advanced settings panel content
  const advancedPanelContent = (
    <>
      {/* Header configuration */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 8 }}>
          <Space>
            <span>Request Headers Configuration</span>
            <Tooltip title='Authorization requires API Key with Bearer prefix'>
              <InfoCircleOutlined />
            </Tooltip>
          </Space>
        </div>
        <Form.List name='headers'>
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => {
                const isFixed = form.getFieldValue(['headers', name, 'fixed']);
                const headerKey = form.getFieldValue(['headers', name, 'key']);
                const isAuth = headerKey === 'Authorization';

                return (
                  <Space key={key} style={{ display: 'flex', marginBottom: 8 }}>
                    <Form.Item
                      {...restField}
                      name={[name, 'key']}
                      style={{ flex: 1 }}
                    >
                      <Input placeholder='Header Key' disabled={isFixed} />
                    </Form.Item>
                    <Form.Item
                      {...restField}
                      name={[name, 'value']}
                      style={{ flex: 1 }}
                      rules={
                        isAuth
                          ? [
                              {
                                required: false,
                                message:
                                  'Please enter API Key with Bearer prefix',
                              },
                            ]
                          : []
                      }
                    >
                      <Input
                        placeholder={
                          isAuth ? 'API Key with Bearer prefix' : 'Header Value'
                        }
                        disabled={isFixed}
                      />
                    </Form.Item>
                    {!isFixed && (
                      <MinusCircleOutlined
                        onClick={() => remove(name)}
                        style={{ marginTop: 8 }}
                      />
                    )}
                  </Space>
                );
              })}
              <Button
                type='dashed'
                onClick={() => add()}
                block
                icon={<PlusOutlined />}
              >
                Add Request Header
              </Button>
            </>
          )}
        </Form.List>
      </div>

      {/* Client certificate upload */}
      <Form.Item
        name='client_cert_key'
        label={
          <span>
            Client Certificate
            <Tooltip title='Certificate files required for HTTPS mutual authentication'>
              <InfoCircleOutlined style={{ marginLeft: 5 }} />
            </Tooltip>
          </span>
        }
      >
        <div>
          <Radio.Group
            defaultValue='combined'
            onChange={e => form.setFieldsValue({ cert_type: e.target.value })}
            style={{ marginBottom: 16 }}
          >
            <Radio value='combined'>Combined Upload</Radio>
            <Radio value='separate'>Separate Upload</Radio>
          </Radio.Group>

          <Form.Item noStyle shouldUpdate>
            {({ getFieldValue }) => {
              const certType = getFieldValue('cert_type') || 'combined';
              return certType === 'combined' ? (
                <div style={{ padding: '8px 0' }}>
                  <Upload
                    maxCount={1}
                    accept='.pem'
                    customRequest={handleCombinedCertUpload}
                    listType='text'
                    style={{ width: '100%' }}
                  >
                    <Button
                      icon={<UploadOutlined />}
                      size='middle'
                      style={{ width: '180px', height: '40px' }}
                    >
                      Upload Cert+Key File
                    </Button>
                  </Upload>
                  <div
                    style={{
                      marginTop: 8,
                      color: token.colorTextSecondary,
                      fontSize: '12px',
                    }}
                  >
                    Supported format: .pem (contains certificate and private
                    key)
                  </div>
                </div>
              ) : (
                <div style={{ padding: '8px 0' }}>
                  <Space
                    direction='horizontal'
                    style={{
                      width: '100%',
                      display: 'flex',
                      justifyContent: 'flex-start',
                    }}
                  >
                    <div>
                      <Upload
                        maxCount={1}
                        accept='.crt,.pem'
                        customRequest={handleCertFileUpload}
                        listType='text'
                      >
                        <Button
                          icon={<UploadOutlined />}
                          size='middle'
                          style={{ width: '180px', height: '40px' }}
                        >
                          Upload Certificate
                        </Button>
                      </Upload>
                      <div
                        style={{
                          marginTop: 4,
                          color: token.colorTextSecondary,
                          fontSize: '12px',
                        }}
                      >
                        Supported formats: .crt, .pem
                      </div>
                    </div>

                    <div style={{ marginLeft: 24 }}>
                      <Upload
                        maxCount={1}
                        accept='.key,.pem'
                        customRequest={handleKeyFileUpload}
                        listType='text'
                      >
                        <Button
                          icon={<UploadOutlined />}
                          size='middle'
                          style={{ width: '180px', height: '40px' }}
                        >
                          Upload Private Key
                        </Button>
                      </Upload>
                      <div
                        style={{
                          marginTop: 4,
                          color: token.colorTextSecondary,
                          fontSize: '12px',
                        }}
                      >
                        Supported formats: .key, .pem
                      </div>
                    </div>
                  </Space>
                </div>
              );
            }}
          </Form.Item>
        </div>
      </Form.Item>
    </>
  );

  // define collapse panel items
  const collapseItems = [
    {
      key: 'advanced',
      // header: <span style={{ color: token.colorTextSecondary }}>Click to expand more configuration options</span>,
      label: (
        <Space style={{ marginTop: 3 }}>
          {/* <SettingOutlined /> */}
          <span
            style={{ fontSize: 16, marginTop: '-2px', display: 'inline-block' }}
          >
            Advanced Settings
          </span>
        </Space>
      ),
      children: advancedPanelContent,
      styles: { header: { paddingLeft: 0 } },
    },
  ];

  return (
    <Card
      className='form-card'
      styles={{
        body: { padding: '24px', boxShadow: token.boxShadowTertiary },
      }}
    >
      <Form
        form={form}
        ref={formRef}
        layout='vertical'
        initialValues={{
          headers: [
            { key: 'Content-Type', value: 'application/json', fixed: true },
            { key: 'Authorization', value: '', fixed: false },
          ],
          stream_mode: true,
          spawn_rate: 1,
          concurrent_users: 1,
          chat_type: 0,
          temp_task_id: tempTaskId,
        }}
        onFinish={handleSubmit}
      >
        {/* Hidden field for storing file and temporary task ID */}
        <Form.Item name='temp_task_id' hidden>
          <Input />
        </Form.Item>
        <Form.Item name='cert_file' hidden>
          <Input />
        </Form.Item>
        <Form.Item name='key_file' hidden>
          <Input />
        </Form.Item>

        {/* Basic configuration */}
        <div style={{ margin: '16px 0', fontWeight: 'bold', fontSize: '16px' }}>
          <Space>
            <ApiOutlined />
            <span>Basic Configuration</span>
          </Space>
        </div>

        <Row gutter={24}>
          <Col span={24}>
            <Form.Item
              name='name'
              label='Task Name'
              rules={[{ required: true, message: 'Please enter task name' }]}
            >
              <Input placeholder='Please enter task name' />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={24}>
          <Col span={24}>
            <Form.Item name='api_url' label='API URL' required>
              <div style={{ display: 'flex', width: '100%' }}>
                <Form.Item
                  name='target_host'
                  noStyle
                  rules={[{ required: true, message: 'Please enter API URL' }]}
                >
                  <Input
                    style={{ width: '100%', flexGrow: 7 }}
                    placeholder='https://your-api-domain.com'
                  />
                </Form.Item>
                <Input
                  style={{ width: '30%', flexGrow: 3 }}
                  value='/v1/chat/completions'
                  disabled
                />
              </div>
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={24}>
          <Col span={24}>
            <Form.Item
              name='model'
              label='Model Name'
              rules={[{ required: true, message: 'Please enter model name' }]}
            >
              <Input placeholder='e.g.: internlm3-latest' />
            </Form.Item>
          </Col>
        </Row>

        {/* Test configuration */}
        <div
          style={{
            margin: '24px 0 16px',
            fontWeight: 'bold',
            fontSize: '16px',
          }}
        >
          <Space>
            <RocketOutlined />
            <span>Test Configuration</span>
          </Space>
        </div>

        <Row gutter={24}>
          <Col span={8}>
            <Form.Item
              name='duration'
              label='Test Duration (s)'
              rules={[{ required: true, message: 'Please enter duration' }]}
            >
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          </Col>

          <Col span={8}>
            <Form.Item
              name='concurrent_users'
              label='Concurrent Users'
              rules={[
                { required: true, message: 'Please enter concurrent users' },
              ]}
            >
              <InputNumber
                min={1}
                style={{ width: '100%' }}
                onChange={handleConcurrentUsersChange}
              />
            </Form.Item>
          </Col>

          <Col span={8}>
            <Form.Item
              name='spawn_rate'
              label={
                <span>
                  User Spawn Rate
                  <Tooltip title='Number of virtual users created per second'>
                    <InfoCircleOutlined style={{ marginLeft: 5 }} />
                  </Tooltip>
                </span>
              }
            >
              <InputNumber
                min={1}
                style={{ width: '100%' }}
                onChange={handleSpawnRateChange}
              />
            </Form.Item>
          </Col>
        </Row>

        <div style={{ display: 'flex', gap: '16px', marginBottom: '24px' }}>
          <Form.Item
            name='chat_type'
            label={
              <span>
                Chat Type
                <Tooltip title='Text-only or image-text conversations'>
                  <InfoCircleOutlined style={{ marginLeft: 5 }} />
                </Tooltip>
              </span>
            }
            rules={[{ required: true }]}
            style={{ flex: 1 }}
          >
            <Radio.Group>
              <Radio value={0}>Text Only</Radio>
              <Radio value={1}>Image-Text</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item
            name='stream_mode'
            label={
              <span>
                Output Mode
                <Tooltip title='Whether to enable streaming response'>
                  <InfoCircleOutlined style={{ marginLeft: 5 }} />
                </Tooltip>
              </span>
            }
            rules={[{ required: true }]}
            style={{ flex: 1 }}
          >
            <Radio.Group>
              <Radio value>Streaming</Radio>
              <Radio value={false}>Non-streaming</Radio>
            </Radio.Group>
          </Form.Item>
        </div>

        {/* More settings */}
        <div
          style={{
            margin: '24px 0 8px',
            fontWeight: 'bold',
            fontSize: '16px',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <Collapse
            ghost
            defaultActiveKey={[]}
            className='more-settings-collapse'
            items={collapseItems}
          />
        </div>

        <Form.Item style={{ marginTop: 24, textAlign: 'right' }}>
          <Space>
            <Button onClick={onCancel}>Cancel</Button>
            <Button type='primary' htmlType='submit' loading={submitting}>
              {submitting ? 'Submitting...' : isCopyMode ? 'Create' : 'Create'}
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  );
};

const CreateJobForm: React.FC<CreateJobFormProps> = props => (
  <App>
    <CreateJobFormContent {...props} />
  </App>
);

export default CreateJobForm;
