/**
 * @file ResultComparison.tsx
 * @description Result comparison page
 * @author Charm
 * @copyright 2025
 * */
import {
  BarChartOutlined,
  ClearOutlined,
  DownloadOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import { Column } from '@ant-design/plots';
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Empty,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import html2canvas from 'html2canvas';
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { api } from '../api/apiClient';
import { LoadingSpinner } from '../components/ui/LoadingState';
import { PageHeader } from '../components/ui/PageHeader';
import { createFileTimestamp, formatDate } from '../utils/date';

const { Title, Text } = Typography;
const { Option } = Select;

interface ModelTaskInfo {
  model_name: string;
  concurrent_users: number;
  task_id: string;
  task_name: string;
  created_at: string;
}

interface ComparisonMetrics {
  task_id: string;
  model_name: string;
  concurrent_users: number;
  task_name: string;
  ttft: number;
  total_tps: number;
  completion_tps: number;
  avg_total_tpr: number;
  avg_completion_tpr: number;
  avg_response_time: number;
  rps: number;
}

interface SelectedTask {
  task_id: string;
  model_name: string;
  concurrent_users: number;
  task_name: string;
  created_at: string;
}

const ResultComparison: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [availableTasks, setAvailableTasks] = useState<ModelTaskInfo[]>([]);
  const [selectedTasks, setSelectedTasks] = useState<SelectedTask[]>([]);
  const [comparisonResults, setComparisonResults] = useState<
    ComparisonMetrics[]
  >([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [selectedModel, setSelectedModel] = useState<string | undefined>(
    undefined
  );
  const [tempSelectedTasks, setTempSelectedTasks] = useState<string[]>([]);
  const [messageApi, contextHolder] = message.useMessage();

  // Refs for download functionality
  const modelInfoRef = useRef<HTMLDivElement | null>(null);
  const comparisonResultsRef = useRef<HTMLDivElement | null>(null);

  // Fetch available tasks for comparison
  const fetchAvailableTasks = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get<{
        data: ModelTaskInfo[];
        status: string;
        error?: string;
      }>('/tasks/comparison/available');

      if (response.data.status === 'success') {
        setAvailableTasks(response.data.data);
      } else {
        messageApi.error(
          response.data.error || 'Failed to fetch available tasks'
        );
      }
    } catch (error) {
      messageApi.error('Failed to fetch available tasks');
    } finally {
      setLoading(false);
    }
  }, [messageApi]);

  // Compare selected tasks
  const compareResult = useCallback(async () => {
    if (tempSelectedTasks.length < 2) {
      messageApi.warning('Please select at least 2 tasks for comparison');
      return;
    }

    if (tempSelectedTasks.length > 10) {
      messageApi.warning('Maximum 10 tasks can be selected for comparison');
      return;
    }

    setComparing(true);
    try {
      const response = await api.post<{
        data: ComparisonMetrics[];
        status: string;
        error?: string;
      }>('/tasks/comparison', {
        selected_tasks: tempSelectedTasks,
      });

      if (response.data.status === 'success') {
        setComparisonResults(response.data.data);

        // Update selected tasks with the ones from tempSelectedTasks
        const selectedTasksData = availableTasks
          .filter(task => tempSelectedTasks.includes(task.task_id))
          .map(task => ({
            task_id: task.task_id,
            model_name: task.model_name,
            concurrent_users: task.concurrent_users,
            task_name: task.task_name,
            created_at: task.created_at,
          }));

        setSelectedTasks(selectedTasksData);
        setIsModalVisible(false);
        setTempSelectedTasks([]);
        messageApi.success('Result comparison completed');
      } else {
        messageApi.error(response.data.error || 'Failed to compare Result');
      }
    } catch (error) {
      messageApi.error('Failed to compare Result');
    } finally {
      setComparing(false);
    }
  }, [tempSelectedTasks, availableTasks, messageApi]);

  // Handle task selection in modal
  const handleTaskSelection = (taskId: string, checked: boolean) => {
    if (checked) {
      if (tempSelectedTasks.length >= 10) {
        messageApi.warning('Maximum 10 tasks can be selected for comparison');
        return;
      }
      setTempSelectedTasks([...tempSelectedTasks, taskId]);
    } else {
      setTempSelectedTasks(tempSelectedTasks.filter(id => id !== taskId));
    }
  };

  // Handle search input change
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchText(e.target.value);
  };

  // Handle search clear or search action
  const handleSearch = (value: string) => {
    if (!value.trim()) {
      // When search is cleared, refresh the available tasks
      fetchAvailableTasks();
    }
  };

  // Handle model filter change
  const handleModelFilterChange = (value: string) => {
    setSelectedModel(value || undefined);
    if (!value) {
      // When model filter is cleared, refresh the available tasks
      fetchAvailableTasks();
    }
  };

  // Clear all selected tasks
  const clearAllTasks = () => {
    Modal.confirm({
      title: 'Clear All Selected Tasks',
      icon: <ExclamationCircleOutlined />,
      content: 'Are you sure you want to clear all selected tasks?',
      onOk: () => {
        setSelectedTasks([]);
        setComparisonResults([]);
        messageApi.success('All tasks cleared');
      },
    });
  };

  // Reset modal state when opening
  const handleModalOpen = () => {
    setTempSelectedTasks([]);
    setIsModalVisible(true);
  };

  // Filter available tasks
  const filteredAvailableTasks = useMemo(() => {
    return availableTasks.filter(task => {
      const matchesSearch =
        searchText === '' ||
        task.model_name.toLowerCase().includes(searchText.toLowerCase()) ||
        task.task_name.toLowerCase().includes(searchText.toLowerCase());

      const matchesModel = !selectedModel || task.model_name === selectedModel;

      return matchesSearch && matchesModel;
    });
  }, [availableTasks, searchText, selectedModel]);

  // Get unique model names for filtering
  const uniqueModels = useMemo(() => {
    const models = [...new Set(availableTasks.map(task => task.model_name))];
    return models.sort();
  }, [availableTasks]);

  // Color mapping for models
  const modelColors = [
    '#1890ff', // Blue
    '#52c41a', // Green
    '#fa8c16', // Orange
    '#eb2f96', // Pink
    '#722ed1', // Purple
    '#13c2c2', // Cyan
    '#f5222d', // Red
    '#a0d911', // Lime
    '#fa541c', // Dark Orange
    '#2f54eb', // Dark Blue
  ];

  const getModelColor = (modelName: string) => {
    // Assign colors based on the actual order of data appearance to maintain consistency with data display order
    const allTasks = [
      ...availableTasks,
      ...selectedTasks,
      ...comparisonResults.map(result => ({
        model_name: result.model_name,
        created_at: '', // No need for specific time, only model name is needed
      })),
    ];

    // Get unique model names in order of appearance, without alphabetical sorting
    const uniqueModelsList: string[] = [];
    allTasks.forEach(task => {
      if (!uniqueModelsList.includes(task.model_name)) {
        uniqueModelsList.push(task.model_name);
      }
    });

    const index = uniqueModelsList.indexOf(modelName);
    return modelColors[index % modelColors.length];
  };

  // Table columns for available tasks in modal
  const availableTasksColumns: ColumnsType<ModelTaskInfo> = [
    {
      title: 'Select',
      key: 'select',
      width: 60,
      align: 'center',
      render: (_, record) => (
        <Checkbox
          checked={tempSelectedTasks.includes(record.task_id)}
          onChange={e => handleTaskSelection(record.task_id, e.target.checked)}
        />
      ),
    },
    {
      title: 'Task ID',
      dataIndex: 'task_id',
      key: 'task_id',
      ellipsis: true,
    },
    {
      title: 'Task Name',
      dataIndex: 'task_name',
      key: 'task_name',
      ellipsis: true,
    },
    {
      title: 'Model Name',
      dataIndex: 'model_name',
      key: 'model_name',
      render: (model: string) => (
        <Tag color={getModelColor(model)}>{model}</Tag>
      ),
    },
    {
      title: 'Concurrent Users',
      dataIndex: 'concurrent_users',
      key: 'concurrent_users',
      align: 'center',
    },
    {
      title: 'Created Time',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => formatDate(date),
    },
  ];

  // Table columns for selected tasks
  const selectedTasksColumns: ColumnsType<SelectedTask> = [
    {
      title: 'Task ID',
      dataIndex: 'task_id',
      key: 'task_id',
      ellipsis: true,
    },
    {
      title: 'Task Name',
      dataIndex: 'task_name',
      key: 'task_name',
      ellipsis: true,
    },
    {
      title: 'Model Name',
      dataIndex: 'model_name',
      key: 'model_name',
      render: (model: string) => (
        <Tag color={getModelColor(model)}>{model}</Tag>
      ),
    },
    {
      title: 'Concurrent Users',
      dataIndex: 'concurrent_users',
      key: 'concurrent_users',
      align: 'center',
    },
    {
      title: 'Created Time',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => formatDate(date),
    },
  ];

  // Chart configurations
  const createChartConfig = (
    yField: keyof ComparisonMetrics,
    title: string
  ) => ({
    data: comparisonResults.map((result, index) => ({
      task: `${result.model_name} - ${result.task_id.substring(0, 5)}(${result.concurrent_users}u) `,
      value: result[yField] as number,
      model: result.model_name,
      index,
    })),
    xField: 'task',
    yField: 'value',
    colorField: 'model',
    height: 300,
    title: { visible: true, text: title },
    color: comparisonResults.reduce(
      (acc, result) => {
        acc[result.model_name] = getModelColor(result.model_name);
        return acc;
      },
      {} as Record<string, string>
    ),
    label: {
      visible: true,
      position: 'top',
      formatter: (text: string) => `${parseFloat(text).toFixed(2)}`,
    },
    meta: {
      value: {
        alias: title,
      },
    },
    xAxis: {
      label: {
        autoRotate: true,
        autoHide: true,
        style: {
          fontSize: 10,
        },
      },
    },
  });

  // Metric descriptions for tooltips
  const metricDescriptions = {
    RPS: 'Number of requests sent per second',
    'TTFT (s)': 'Time to first token (s)',
    'Total TPS (tokens/s)': 'Number of input and generated tokens per second',
    'Completion TPS (tokens/s)': 'Number of generated tokens per second',
    'Avg. Total TPR (tokens/req)':
      'Average number of input and generated tokens per request',
    'Avg. Completion TPR (tokens/req)':
      'Average number of generated tokens per request',
  };

  // Helper function to create card title with tooltip
  const createCardTitle = (title: string, description: string) => (
    <Space>
      <span>{title}</span>
      <Tooltip title={description} placement='topRight'>
        <InfoCircleOutlined style={{ color: '#1890ff', cursor: 'help' }} />
      </Tooltip>
    </Space>
  );

  // Function to handle comparison results download
  const handleDownloadComparison = async () => {
    if (!modelInfoRef.current || !comparisonResultsRef.current) {
      messageApi.error(
        'Comparison components not fully loaded, please try again later.'
      );
      return;
    }

    setIsDownloading(true);
    messageApi.loading({
      content: 'Generating comparison report...',
      key: 'downloadComparison',
      duration: 0,
    });

    try {
      const elementsToCapture = [
        { ref: modelInfoRef, title: 'Model Info' },
        { ref: comparisonResultsRef, title: 'Comparison Results' },
      ];

      const canvases = await Promise.all(
        elementsToCapture.map(async elementInfo => {
          if (elementInfo.ref.current) {
            return html2canvas(elementInfo.ref.current, {
              useCORS: true,
              scale: 2,
              backgroundColor: '#ffffff',
            } as any);
          }
          return null;
        })
      );

      const validCanvases = canvases.filter(
        canvas => canvas !== null
      ) as HTMLCanvasElement[];
      if (validCanvases.length === 0) {
        throw new Error('Unable to capture any comparison content.');
      }

      // Calculate the total height and maximum width of the merged Canvas
      const padding = 30;
      let totalHeight = 0;
      let maxWidth = 0;

      validCanvases.forEach(canvas => {
        totalHeight += canvas.height;
        if (canvas.width > maxWidth) {
          maxWidth = canvas.width;
        }
      });
      if (validCanvases.length > 0) {
        totalHeight += (validCanvases.length - 1) * padding;
      }

      // Create a new Canvas for merging
      const mergedCanvas = document.createElement('canvas');
      mergedCanvas.width = maxWidth;
      mergedCanvas.height = totalHeight;
      const ctx = mergedCanvas.getContext('2d');

      if (!ctx) {
        throw new Error('Unable to create Canvas drawing context.');
      }

      // Set the background color of the merged image
      ctx.fillStyle = 'white';
      ctx.fillRect(0, 0, mergedCanvas.width, mergedCanvas.height);

      let currentY = 0;
      for (let i = 0; i < validCanvases.length; i++) {
        const canvas = validCanvases[i];
        const offsetX = (mergedCanvas.width - canvas.width) / 2;
        ctx.drawImage(canvas, offsetX > 0 ? offsetX : 0, currentY);
        currentY += canvas.height;

        if (i < validCanvases.length - 1) {
          currentY += padding;
        }
      }

      // Convert merged Canvas to image and download
      const image = mergedCanvas.toDataURL('image/png');
      const link = document.createElement('a');
      link.href = image;
      link.download = `model-comparison-${createFileTimestamp()}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      messageApi.success({
        content: 'Download successful!',
        key: 'downloadComparison',
        duration: 3,
      });
    } catch (err: any) {
      messageApi.error({
        content: `Download failed: ${err.message || 'Unknown error'}`,
        key: 'downloadComparison',
        duration: 4,
      });
    } finally {
      setIsDownloading(false);
    }
  };

  useEffect(() => {
    fetchAvailableTasks();
  }, [fetchAvailableTasks]);

  return (
    <div className='page-container'>
      {contextHolder}

      <PageHeader
        title=' Model Arena'
        description='Model performance comparison with multi-metric'
        icon={<BarChartOutlined />}
        className='mb-24'
      />

      {/* Model Info Section */}
      <div ref={modelInfoRef} className='mb-24'>
        <div className='flex justify-between align-center mb-16'>
          <Title level={5} style={{ margin: 0 }}>
            Model Info
          </Title>
          <Space>
            <Button
              type='primary'
              icon={<DownloadOutlined />}
              onClick={handleDownloadComparison}
              loading={isDownloading}
              disabled={comparisonResults.length === 0}
            >
              Download
            </Button>
            <Button
              type='primary'
              icon={<PlusOutlined />}
              onClick={handleModalOpen}
            >
              Select Model
            </Button>
            {selectedTasks.length > 0 && (
              <Button
                type='primary'
                danger
                icon={<ClearOutlined />}
                onClick={clearAllTasks}
                style={{
                  backgroundColor: '#ff4d4f',
                  borderColor: '#ff4d4f',
                  color: 'white',
                }}
              >
                Clear All
              </Button>
            )}
          </Space>
        </div>

        <Card>
          {selectedTasks.length === 0 ? (
            <Empty
              description='Please select the model for comparison'
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          ) : (
            <Table
              columns={selectedTasksColumns}
              dataSource={selectedTasks}
              rowKey='task_id'
              pagination={false}
              size='small'
            />
          )}
        </Card>
      </div>

      {/* Comparison Results */}
      {comparisonResults.length > 0 && (
        <div ref={comparisonResultsRef}>
          <Title level={5} className='mb-24'>
            Comparison Results
          </Title>

          <Row gutter={[16, 16]}>
            <Col span={12}>
              <Card
                title={createCardTitle(
                  'Time to First Token (TTFT)',
                  metricDescriptions['TTFT (s)']
                )}
                size='small'
              >
                <Column {...createChartConfig('ttft', 'TTFT (ms)')} />
              </Card>
            </Col>
            <Col span={12}>
              <Card
                title={createCardTitle(
                  'Requests Per Second (RPS)',
                  metricDescriptions.RPS
                )}
                size='small'
              >
                <Column {...createChartConfig('rps', 'RPS')} />
              </Card>
            </Col>
            <Col span={12}>
              <Card
                title={createCardTitle(
                  'Total Tokens Per Second (TPS)',
                  metricDescriptions['Total TPS (tokens/s)']
                )}
                size='small'
              >
                <Column {...createChartConfig('total_tps', 'Total TPS')} />
              </Card>
            </Col>
            <Col span={12}>
              <Card
                title={createCardTitle(
                  'Completion Tokens Per Second',
                  metricDescriptions['Completion TPS (tokens/s)']
                )}
                size='small'
              >
                <Column
                  {...createChartConfig('completion_tps', 'Completion TPS')}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card
                title={createCardTitle(
                  'Average Total Tokens Per Request',
                  metricDescriptions['Avg. Total TPR (tokens/req)']
                )}
                size='small'
              >
                <Column
                  {...createChartConfig('avg_total_tpr', 'Avg Total TPR')}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card
                title={createCardTitle(
                  'Average Completion Tokens Per Request',
                  metricDescriptions['Avg. Completion TPR (tokens/req)']
                )}
                size='small'
              >
                <Column
                  {...createChartConfig(
                    'avg_completion_tpr',
                    'Avg Completion TPR'
                  )}
                />
              </Card>
            </Col>
          </Row>
        </div>
      )}

      {/* Select Model Modal */}
      <Modal
        title='Select Model for Comparison'
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false);
          setTempSelectedTasks([]);
        }}
        width={1000}
        footer={
          <div className='flex justify-between align-center'>
            <Text type='secondary'>
              {tempSelectedTasks.length} task(s) selected
            </Text>
            <Space>
              <Button
                onClick={() => {
                  setIsModalVisible(false);
                  setTempSelectedTasks([]);
                }}
              >
                Cancel
              </Button>
              <Button
                type='primary'
                icon={<SwapOutlined />}
                loading={comparing}
                disabled={tempSelectedTasks.length < 2}
                onClick={compareResult}
              >
                Compare Result
              </Button>
            </Space>
          </div>
        }
      >
        <div className='mb-16'>
          <Space>
            <Input.Search
              placeholder='Search task name or model name'
              value={searchText}
              onChange={handleSearchChange}
              onSearch={handleSearch}
              allowClear
              className='w-300'
            />
            <Select
              placeholder='Filter model'
              value={selectedModel}
              onChange={handleModelFilterChange}
              className='w-200'
              allowClear
            >
              {uniqueModels.map(model => (
                <Option key={model} value={model}>
                  {model}
                </Option>
              ))}
            </Select>
            <Button
              icon={<ReloadOutlined />}
              onClick={fetchAvailableTasks}
              loading={loading}
            >
              Refresh
            </Button>
          </Space>
        </div>

        {loading ? (
          <div className='text-center p-24'>
            <LoadingSpinner size='large' />
          </div>
        ) : (
          <div>
            {filteredAvailableTasks.length === 0 ? (
              <Empty description='No available tasks found' />
            ) : (
              <div>
                <Alert
                  description='Select 2-10 completed tasks for comparison.'
                  type='info'
                  showIcon
                  className='mb-16'
                />
                <Table
                  columns={availableTasksColumns}
                  dataSource={filteredAvailableTasks}
                  rowKey='task_id'
                  pagination={{ pageSize: 10 }}
                  size='small'
                />
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default ResultComparison;
