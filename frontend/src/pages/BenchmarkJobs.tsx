/**
 * @file BenchmarkJobs.tsx
 * @description Benchmark jobs page component
 * @author Charm
 * @copyright 2025
 * */
import {
  ClockCircleOutlined,
  CopyOutlined,
  ExclamationCircleOutlined,
  ExperimentOutlined,
  MoreOutlined,
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
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import 'dayjs/locale/en';
import relativeTime from 'dayjs/plugin/relativeTime';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import React, { useCallback, useMemo, useState } from 'react';

import CreateJobForm from '../components/CreateJobForm';
import { useBenchmarkJobs } from '../hooks/useBenchmarkJobs';
import { BenchmarkJob } from '../types/benchmark';

// Configure dayjs plugins
dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(relativeTime);
dayjs.locale('en');

const { Search } = Input;
const { Text, Title } = Typography;

// Task status mapping table
const statusMap = {
  created: { color: 'default', text: 'Created' },
  running: { color: 'processing', text: 'Running' },
  completed: { color: 'success', text: 'Completed' },
  stopping: { color: 'gold', text: 'Stopping' },
  stopped: { color: 'volcano', text: 'Stopped' },
  locked: { color: 'warning', text: 'Waiting' },
  failed: { color: 'error', text: 'Failed' },
};

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

  // Function to copy text to the clipboard
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(
      () => messageApi.success('Copied'),
      () => messageApi.error('Copy failed, please copy manually')
    );
  };

  // Function to handle copying a job
  const handleCopyJob = useCallback((job: BenchmarkJob) => {
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

    if (jobToCopyData.headers) {
      try {
        const headerObject =
          typeof jobToCopyData.headers === 'string'
            ? JSON.parse(jobToCopyData.headers)
            : jobToCopyData.headers;
        jobToCopyData.headers = JSON.parse(JSON.stringify(headerObject));
      } catch (e) {
        console.error('Failed to parse headers when copying task:', e);
        jobToCopyData.headers = [];
      }
    }
    setTaskToCopy(jobToCopyData);
    setIsModalVisible(true);
  }, []);

  // Confirm stopping a job
  const showStopConfirm = (jobId: string, jobName?: string) => {
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
  };

  // Table column definitions
  const columns: ColumnsType<BenchmarkJob> = useMemo(
    () => [
      {
        title: 'Task ID',
        dataIndex: 'id',
        key: 'id',
        width: 180,
        render: (id: string) => (
          <Space>
            <Text ellipsis style={{ maxWidth: '150px' }}>
              {id}
            </Text>
            <Tooltip title='Copy'>
              <Button
                type='text'
                icon={<CopyOutlined />}
                size='small'
                onClick={e => {
                  e.stopPropagation();
                  copyToClipboard(id);
                }}
              />
            </Tooltip>
          </Space>
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
        ellipsis: true,
        width: 180,
        render: (target_host: string) => (
          <Space>
            <Text ellipsis style={{ maxWidth: '150px' }}>
              {target_host}
            </Text>
            <Tooltip title='Copy'>
              <Button
                type='text'
                icon={<CopyOutlined />}
                size='small'
                onClick={e => {
                  e.stopPropagation();
                  copyToClipboard(target_host);
                }}
              />
            </Tooltip>
          </Space>
        ),
      },
      {
        title: 'Model Name',
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
        filters: Object.entries(statusMap).map(([key, value]) => ({
          text: value.text,
          value: key,
        })),
        onFilter: (value, record) => record.status?.toLowerCase() === value,
        render: (status: string) => {
          const statusInfo = statusMap[
            status?.toLowerCase() as keyof typeof statusMap
          ] || { color: 'default', text: status || 'Unknown' };
          return <Tag color={statusInfo.color as any}>{statusInfo.text}</Tag>;
        },
      },
      {
        title: 'Created Time',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 120,
        sorter: (a, b) =>
          dayjs(a.created_at).valueOf() - dayjs(b.created_at).valueOf(),
        render: (time: string) =>
          time ? dayjs(time).format('YYYY-MM-DD HH:mm:ss') : '-',
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
                  style={{ width: '100%', textAlign: 'left' }}
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
                  style={{ width: '100%', textAlign: 'left' }}
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
    [handleCopyJob]
  );

  // Create job handler
  const handleCreateJob = async (values: any) => {
    const success = await createJob(values);
    if (success) {
      setIsModalVisible(false);
      setTaskToCopy(null);
    }
  };

  // Table change handler for pagination and filters
  const handleTableChange = (newPagination: any, filters: any) => {
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
  };

  // Render last refresh time
  const renderLastRefreshTime = () => {
    if (!lastRefreshTime) return null;
    return (
      <Tooltip
        title={`Last refresh: ${dayjs(lastRefreshTime).format('YYYY-MM-DD HH:mm:ss')}`}
      >
        <span style={{ fontSize: '12px', color: '#888', marginRight: '10px' }}>
          <ClockCircleOutlined style={{ marginRight: '4px' }} />
          Refreshed {dayjs(lastRefreshTime).fromNow()}
        </span>
      </Tooltip>
    );
  };

  // Main render
  return (
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: '24px' }}>
        <Title level={3}>
          <ExperimentOutlined /> Test Tasks
        </Title>
        <Text type='secondary'>Test task management and monitoring</Text>
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '24px',
        }}
      >
        <Space>
          <Button
            type='primary'
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
            style={{ width: 300 }}
            allowClear
            enterButton
          />
          <Button
            icon={<ReloadOutlined spin={refreshing} />}
            onClick={() => manualRefresh()}
            disabled={loading || refreshing}
          >
            Refresh
          </Button>
        </Space>
      </div>

      <style>{`
                .highlight-row { background-color: rgba(24, 144, 255, 0.05); }
                .ant-table-row:hover { cursor: pointer; }
            `}</style>

      <Table<BenchmarkJob>
        columns={columns}
        rowKey='id'
        dataSource={filteredJobs}
        loading={loading}
        pagination={pagination}
        onChange={handleTableChange}
        scroll={{ x: 1100 }}
        rowClassName={record =>
          record.status?.toLowerCase() === 'running' ? 'highlight-row' : ''
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
        onCancel={() => {
          setIsModalVisible(false);
          setTaskToCopy(null);
        }}
        footer={null}
        width={800}
        destroyOnHidden
      >
        <CreateJobForm
          onSubmit={handleCreateJob}
          onCancel={() => {
            setIsModalVisible(false);
            setTaskToCopy(null);
          }}
          loading={loading}
          initialData={taskToCopy}
        />
      </Modal>
    </div>
  );
};

export default BenchmarkJobs;
