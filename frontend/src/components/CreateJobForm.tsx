/**
 * @file CreateJobForm.tsx
 * @description Create job form component
 * @author Charm
 * @copyright 2025
 * */
import {
  ApiOutlined,
  BugOutlined,
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
  Modal,
  Radio,
  Row,
  Select,
  Space,
  theme,
  Tooltip,
  Typography,
  Upload,
} from 'antd';
import React, { useCallback, useEffect, useState } from 'react';

import { benchmarkJobApi, uploadCertificateFiles } from '@/api/services';
import { BenchmarkJob } from '@/types/benchmark';

const { TextArea } = Input;
const { Text } = Typography;

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
  const [submitting, setSubmitting] = useState(loading || false);
  const [testing, setTesting] = useState(false);
  const { token } = theme.useToken();
  const [tempTaskId] = useState(`temp-${Date.now()}`);
  // add state to track if auto sync spawn_rate
  const [autoSyncSpawnRate, setAutoSyncSpawnRate] = useState(true);
  const [isCopyMode, setIsCopyMode] = useState(false);
  const [testModalVisible, setTestModalVisible] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);

  // Handle modal open/close body class management
  useEffect(() => {
    if (testModalVisible) {
      document.body.classList.add('api-test-modal-open');
    } else {
      document.body.classList.remove('api-test-modal-open');
    }

    return () => {
      document.body.classList.remove('api-test-modal-open');
    };
  }, [testModalVisible]);

  // Form values states to replace Form.useWatch
  const [concurrentUsers, setConcurrentUsers] = useState<number>();
  const [apiPath, setApiPath] = useState<string>('/v1/chat/completions');
  const [streamMode, setStreamMode] = useState<boolean>(true);
  const [isFormReady, setIsFormReady] = useState(false);

  // Initialize form ready state
  useEffect(() => {
    setIsFormReady(true);
  }, []);

  // when concurrent_users changes and autoSyncSpawnRate is true, auto update spawn_rate
  useEffect(() => {
    if (autoSyncSpawnRate && isFormReady) {
      if (concurrentUsers && typeof concurrentUsers === 'number') {
        form.setFieldsValue({ spawn_rate: concurrentUsers });
      }
    }
  }, [concurrentUsers, autoSyncSpawnRate, form, isFormReady]);

  // listen to concurrent_users field changes
  const handleConcurrentUsersChange = (value: number) => {
    setConcurrentUsers(value);
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
    if (initialData) {
      setIsCopyMode(true);

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
        currentHeaders.push({
          key: 'Authorization',
          value: '',
          fixed: false,
        });
      }
      dataToFill.headers = currentHeaders;

      // handle cookies
      const currentCookies = initialData.cookies
        ? JSON.parse(JSON.stringify(initialData.cookies))
        : [];
      dataToFill.cookies = currentCookies;

      // handle field_mapping based on API type
      const isChatCompletions = dataToFill.api_path === '/v1/chat/completions';
      const isStreaming = dataToFill.stream_mode === true;

      // Preserve original field_mapping and request_payload when copying
      const originalFieldMapping = dataToFill.field_mapping
        ? JSON.parse(JSON.stringify(dataToFill.field_mapping))
        : {};
      const originalRequestPayload = dataToFill.request_payload;

      if (isChatCompletions) {
        // For chat completions API, preserve original values when copying and merge with defaults only if needed
        const defaultFieldMapping = {
          prompt: '',
          stream_prefix: 'data:',
          data_format: 'json',
          content: isStreaming
            ? 'choices.0.delta.content'
            : 'choices.0.message.content',
          reasoning_content: isStreaming
            ? 'choices.0.delta.reasoning_content'
            : 'choices.0.message.reasoning_content',
          end_prefix: 'data:',
          stop_flag: '[DONE]',
          end_condition: '',
        };

        // Preserve original values first, then fill in missing required fields with defaults
        dataToFill.field_mapping = {
          ...defaultFieldMapping,
          ...originalFieldMapping, // Original values take precedence
        };
      } else {
        // For custom APIs, preserve original field_mapping and request_payload completely
        dataToFill.field_mapping = originalFieldMapping || {
          prompt: '',
          stream_prefix: '',
          data_format: 'json',
          content: '',
          reasoning_content: '',
          end_prefix: '',
          stop_flag: '',
          end_condition: '',
        };
        dataToFill.request_payload = originalRequestPayload;
      }

      // clean fields that should not be copied directly or provided by the user
      delete dataToFill.id;
      delete dataToFill.status;
      delete dataToFill.created_at;
      delete dataToFill.updated_at;
      // actual certificate file needs to be uploaded again

      form.setFieldsValue(dataToFill);

      // Update apiPath state immediately to ensure correct API type detection
      if (dataToFill.api_path) {
        setApiPath(dataToFill.api_path);
      }

      // Update stream mode state for proper field mapping
      if (dataToFill.stream_mode !== undefined) {
        setStreamMode(dataToFill.stream_mode);
      }

      if (
        dataToFill.concurrent_users &&
        dataToFill.spawn_rate &&
        dataToFill.concurrent_users === dataToFill.spawn_rate
      ) {
        setAutoSyncSpawnRate(true);
      } else {
        setAutoSyncSpawnRate(false);
      }

      // Show message for advanced settings that need attention
      const hasCustomHeaders =
        dataToFill.headers &&
        dataToFill.headers.some(
          (h: any) => h.key !== 'Content-Type' && h.key !== 'Authorization'
        );
      const hasCookies = dataToFill.cookies && dataToFill.cookies.length > 0;
      const hasCertConfig = !!(initialData as any).cert_config;

      if (hasCustomHeaders || hasCookies || hasCertConfig) {
        message.warning(
          'Task template copied. Please note: Advanced settings need to be re-filled or uploaded.',
          5
        );
      }
    } else if (!isCopyMode) {
      setIsCopyMode(false);
      // reset form fields
      const currentTempTaskId = form.getFieldValue('temp_task_id');
      if (currentTempTaskId !== tempTaskId) {
        form.resetFields();
        const currentConcurrentUsers =
          form.getFieldValue('concurrent_users') || 1;
        form.setFieldsValue({
          temp_task_id: tempTaskId,
          spawn_rate: currentConcurrentUsers,
        });
        setAutoSyncSpawnRate(true);
      }
    }
  }, [initialData, form, tempTaskId, message]);

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
      message.error(`${file.name} upload failed`);
      onError();
    }
  };

  // Test API endpoint
  const handleTestAPI = async () => {
    try {
      setTesting(true);
      const values = await form.validateFields();

      // Validate request payload for custom APIs
      if (
        values.api_path !== '/v1/chat/completions' &&
        !values.request_payload
      ) {
        message.error('Request payload is required for custom API endpoints');
        return;
      }

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
          delete values.cert_file;
          delete values.key_file;
          values.temp_task_id = tempTaskId;
        } catch (error) {
          message.error('Certificate upload failed, please try again');
          return;
        }
      }

      // Prepare test data - exclude field_mapping as it's not needed for testing
      const testData = { ...values };
      delete testData.field_mapping;
      delete testData.cert_type;

      // Call test API
      const apiResponse = await benchmarkJobApi.testApiEndpoint(testData);
      // Extract the actual backend response data
      const result = apiResponse.data;

      setTestResult(result);
      setTestModalVisible(true);
    } catch (error) {
      message.error('Test failed, please check your configuration');
    } finally {
      setTesting(false);
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
          message.error('Certificate upload failed, please try again');
          setSubmitting(false);
          return;
        }
      }

      await onSubmit(values);
    } catch (error) {
      setSubmitting(false); // Only reset state here when error occurs
    }
  };

  // Determine if current API is chat completions
  const isChatCompletionsAPI = !apiPath || apiPath === '/v1/chat/completions';

  // State to track form validity for testing
  const [isTestButtonEnabled, setIsTestButtonEnabled] = useState(false);

  // Check if form is valid for testing
  const checkFormValidForTest = useCallback(() => {
    try {
      const values = form.getFieldsValue();

      // Basic Configuration required fields
      if (!values.target_host || !values.api_path) {
        return false;
      }

      // Test Configuration required fields
      if (
        !values.model ||
        !values.duration ||
        !values.concurrent_users ||
        values.stream_mode === undefined ||
        values.stream_mode === null
      ) {
        return false;
      }

      // Chat type is required for chat completions API
      if (
        isChatCompletionsAPI &&
        (values.chat_type === undefined || values.chat_type === null)
      ) {
        return false;
      }

      // Request payload is required for custom APIs
      if (!isChatCompletionsAPI && !values.request_payload) {
        return false;
      }

      // API Field Mapping fields are NOT required for testing

      return true;
    } catch (error) {
      return false;
    }
  }, [form, isChatCompletionsAPI]);

  // Update test button state when form values change
  useEffect(() => {
    const isValid = checkFormValidForTest();
    setIsTestButtonEnabled(isValid);
  }, [checkFormValidForTest]);

  // Initial check after form is ready
  useEffect(() => {
    if (isFormReady) {
      const isValid = checkFormValidForTest();
      setIsTestButtonEnabled(isValid);
    }
  }, [isFormReady, checkFormValidForTest]);

  // Function for external use (backwards compatibility)
  const isFormValidForTest = () => {
    return isTestButtonEnabled;
  };

  // Clear fields when switching between API types (but not in copy mode)
  useEffect(() => {
    if (!isCopyMode && isFormReady) {
      if (isChatCompletionsAPI) {
        // Set default values for chat completions API only if not already set
        const currentFieldMapping = form.getFieldValue('field_mapping') || {};
        const currentStreamMode = form.getFieldValue('stream_mode');
        const isStreaming =
          currentStreamMode === true || currentStreamMode === undefined;

        // Only set default values if field_mapping is empty or not properly initialized
        if (
          !currentFieldMapping.stream_prefix &&
          !currentFieldMapping.content
        ) {
          form.setFieldsValue({
            chat_type: form.getFieldValue('chat_type') || 0,
            field_mapping: {
              prompt: '',
              stream_prefix: 'data:',
              data_format: 'json',
              content: isStreaming
                ? 'choices.0.delta.content'
                : 'choices.0.message.content',
              reasoning_content: isStreaming
                ? 'choices.0.delta.reasoning_content'
                : 'choices.0.message.reasoning_content',
              end_prefix: 'data:',
              stop_flag: '[DONE]',
              end_condition: '',
            },
          });
        }
      } else {
        // Clear custom API fields when switching to chat completions
        const currentFieldMapping = form.getFieldValue('field_mapping') || {};
        // Only clear if switching from chat completions to custom API
        if (
          currentFieldMapping.stream_prefix === 'data:' &&
          currentFieldMapping.stop_flag === '[DONE]'
        ) {
          form.setFieldsValue({
            request_payload: undefined,
            field_mapping: {
              prompt: '',
              stream_prefix: '',
              data_format: 'json',
              content: '',
              reasoning_content: '',
              end_prefix: '',
              stop_flag: '',
              end_condition: '',
            },
          });
        }
      }
    }
  }, [isChatCompletionsAPI, form, isCopyMode, isFormReady]);

  // Update field mapping when stream mode changes for chat completions API (but not in copy mode)
  useEffect(() => {
    if (isChatCompletionsAPI && !isCopyMode && isFormReady) {
      const isStreaming = streamMode === true;
      const currentFieldMapping = form.getFieldValue('field_mapping') || {};

      const expectedContent = isStreaming
        ? 'choices.0.delta.content'
        : 'choices.0.message.content';
      const expectedReasoningContent = isStreaming
        ? 'choices.0.delta.reasoning_content'
        : 'choices.0.message.reasoning_content';

      // Only call setFieldsValue when content fields need to be updated
      if (
        currentFieldMapping.content !== expectedContent ||
        currentFieldMapping.reasoning_content !== expectedReasoningContent
      ) {
        form.setFieldsValue({
          field_mapping: {
            ...currentFieldMapping,
            content: expectedContent,
            reasoning_content: expectedReasoningContent,
          },
        });
      }
    }
  }, [streamMode, isChatCompletionsAPI, form, isCopyMode, isFormReady]);

  // Field mapping section
  const fieldMappingSection = (
    <div style={{ marginBottom: 24 }}>
      <div
        style={{
          margin: '24px 0 16px',
          fontWeight: 'bold',
          fontSize: '16px',
        }}
      >
        <Space>
          <ApiOutlined />
          <span>API Field Mapping</span>
        </Space>
      </div>

      {/* Prompt Field Path - only show for custom APIs */}
      {!isChatCompletionsAPI && (
        <Row gutter={24}>
          <Col span={24}>
            <Form.Item
              name={['field_mapping', 'prompt']}
              label={
                <span>
                  Prompt Field Path
                  <Tooltip title='Enter the key in the request payload that contains the prompt (required for statistical metrics)'>
                    <InfoCircleOutlined style={{ marginLeft: 5 }} />
                  </Tooltip>
                </span>
              }
              rules={[
                {
                  required: !isChatCompletionsAPI,
                  message: 'Please enter prompt field',
                },
              ]}
            >
              <Input placeholder='e.g. query, prompt, input' />
            </Form.Item>
          </Col>
        </Row>
      )}

      {streamMode ? (
        // Streaming mode configuration
        <>
          {/* Stream Data Configuration */}
          <div style={{ marginBottom: 24 }}>
            <div
              style={{
                margin: '16px 0 12px',
                fontWeight: 'bold',
                fontSize: '14px',
              }}
            >
              Stream Data Configuration
            </div>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  name={['field_mapping', 'stream_prefix']}
                  label={
                    <span>
                      Stream Prefix
                      <Tooltip title='Prefix for each streaming data line'>
                        <InfoCircleOutlined style={{ marginLeft: 5 }} />
                      </Tooltip>
                    </span>
                  }
                >
                  <Input placeholder='e.g. data:' />
                </Form.Item>
              </Col>

              <Col span={12}>
                <Form.Item
                  name={['field_mapping', 'data_format']}
                  label={
                    <span>
                      Data Format
                      <Tooltip title='Format of data after removing stream prefix'>
                        <InfoCircleOutlined style={{ marginLeft: 5 }} />
                      </Tooltip>
                    </span>
                  }
                  rules={[
                    {
                      required: true,
                      message: 'Please select data format',
                    },
                  ]}
                >
                  <Select placeholder='Select data format'>
                    <Select.Option value='json'>JSON</Select.Option>
                    <Select.Option value='non-json'>Non-JSON</Select.Option>
                  </Select>
                </Form.Item>
              </Col>
            </Row>

            {/* Content Field Configuration - only show when data format is JSON */}
            <Form.Item noStyle shouldUpdate>
              {({ getFieldValue }) => {
                const dataFormat =
                  getFieldValue(['field_mapping', 'data_format']) || 'json';
                return (
                  dataFormat === 'json' && (
                    <Row gutter={24}>
                      <Col span={12}>
                        <Form.Item
                          name={['field_mapping', 'content']}
                          label={
                            <span>
                              Content Field Path
                              <Tooltip title='The mapping path of the model output field in JSON format, separated by dots (e.g. choices.0.delta.content -> response_iter_lines["choices"][0]["delta"]["content"]'>
                                <InfoCircleOutlined style={{ marginLeft: 5 }} />
                              </Tooltip>
                            </span>
                          }
                          rules={[
                            {
                              required: dataFormat === 'json',
                              message: 'Please enter content field path',
                            },
                          ]}
                        >
                          <Input placeholder='e.g. choices.0.delta.content' />
                        </Form.Item>
                      </Col>

                      <Col span={12}>
                        <Form.Item
                          name={['field_mapping', 'reasoning_content']}
                          label={
                            <span>
                              Reasoning Content Path
                              <Tooltip title='The mapping path of the reasoning content field in JSON format, separated by dots (optional)'>
                                <InfoCircleOutlined style={{ marginLeft: 5 }} />
                              </Tooltip>
                            </span>
                          }
                        >
                          <Input placeholder='e.g. choices.0.delta.reasoning_content' />
                        </Form.Item>
                      </Col>
                    </Row>
                  )
                );
              }}
            </Form.Item>
          </div>

          {/* End Condition Configuration */}
          <div style={{ marginBottom: 24 }}>
            <div
              style={{
                margin: '16px 0 12px',
                fontWeight: 'bold',
                fontSize: '14px',
              }}
            >
              End Condition Configuration
            </div>

            <Row gutter={16}>
              <Col span={8}>
                <Form.Item
                  name={['field_mapping', 'end_prefix']}
                  label={
                    <span>
                      End Prefix
                      <Tooltip title='Prefix for end lines (e.g. "data:", "event:")'>
                        <InfoCircleOutlined style={{ marginLeft: 5 }} />
                      </Tooltip>
                    </span>
                  }
                >
                  <Input placeholder='e.g. data:' />
                </Form.Item>
              </Col>

              <Col span={8}>
                <Form.Item
                  name={['field_mapping', 'stop_flag']}
                  label={
                    <span>
                      Stop Flag
                      <Tooltip title='Text that indicates stream end (e.g. [DONE], done, complete)'>
                        <InfoCircleOutlined style={{ marginLeft: 5 }} />
                      </Tooltip>
                    </span>
                  }
                  rules={[
                    {
                      required: true,
                      message: 'Please enter stop flag',
                    },
                  ]}
                >
                  <Input placeholder='e.g. [DONE]' />
                </Form.Item>
              </Col>

              <Col span={8}>
                <Form.Item
                  name={['field_mapping', 'end_condition']}
                  label={
                    <span>
                      End Field Path
                      <Tooltip title='The mapping path of the end flag in JSON format, separated by dots (optional)'>
                        <InfoCircleOutlined style={{ marginLeft: 5 }} />
                      </Tooltip>
                    </span>
                  }
                >
                  <Input placeholder='e.g. choices.0.finish_reason' />
                </Form.Item>
              </Col>
            </Row>
          </div>
        </>
      ) : (
        // Non-streaming mode configuration
        <Row gutter={24}>
          <Col span={12}>
            <Form.Item
              name={['field_mapping', 'content']}
              label={
                <span>
                  Content Field Path
                  <Tooltip title='Dot-separated path to content field in response (e.g. choices.0.message.content)'>
                    <InfoCircleOutlined style={{ marginLeft: 5 }} />
                  </Tooltip>
                </span>
              }
              rules={[
                {
                  required: true,
                  message: 'Please enter content field path',
                },
              ]}
            >
              <Input placeholder='e.g. choices.0.message.content' />
            </Form.Item>
          </Col>

          <Col span={12}>
            <Form.Item
              name={['field_mapping', 'reasoning_content']}
              label={
                <span>
                  Reasoning Content Path
                  <Tooltip title='Dot-separated path to reasoning content field (optional)'>
                    <InfoCircleOutlined style={{ marginLeft: 5 }} />
                  </Tooltip>
                </span>
              }
            >
              <Input placeholder='e.g. choices.0.message.reasoning_content' />
            </Form.Item>
          </Col>
        </Row>
      )}
    </div>
  );

  // create advanced settings panel content
  const advancedPanelContent = (
    <>
      {/* Method configuration */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 8 }}>
          <span>Method</span>
        </div>
        <Input value='POST' disabled style={{ width: '180px' }} />
      </div>

      {/* Header configuration */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 8 }}>
          <Space>
            <span>Headers</span>
            <Tooltip title='Note whether the Authorization needs to have the Bearer prefix'>
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
                        placeholder={isAuth ? 'API Key' : 'Header Value'}
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
                Add Header
              </Button>
            </>
          )}
        </Form.List>
      </div>

      {/* Cookies */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 8, fontWeight: 500 }}>
          <Space>
            <span style={{ fontWeight: 'bold' }}>Cookies</span>
            <Tooltip title='Request cookies for authentication'>
              <InfoCircleOutlined />
            </Tooltip>
          </Space>
        </div>
        <Form.List name='cookies'>
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => {
                return (
                  <Space key={key} style={{ display: 'flex', marginBottom: 8 }}>
                    <Form.Item
                      {...restField}
                      name={[name, 'key']}
                      style={{ flex: 1 }}
                    >
                      <Input placeholder='Cookie Key (e.g. token, uaa_token)' />
                    </Form.Item>
                    <Form.Item
                      {...restField}
                      name={[name, 'value']}
                      style={{ flex: 1 }}
                    >
                      <Input placeholder='Cookie Value' />
                    </Form.Item>
                    <MinusCircleOutlined
                      onClick={() => remove(name)}
                      style={{ marginTop: 8 }}
                    />
                  </Space>
                );
              })}
              <Button
                type='dashed'
                onClick={() => add()}
                block
                icon={<PlusOutlined />}
              >
                Add Cookie
              </Button>
            </>
          )}
        </Form.List>
      </div>

      {/* Client certificate upload */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 8, fontWeight: 500 }}>
          <Space>
            <span style={{ fontWeight: 'bold' }}>Client Certificate</span>
            <Tooltip title='Certificate files required for HTTPS mutual authentication'>
              <InfoCircleOutlined />
            </Tooltip>
          </Space>
        </div>
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
      </div>
    </>
  );

  // define collapse panel items
  const collapseItems = [
    {
      key: 'advanced',
      label: (
        <Space style={{ marginTop: 3 }}>
          <span
            style={{
              fontSize: 16,
              marginTop: '-2px',
              display: 'inline-block',
            }}
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
        layout='vertical'
        initialValues={{
          headers: [
            { key: 'Content-Type', value: 'application/json', fixed: true },
            { key: 'Authorization', value: '', fixed: false },
          ],
          cookies: [],
          stream_mode: true,
          spawn_rate: 1,
          concurrent_users: 1,
          chat_type: 0,
          temp_task_id: tempTaskId,
          target_host: '',
          api_path: '/v1/chat/completions',
          duration: '',
          model: '',
          field_mapping: {
            prompt: '',
            stream_prefix: 'data:',
            data_format: 'json',
            content: 'choices.0.delta.content',
            reasoning_content: 'choices.0.delta.reasoning_content',
            end_prefix: 'data:',
            stop_flag: '[DONE]',
            end_condition: '',
          },
        }}
        onFinish={handleSubmit}
        onValuesChange={changedValues => {
          if ('api_path' in changedValues) {
            setApiPath(changedValues.api_path);
          }
          if ('stream_mode' in changedValues) {
            setStreamMode(changedValues.stream_mode);
          }
          if ('concurrent_users' in changedValues) {
            setConcurrentUsers(changedValues.concurrent_users);
          }

          // Check form validity for test button whenever any field changes
          setTimeout(() => {
            const isValid = checkFormValidForTest();
            setIsTestButtonEnabled(isValid);
          }, 0);
        }}
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
            <Form.Item
              name='api_url'
              label={
                <span>
                  API URL
                  <Tooltip title='API endpoint for testing.'>
                    <InfoCircleOutlined style={{ marginLeft: 5 }} />
                  </Tooltip>
                </span>
              }
              required
            >
              <div style={{ display: 'flex', width: '100%' }}>
                <Form.Item
                  name='target_host'
                  noStyle
                  rules={[{ required: true, message: 'Please enter API URL' }]}
                >
                  <Input
                    style={{ width: '70%' }}
                    placeholder='https://your-api-domain.com'
                  />
                </Form.Item>
                <Form.Item
                  name='api_path'
                  noStyle
                  rules={[
                    {
                      required: true,
                      message: 'Please enter API path',
                    },
                  ]}
                >
                  <Input
                    style={{ width: '30%' }}
                    placeholder='/v1/chat/completions'
                  />
                </Form.Item>
              </div>
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

        {/* Request Payload - only show for custom APIs */}
        {!isChatCompletionsAPI && (
          <Row gutter={24} style={{ marginBottom: 16 }}>
            <Col span={24}>
              <Form.Item
                name='request_payload'
                label={
                  <span>
                    Request Payload
                    <Tooltip title='JSON payload to send to the custom API endpoint. To quickly test the connectivity, please use a simple prompt. The default dataset will be used in the formal load test.'>
                      <InfoCircleOutlined style={{ marginLeft: 5 }} />
                    </Tooltip>
                  </span>
                }
                rules={[
                  {
                    required: !isChatCompletionsAPI,
                    message: 'Please enter request payload',
                  },
                  {
                    validator: (_, value) => {
                      // Skip validation if field is not required (chat completions API)
                      if (isChatCompletionsAPI) return Promise.resolve();
                      if (!value) return Promise.resolve();
                      try {
                        JSON.parse(value);
                        return Promise.resolve();
                      } catch (e) {
                        return Promise.reject(
                          new Error('Please enter valid JSON')
                        );
                      }
                    },
                  },
                ]}
              >
                <TextArea
                  rows={4}
                  placeholder='e.g. {"query": "What is LLM?", "imgs": [], "model": "gpt-4o"}'
                />
              </Form.Item>
            </Col>
          </Row>
        )}

        {/* Model Name, Chat Type (if chat completions), and Output Mode */}
        <Row gutter={24}>
          <Col span={isChatCompletionsAPI ? 8 : 12}>
            <Form.Item
              name='model'
              label={
                <span>
                  Model Name
                  <Tooltip title='Please enter an available model name'>
                    <InfoCircleOutlined style={{ marginLeft: 5 }} />
                  </Tooltip>
                </span>
              }
              rules={[{ required: true, message: 'Please enter model name' }]}
            >
              <Input placeholder='e.g. internlm3-latest' />
            </Form.Item>
          </Col>

          {isChatCompletionsAPI && (
            <Col span={8}>
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
              >
                <Select placeholder='Select chat type'>
                  <Select.Option value={0}>Text-Only</Select.Option>
                  <Select.Option value={1}>Image-Text</Select.Option>
                </Select>
              </Form.Item>
            </Col>
          )}

          <Col span={isChatCompletionsAPI ? 8 : 12}>
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
            >
              <Select placeholder='Select output mode'>
                <Select.Option value>Stream</Select.Option>
                <Select.Option value={false}>Non-stream</Select.Option>
              </Select>
            </Form.Item>
          </Col>
        </Row>

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

        {/* Field Mapping Section - always show */}
        {fieldMappingSection}

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

        <Form.Item className='form-actions'>
          <Space>
            <Button
              icon={<BugOutlined />}
              onClick={handleTestAPI}
              loading={testing}
              disabled={!isFormValidForTest()}
              className={isFormValidForTest() ? 'test-button-active' : ''}
            >
              Test It
            </Button>
            <Button onClick={onCancel}>Cancel</Button>
            <Button type='primary' htmlType='submit' loading={submitting}>
              {submitting ? 'Submitting...' : isCopyMode ? 'Create' : 'Create'}
            </Button>
          </Space>
        </Form.Item>
      </Form>

      {/* Test Result Modal */}
      <Modal
        title={
          <Space>
            <BugOutlined />
            <span>API Test</span>
          </Space>
        }
        open={testModalVisible}
        onCancel={() => setTestModalVisible(false)}
        footer={[
          <Button
            key='close'
            size='large'
            onClick={() => setTestModalVisible(false)}
          >
            Close
          </Button>,
        ]}
        width={800}
        centered={false}
        destroyOnHidden
        mask={false}
        maskClosable={false}
        keyboard={false}
        zIndex={1002}
        getContainer={false}
        style={{
          position: 'fixed',
          right: '20px',
          top: '50%',
          transform: 'translateY(-50%)',
          margin: 0,
          paddingBottom: 0,
        }}
        styles={{
          body: {
            padding: '20px',
            maxHeight: 'calc(100vh - 160px)',
            overflow: 'auto',
          },
          content: {
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.1)',
            maxHeight: 'calc(100vh - 120px)',
            margin: 0,
          },
          wrapper: {
            overflow: 'visible',
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            pointerEvents: 'none',
          },
        }}
        wrapClassName='api-test-modal-right-side'
      >
        {testResult && (
          <div
            style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            {/* Status Section */}
            <div
              style={{
                padding: '16px',
                backgroundColor: token.colorBgContainer,
                borderRadius: '8px',
                border: `1px solid ${token.colorBorder}`,
                boxShadow: token.boxShadowTertiary,
              }}
            >
              <Row gutter={24} align='middle'>
                {/* Status Code */}
                {testResult.response?.status_code !== undefined && (
                  <Col>
                    <Space>
                      <Text strong style={{ fontSize: '16px' }}>
                        Status Code:
                      </Text>
                      <div
                        style={{
                          padding: '4px 12px',
                          borderRadius: '6px',
                          backgroundColor:
                            testResult.response.status_code === 200
                              ? token.colorSuccessBg
                              : token.colorErrorBg,
                          color:
                            testResult.response.status_code === 200
                              ? token.colorSuccess
                              : token.colorError,
                          fontWeight: 'bold',
                          fontSize: '14px',
                        }}
                      >
                        {testResult.response.status_code}
                      </div>
                    </Space>
                  </Col>
                )}
              </Row>

              {/* Error Message */}
              {testResult.status === 'error' && testResult.error && (
                <div style={{ marginTop: 12 }}>
                  <div
                    style={{
                      padding: '12px',
                      backgroundColor: token.colorErrorBg,
                      borderRadius: '6px',
                      border: `1px solid ${token.colorErrorBorder}`,
                    }}
                  >
                    <Text strong style={{ color: token.colorError }}>
                      Error:
                    </Text>
                    <Text style={{ color: token.colorError, marginLeft: 8 }}>
                      {testResult.error}
                    </Text>
                  </div>
                </div>
              )}
            </div>

            {/* Response Data Section */}
            {testResult.response?.data !== undefined && (
              <div
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  minHeight: 0,
                  backgroundColor: token.colorBgContainer,
                  borderRadius: '8px',
                  border: `1px solid ${token.colorBorder}`,
                  boxShadow: token.boxShadowTertiary,
                  overflow: 'hidden',
                }}
              >
                {/* Response Header */}
                <div
                  style={{
                    padding: '12px 16px',
                    backgroundColor: token.colorFillQuaternary,
                    borderBottom: `1px solid ${token.colorBorder}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <Space>
                    <Text strong style={{ fontSize: '16px' }}>
                      Response Data
                    </Text>
                    {testResult.response.is_stream &&
                      Array.isArray(testResult.response.data) && (
                        <div
                          style={{
                            padding: '2px 8px',
                            backgroundColor: token.colorPrimaryBg,
                            color: token.colorPrimary,
                            borderRadius: '4px',
                            fontSize: '12px',
                            fontWeight: 'bold',
                          }}
                        >
                          Stream ({testResult.response.data.length} chunks)
                        </div>
                      )}
                  </Space>
                </div>

                {/* Response Content */}
                <div
                  style={{
                    flex: 1,
                    overflow: 'auto',
                    padding: '16px',
                    backgroundColor: '#fafafa',
                    maxHeight: '400px', // limit max height to ensure scrolling
                    scrollbarWidth: 'thin', // Firefox
                    scrollbarColor: '#bfbfbf #f0f0f0', // Firefox
                  }}
                  className='custom-scrollbar'
                >
                  {testResult.response.is_stream &&
                  Array.isArray(testResult.response.data) ? (
                    // stream response display
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                      }}
                    >
                      {testResult.response.data.map((chunk, index) => (
                        <div
                          key={index}
                          style={{
                            padding: '8px 12px',
                            backgroundColor:
                              index % 2 === 0 ? '#ffffff' : '#f8f9fa',
                            borderRadius: '4px',
                            border: '1px solid #e8e8e8',
                            fontSize: '12px',
                            fontFamily:
                              'Monaco, Consolas, "Courier New", monospace',
                            wordBreak: 'break-all',
                            whiteSpace: 'pre-wrap',
                            lineHeight: '1.4',
                          }}
                        >
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'flex-start',
                            }}
                          >
                            <span
                              style={{
                                color: '#666',
                                marginRight: 12,
                                fontSize: '11px',
                                fontWeight: 'bold',
                                minWidth: '40px',
                                opacity: 0.7,
                              }}
                            >
                              [{String(index + 1).padStart(3, '0')}]
                            </span>
                            <div style={{ flex: 1 }}>{chunk}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    // non-stream response display
                    <div
                      style={{
                        backgroundColor: '#ffffff',
                        borderRadius: '6px',
                        border: '1px solid #e8e8e8',
                        overflow: 'hidden',
                      }}
                    >
                      <pre
                        className='custom-scrollbar'
                        style={{
                          margin: 0,
                          padding: '16px',
                          whiteSpace: 'pre-wrap',
                          fontSize: '12px',
                          fontFamily:
                            'Monaco, Consolas, "Courier New", monospace',
                          lineHeight: '1.5',
                          maxHeight: '300px',
                          overflow: 'auto',
                          backgroundColor: 'transparent',
                        }}
                      >
                        {typeof testResult.response.data === 'string'
                          ? testResult.response.data
                          : JSON.stringify(testResult.response.data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </Card>
  );
};

const CreateJobForm: React.FC<CreateJobFormProps> = props => (
  <CreateJobFormContent {...props} />
);

export default CreateJobForm;
