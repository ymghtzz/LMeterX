/**
 * @file BenchmarkJobs.tsx
 * @description Benchmark jobs page component
 * @author Charm
 * @copyright 2025
 * */
import {
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  ExperimentOutlined,
  MoreOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import {
  App,
  Badge,
  Button,
  Dropdown,
  Empty,
  Input,
  Modal,
  Space,
  Table,
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useCallback, useMemo, useState } from 'react';

import CreateJobForm from '../components/CreateJobForm';
import CopyButton from '../components/ui/CopyButton';
import PageHeader from '../components/ui/PageHeader';
import StatusTag from '../components/ui/StatusTag';
import { useBenchmarkJobs } from '../hooks/useBenchmarkJobs';
import { BenchmarkJob } from '../types/benchmark';
import { TASK_STATUS_MAP, UI_CONFIG } from '../utils/constants';
import { deepClone, safeJsonParse, safeJsonStringify } from '../utils/data';
import { formatDate, getRelativeTime, getTimestamp } from '../utils/date';

const { Search } = Input;
const { Text } = Typography;

const BenchmarkJobs: React.FC = () => {
  // State managed by the component
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [taskToCopy, setTaskToCopy] = useState<Partial<BenchmarkJob> | null>(
    null
  );

  // Get message instance from App context
  const { message: messageApi, modal } = App.useApp();

  // Using the custom hook to manage job-related logic
  const {
    filteredJobs,
    pagination,
    setPagination,
    loading,
    refreshing,
    error,
    lastRefreshTime,
    createJob,
    stopJob,
    manualRefresh,
    setSearchText,
    setStatusFilter,
  } = useBenchmarkJobs(messageApi);

  /**
   * Handle copying a job template
   */
  const handleCopyJob = useCallback(
    (job: BenchmarkJob) => {
      const copiedName = job.name
        ? `${job.name} (Copy)`
        : `Copy Task ${job.id.substring(0, 8)}`;

      const jobToCopyData: Partial<BenchmarkJob> = {
        ...job,
        name: copiedName,
        id: undefined,
        status: undefined,
        created_at: undefined,
        updated_at: undefined,
      };

      // Handle headers using safe JSON parsing
      if (jobToCopyData.headers) {
        const headerObject =
          typeof jobToCopyData.headers === 'string'
            ? safeJsonParse(jobToCopyData.headers, [])
            : jobToCopyData.headers;
        jobToCopyData.headers = deepClone(headerObject) || [];
      }

      // Handle request_payload - preserve for custom APIs
      if (jobToCopyData.request_payload) {
        jobToCopyData.request_payload =
          typeof jobToCopyData.request_payload === 'string'
            ? jobToCopyData.request_payload
            : safeJsonStringify(jobToCopyData.request_payload);
      }

      // Handle field_mapping - preserve configuration with proper structure
      if (jobToCopyData.field_mapping) {
        const fieldMappingObject =
          typeof jobToCopyData.field_mapping === 'string'
            ? safeJsonParse(jobToCopyData.field_mapping, {})
            : jobToCopyData.field_mapping;

        // Ensure all required field_mapping properties exist
        const completeFieldMapping = {
          prompt: '',
          stream_prefix: '',
          data_format: 'json',
          content: '',
          reasoning_content: '',
          end_prefix: '',
          stop_flag: '',
          end_condition: '',
          ...fieldMappingObject, // Override with actual values
        };

        jobToCopyData.field_mapping = deepClone(completeFieldMapping) || {};
      } else {
        // Initialize empty field_mapping structure if not present
        jobToCopyData.field_mapping = {
          prompt: '',
          stream_prefix: '',
          data_format: 'json',
          content: '',
          reasoning_content: '',
          end_prefix: '',
          stop_flag: '',
          end_condition: '',
        };
      }

      setTaskToCopy(jobToCopyData);
      setIsModalVisible(true);

      // Show toast notification about re-entering sensitive information
      messageApi.warning({
        content:
          'Please note: Authentication credentials and uploaded files need to be re-entered.',
        duration: 5,
      });
    },
    [messageApi]
  );

  /**
   * Show confirmation dialog for stopping a job
   */
  const showStopConfirm = useCallback(
    (jobId: string, jobName?: string) => {
      modal.confirm({
        title: 'Are you sure you want to stop this task?',
        icon: <ExclamationCircleOutlined />,
        content: (
          <span>
            After stopping task <Text code>{jobName || jobId}</Text>, the task
            cannot be resumed.
          </span>
        ),
        okText: 'Confirm Stop',
        okType: 'danger',
        cancelText: 'Cancel',
        onOk: () => stopJob(jobId),
      });
    },
    [modal, stopJob]
  );

  /**
   * Table column definitions
   */
  const columns: ColumnsType<BenchmarkJob> = useMemo(
    () => [
      {
        title: 'Task ID',
        dataIndex: 'id',
        key: 'id',
        width: 180,
        render: (id: string) => (
          <div className='table-cell-with-copy'>
            <Tooltip title={id} placement='topLeft'>
              <Text className='table-cell-text table-ellipsis-150'>{id}</Text>
            </Tooltip>
            <div className='table-cell-action'>
              <CopyButton text={id} />
            </div>
          </div>
        ),
      },
      {
        title: 'Task Name',
        dataIndex: 'name',
        key: 'name',
        ellipsis: true,
        width: 150,
      },
      {
        title: 'Target URL',
        dataIndex: 'target_host',
        key: 'target_host',
        width: 280,
        render: (target_host: string, record: BenchmarkJob) => {
          const apiPath = record.api_path || '/chat/completions';
          const fullUrl = target_host + apiPath;
          return (
            <div className='table-cell-with-copy'>
              <Tooltip title={fullUrl} placement='topLeft'>
                <Text className='table-cell-text table-ellipsis-220'>
                  {fullUrl}
                </Text>
              </Tooltip>
              <div className='table-cell-action'>
                <CopyButton text={fullUrl} />
              </div>
            </div>
          );
        },
      },
      {
        title: 'Model',
        dataIndex: 'model',
        key: 'model',
        ellipsis: true,
        width: 150,
      },
      {
        title: 'Concurrent Users',
        dataIndex: 'concurrent_users',
        key: 'concurrent_users',
        width: 120,
      },
      {
        title: 'Duration (s)',
        dataIndex: 'duration',
        key: 'duration',
        width: 120,
      },
      {
        title: 'Status',
        dataIndex: 'status',
        key: 'status',
        width: 120,
        filters: Object.entries(TASK_STATUS_MAP).map(([key, value]) => ({
          text: value.text,
          value: key,
        })),
        onFilter: (value, record) => record.status?.toLowerCase() === value,
        render: (status: string) => <StatusTag status={status} />,
      },
      {
        title: 'Created Time',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 120,
        sorter: (a, b) =>
          getTimestamp(a.created_at) - getTimestamp(b.created_at),
        render: (time: string) => formatDate(time),
      },
      {
        title: 'Actions',
        key: 'action',
        width: 150,
        fixed: 'right',
        render: (_, record) => {
          const menuItems = [
            {
              key: 'copy',
              label: (
                <Button
                  type='text'
                  size='small'
                  className='table-action-button'
                  onClick={e => {
                    e.stopPropagation();
                    handleCopyJob(record);
                  }}
                >
                  Copy Template
                </Button>
              ),
            },
          ];

          if (['running', 'queued'].includes(record.status?.toLowerCase())) {
            menuItems.push({
              key: 'stop',
              label: (
                <Button
                  type='text'
                  danger
                  size='small'
                  className='table-action-button'
                  onClick={e => {
                    e.stopPropagation();
                    showStopConfirm(record.id, record.name);
                  }}
                >
                  Stop
                </Button>
              ),
            });
          }

          return (
            <Space size='small' wrap>
              <Button
                size='small'
                type='primary'
                onClick={e => {
                  e.stopPropagation();
                  window.open(`/results/${record.id}`, '_blank');
                }}
              >
                Results
              </Button>
              <Button
                size='small'
                type='primary'
                onClick={e => {
                  e.stopPropagation();
                  window.open(`/logs/task/${record.id}`, '_blank');
                }}
              >
                Logs
              </Button>
              {menuItems.length > 0 && (
                <Dropdown menu={{ items: menuItems }} trigger={['click']}>
                  <Button
                    type='text'
                    icon={<MoreOutlined />}
                    onClick={e => e.stopPropagation()}
                  />
                </Dropdown>
              )}
            </Space>
          );
        },
      },
    ],
    [handleCopyJob, showStopConfirm]
  );

  /**
   * Handle job creation
   */
  const handleCreateJob = useCallback(
    async (values: any) => {
      const success = await createJob(values);
      if (success) {
        setIsModalVisible(false);
        setTaskToCopy(null);
      }
    },
    [createJob]
  );

  /**
   * Handle table changes (pagination and filters)
   */
  const handleTableChange = useCallback(
    (newPagination: any, filters: any) => {
      // Check if filters have changed (not just pagination)
      const isFilterChange =
        filters && Object.keys(filters).some(key => filters[key]);

      setPagination({
        current: isFilterChange ? 1 : newPagination.current, // Reset to page 1 if filters changed
        pageSize: newPagination.pageSize,
        total: newPagination.total,
      });

      // Handle status filter change from table
      if (filters.status) {
        setStatusFilter(filters.status.join(','));
      } else {
        setStatusFilter('');
      }
    },
    [setPagination, setStatusFilter]
  );

  /**
   * Render last refresh time indicator
   */
  const renderLastRefreshTime = useCallback(() => {
    if (!lastRefreshTime) return null;

    return (
      <Tooltip title={`Last refresh: ${formatDate(lastRefreshTime)}`}>
        <span className='status-refresh'>
          <ClockCircleOutlined className='mr-4' />
          Refreshed {getRelativeTime(lastRefreshTime)}
        </span>
      </Tooltip>
    );
  }, [lastRefreshTime]);

  /**
   * Handle modal cancel
   */
  const handleModalCancel = useCallback(() => {
    setIsModalVisible(false);
    setTaskToCopy(null);
  }, []);

  return (
    <div className='page-container'>
      <PageHeader
        title=' Test Tasks'
        icon={<ExperimentOutlined />}
        description='Test task management and monitoring'
      />

      <div className='flex justify-between align-center mb-24'>
        <Space>
          <Button
            type='primary'
            icon={<PlusOutlined />}
            onClick={() => setIsModalVisible(true)}
            disabled={loading}
          >
            Create Task
          </Button>
          {refreshing && <Badge status='processing' />}
        </Space>
        <Space wrap>
          {renderLastRefreshTime()}
          <Search
            placeholder='Search task name, model or ID'
            onSearch={setSearchText}
            onChange={e => {
              if (!e.target.value) {
                setSearchText('');
              }
            }}
            className='w-300'
            allowClear
            enterButton
          />
          <Button
            icon={<ReloadOutlined spin={refreshing} />}
            onClick={manualRefresh}
            disabled={loading || refreshing}
          >
            Refresh
          </Button>
        </Space>
      </div>

      <style>{`
        .table-highlight-row { background-color: rgba(24, 144, 255, 0.05); }
        .ant-table-row:hover { cursor: pointer; }
      `}</style>

      <Table<BenchmarkJob>
        columns={columns}
        rowKey='id'
        dataSource={filteredJobs}
        loading={loading}
        pagination={pagination}
        onChange={handleTableChange}
        scroll={{ x: UI_CONFIG.TABLE_SCROLL_X }}
        rowClassName={record =>
          record.status?.toLowerCase() === 'running'
            ? 'table-highlight-row'
            : ''
        }
        locale={{
          emptyText: error ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={<Text type='danger'>{error}</Text>}
            />
          ) : (
            <Empty description='No data' />
          ),
        }}
      />

      <Modal
        title={taskToCopy ? 'Edit Task' : 'Create Task'}
        open={isModalVisible}
        onCancel={handleModalCancel}
        footer={null}
        width={800}
        destroyOnHidden
      >
        <CreateJobForm
          onSubmit={handleCreateJob}
          onCancel={handleModalCancel}
          loading={loading}
          initialData={taskToCopy}
        />
      </Modal>
    </div>
  );
};

export default BenchmarkJobs;
