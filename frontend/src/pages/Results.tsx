/**
 * @file Results.tsx
 * @description Results page component
 * @author Charm
 * @copyright 2025
 * */
import {
  DownloadOutlined,
  FileTextOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  message,
  Row,
  Statistic,
  Table,
  Tooltip,
} from 'antd';
import html2canvas from 'html2canvas';
import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { benchmarkJobApi, resultApi } from '../api/services';
import { CopyButton } from '../components/ui/CopyButton';
import { IconTooltip } from '../components/ui/IconTooltip';
import { LoadingSpinner } from '../components/ui/LoadingState';
import { PageHeader } from '../components/ui/PageHeader';

const TaskResults: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<any[]>([]);
  const [taskInfo, setTaskInfo] = useState<any>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const configCardRef = useRef<HTMLDivElement | null>(null);
  const overviewCardRef = useRef<HTMLDivElement | null>(null);
  const detailsCardRef = useRef<HTMLDivElement | null>(null);
  const responseTimeCardRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!id) return;

      try {
        setLoading(true);
        setError(null);

        // Handle task information acquisition separately
        try {
          const taskResponse = await benchmarkJobApi.getJob(id);
          setTaskInfo(taskResponse.data);
        } catch (err: any) {
          // Failed to get task info - continue with results
        }

        // Try to get results
        try {
          const resultsResponse = await resultApi.getJobResult(id);

          if (resultsResponse.data?.status === 'error') {
            throw new Error(
              resultsResponse.data.error || 'Failed to get results'
            );
          }

          if (Array.isArray(resultsResponse.data)) {
            setResults(resultsResponse.data);
          } else if (
            resultsResponse.data &&
            Array.isArray(resultsResponse.data.results)
          ) {
            setResults(resultsResponse.data.results);
          } else if (
            resultsResponse.data &&
            Array.isArray(resultsResponse.data.data)
          ) {
            setResults(resultsResponse.data.data);
          } else {
            setResults([]);
            setError('No data');
          }
        } catch (err: any) {
          setError(err.message || 'Failed to get results');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id]);

  // Define metric results
  const TpsResult = results.find(item => item.metric_type === 'token_metrics');
  const CompletionResult = results.find(
    item => item.metric_type === 'Total_turnaround_time'
  );
  const firstTokenResult = results.find(
    item => item.metric_type === 'Time_to_first_output_token'
  );
  const outputCompletionResult = results.find(
    item => item.metric_type === 'Time_to_output_completion'
  );
  const failResult = results.find(item => item.metric_type === 'failure');

  // Calculate total failed requests from multiple sources
  const calculateFailedRequests = () => {
    // Get failure requests from 'failure' metric type
    const failureMetricRequests = failResult?.request_count || 0;

    // Get failure count from chat_completions or custom_api metric types
    const chatCompletionsResult = results.find(
      item => item.metric_type === 'chat_completions'
    );
    const customApiResult = results.find(
      item => item.metric_type === 'custom_api'
    );

    const chatCompletionsFailures = chatCompletionsResult?.failure_count || 0;
    const customApiFailures = customApiResult?.failure_count || 0;

    return failureMetricRequests + chatCompletionsFailures + customApiFailures;
  };

  // Check if we have any valid test results
  const hasValidResults =
    CompletionResult || firstTokenResult || outputCompletionResult || TpsResult;

  // Prepare table column definitions
  const metricExplanations: Record<string, string> = {
    Time_to_first_output_token:
      'Time to output the first token in the final answer (content field)',
    Time_to_output_completion: 'Total time for final answer generation',
    Total_turnaround_time: 'Total time to complete the entire request',
    Time_to_first_reasoning_token:
      'Time to output the first token in the reasoning part (reasoning_content field)',
    Time_to_reasoning_completion: 'Total time for reasoning part generation',
  };

  const statisticExplanations: Record<string, string> = {
    RPS: 'Number of requests sent per second',
    'TTFT (s)': 'Time to first token (s)',
    'Total TPS (tokens/s)': 'Number of input and generated tokens per second',
    'Completion TPS (tokens/s)': 'Number of generated tokens per second',
    'Avg. Total TPR (tokens/req)':
      'Average number of input and generated tokens per request',
    'Avg. Completion TPR (tokens/req)':
      'Average number of generated tokens per request',
  };

  const columns = [
    {
      title: 'Metric Type',
      dataIndex: 'metric_type',
      key: 'metric_type',
      render: (text: string) => {
        const explanation = metricExplanations[text];
        if (explanation) {
          return (
            <span>
              {text}{' '}
              <Tooltip title={explanation}>
                <InfoCircleOutlined className='ml-4' />
              </Tooltip>
            </span>
          );
        }
        return text;
      },
    },
    {
      title: 'Total Requests',
      dataIndex: 'request_count',
      key: 'request_count',
      render: (text: number) => text || 0,
    },
    // {
    //     title: 'Failed Requests',
    //     dataIndex: 'failure_count',
    //     key: 'failure_count',
    //     render: (text: number) => text || 0,
    // },
    {
      title: 'Avg Response Time (s)',
      dataIndex: 'avg_response_time',
      key: 'avg_response_time',
      render: (text: number, record: any) => {
        if (!text) return '0.00';
        if (record.metric_type === 'Time_to_output_completion' && text < 10) {
          return text.toFixed(3);
        }
        return (text / 1000).toFixed(2);
      },
    },
    {
      title: 'Max Response Time (s)',
      dataIndex: 'max_response_time',
      key: 'max_response_time',
      render: (text: number, record: any) => {
        if (!text) return '0.00';

        if (record.metric_type === 'Time_to_output_completion' && text < 10) {
          return text.toFixed(3);
        }
        return (text / 1000).toFixed(2);
      },
    },
    {
      title: 'Min Response Time (s)',
      dataIndex: 'min_response_time',
      key: 'min_response_time',
      render: (text: number, record: any) => {
        if (!text) return '0.00';

        if (record.metric_type === 'Time_to_output_completion' && text < 10) {
          return text.toFixed(3);
        }
        return (text / 1000).toFixed(2);
      },
    },
    {
      title: '90% Response Time (s)',
      dataIndex: 'percentile_90_response_time',
      key: 'percentile_90_response_time',
      render: (text: number, record: any) => {
        if (!text) return '0.00';
        if (record.metric_type === 'Time_to_output_completion' && text < 10) {
          return text.toFixed(3);
        }
        return (text / 1000).toFixed(2);
      },
    },
    {
      title: 'Median Response Time (s)',
      dataIndex: 'median_response_time',
      key: 'median_response_time',
      render: (text: number, record: any) => {
        if (!text) return '0.00';

        if (record.metric_type === 'Time_to_output_completion' && text < 10) {
          return text.toFixed(3);
        }
        return (text / 1000).toFixed(2);
      },
    },
    {
      title: 'RPS (req/s)',
      dataIndex: 'rps',
      key: 'rps',
      render: (text: number) => (text ? text.toFixed(2) : '0.00'),
    },
  ];

  // Function to handle report download
  const handleDownloadReport = async () => {
    if (
      !configCardRef.current ||
      !overviewCardRef.current ||
      !responseTimeCardRef.current
    ) {
      message.error(
        'Report components not fully loaded, please try again later.'
      );
      return;
    }

    setIsDownloading(true);
    message.loading({
      content: 'Generating report...',
      key: 'downloadReport',
      duration: 0,
    });

    try {
      const elementsToCapture = [
        { ref: configCardRef, title: 'Test Configuration' },
        { ref: overviewCardRef, title: 'Results Overview' },
        { ref: responseTimeCardRef, title: 'Response Time' },
      ];

      const canvases = await Promise.all(
        elementsToCapture.map(async elementInfo => {
          if (elementInfo.ref.current) {
            // Use html2canvas to convert DOM elements to canvas
            return html2canvas(elementInfo.ref.current, {
              useCORS: true, // This option is needed if there are cross-origin images in the Card
              scale: 2, // Increase image clarity, can be adjusted as needed
              backgroundColor: '#ffffff',
            } as any); // Add type assertion as any
          }
          return null;
        })
      );

      const validCanvases = canvases.filter(
        canvas => canvas !== null
      ) as HTMLCanvasElement[];
      if (validCanvases.length === 0) {
        throw new Error('Unable to capture any report content.');
      }

      // Calculate the total height and maximum width of the merged Canvas
      const padding = 30; // Vertical spacing between image blocks
      let totalHeight = 0; // Initialize total height
      let maxWidth = 0;

      validCanvases.forEach(canvas => {
        totalHeight += canvas.height;
        if (canvas.width > maxWidth) {
          maxWidth = canvas.width;
        }
      });
      // Add spacing between canvases
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

        // Draw screenshot
        // Horizontally center and draw the canvas
        const offsetX = (mergedCanvas.width - canvas.width) / 2;
        ctx.drawImage(canvas, offsetX > 0 ? offsetX : 0, currentY);
        currentY += canvas.height;

        // Add block spacing
        if (i < validCanvases.length - 1) {
          currentY += padding;
        }
      }

      // Convert merged Canvas to image and download
      const image = mergedCanvas.toDataURL('image/png');
      const link = document.createElement('a');
      link.href = image;
      link.download = `task-results-${taskInfo?.name || taskInfo?.id || ''}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      message.success({
        content: 'Download successful!',
        key: 'downloadReport',
        duration: 3,
      });
    } catch (err: any) {
      message.error({
        content: `Download failed: ${err.message || 'Unknown error'}`,
        key: 'downloadReport',
        duration: 4,
      });
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className='page-container'>
      <div className='flex justify-between align-center mb-24'>
        <PageHeader
          title='Results report'
          icon={<FileTextOutlined />}
          level={3}
          className='text-center w-full'
        />
      </div>

      <Button
        type='primary'
        icon={<DownloadOutlined />}
        onClick={handleDownloadReport}
        loading={isDownloading}
        disabled={loading || !!error || !results || results.length === 0}
        className='mb-24'
      >
        Download Report
      </Button>

      {loading ? (
        <div className='loading-container'>
          <LoadingSpinner
            text='Loading result data...'
            size='large'
            className='text-center'
          />
        </div>
      ) : error ? (
        <div className='flex justify-center p-24'>
          <Alert
            description={error}
            type='error'
            showIcon
            className='btn-transparent'
          />
        </div>
      ) : !results || results.length === 0 ? (
        <div className='flex justify-center p-24'>
          <Alert
            description='No test results available'
            type='info'
            showIcon
            className='btn-transparent'
          />
        </div>
      ) : (
        <>
          {/* Test Configuration */}
          <Card
            ref={configCardRef}
            title='Test Configuration'
            variant='borderless'
            className='mb-24 form-card'
          >
            <Descriptions bordered>
              <Descriptions.Item label='Task ID'>
                {taskInfo?.id || id}
              </Descriptions.Item>
              <Descriptions.Item label='Task Name'>
                {taskInfo?.name || 'Unnamed Task'}
              </Descriptions.Item>
              <Descriptions.Item label='Target URL'>
                {taskInfo?.target_host || 'N/A'}
              </Descriptions.Item>
              <Descriptions.Item label='Model Name'>
                {taskInfo?.model || 'N/A'}
              </Descriptions.Item>
              <Descriptions.Item label='Concurrent Users'>
                {taskInfo?.user_count || taskInfo?.concurrent_users || 0}
              </Descriptions.Item>
              <Descriptions.Item label='Test Duration'>
                {taskInfo?.duration || 0} s
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* Results Overview */}
          <Card
            ref={overviewCardRef}
            title='Results Overview'
            variant='borderless'
            className='mb-24 form-card'
          >
            {(() => {
              if (!hasValidResults) {
                return (
                  <Alert
                    message='No valid test results found'
                    type='warning'
                    showIcon
                    className='btn-transparent'
                  />
                );
              }

              const baseRequestCount =
                CompletionResult?.request_count ||
                firstTokenResult?.request_count ||
                0;
              const failedRequestCount = calculateFailedRequests();
              const actualTotalRequests = baseRequestCount + failedRequestCount;
              const actualSuccessRate =
                actualTotalRequests > 0
                  ? (baseRequestCount / actualTotalRequests) * 100
                  : 0;

              return (
                <>
                  {/* First row: request count, success rate, RPS */}
                  <Row gutter={16} className='mb-16'>
                    <Col span={6}>
                      <Statistic
                        title='Total Requests'
                        value={actualTotalRequests}
                      />
                    </Col>
                    <Col span={6}>
                      <Statistic
                        title='Success Rate'
                        value={actualSuccessRate}
                        precision={2}
                        suffix='%'
                      />
                    </Col>
                    <Col span={6}>
                      <Statistic
                        title={
                          <span>
                            RPS
                            <IconTooltip
                              title={statisticExplanations.RPS}
                              className='ml-4'
                              color='#1890ff'
                            />
                          </span>
                        }
                        value={
                          CompletionResult?.rps || firstTokenResult?.rps || '-'
                        }
                        precision={2}
                      />
                    </Col>
                    <Col span={6}>
                      <Statistic
                        title={
                          <span>
                            TTFT (s)
                            <IconTooltip
                              title={statisticExplanations['TTFT (s)']}
                              className='ml-4'
                              color='#1890ff'
                            />
                          </span>
                        }
                        value={
                          firstTokenResult?.avg_response_time
                            ? (
                                firstTokenResult.avg_response_time / 1000
                              ).toFixed(2)
                            : '-'
                        }
                      />
                    </Col>
                  </Row>

                  {/* Second row: Total TPS, Completion TPS, Avg. Total TPR, Avg. Completion TPR */}
                  <Row gutter={16}>
                    <Col span={6}>
                      <Statistic
                        title={
                          <span>
                            Total TPS (tokens/s)
                            <IconTooltip
                              title={
                                statisticExplanations['Total TPS (tokens/s)']
                              }
                              className='ml-4'
                              color='#1890ff'
                            />
                          </span>
                        }
                        value={TpsResult?.total_tps || '-'}
                        precision={2}
                      />
                    </Col>
                    <Col span={6}>
                      <Statistic
                        title={
                          <span>
                            Completion TPS (tokens/s)
                            <IconTooltip
                              title={
                                statisticExplanations[
                                  'Completion TPS (tokens/s)'
                                ]
                              }
                              className='ml-4'
                              color='#1890ff'
                            />
                          </span>
                        }
                        value={TpsResult?.completion_tps || '-'}
                        precision={2}
                      />
                    </Col>
                    <Col span={6}>
                      <Statistic
                        title={
                          <span>
                            Avg. Total TPR (tokens/req)
                            <IconTooltip
                              title={
                                statisticExplanations[
                                  'Avg. Total TPR (tokens/req)'
                                ]
                              }
                              className='ml-4'
                              color='#1890ff'
                            />
                          </span>
                        }
                        value={TpsResult?.avg_total_tokens_per_req || '-'}
                        precision={2}
                      />
                    </Col>
                    <Col span={6}>
                      <Statistic
                        title={
                          <span>
                            Avg. Completion TPR (tokens/req)
                            <IconTooltip
                              title={
                                statisticExplanations[
                                  'Avg. Completion TPR (tokens/req)'
                                ]
                              }
                              className='ml-4'
                              color='#1890ff'
                            />
                          </span>
                        }
                        value={TpsResult?.avg_completion_tokens_per_req || '-'}
                        precision={2}
                      />
                    </Col>
                  </Row>
                </>
              );
            })()}
          </Card>

          {/* Response Time */}
          <Card
            ref={responseTimeCardRef}
            title='Response Time'
            variant='borderless'
            className='mb-24'
            style={{
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
            }}
          >
            <Table
              dataSource={results.filter(
                item =>
                  item.metric_type !== 'total_tokens_per_second' &&
                  item.metric_type !== 'completion_tokens_per_second' &&
                  item.metric_type !== 'token_metrics'
              )}
              columns={columns}
              rowKey='metric_type'
              pagination={false}
            />
          </Card>

          {/* Test Result Details */}
          <Card
            ref={detailsCardRef}
            title='Result Details'
            variant='borderless'
            className='mb-24'
            style={{
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
            }}
          >
            <div style={{ position: 'relative' }}>
              <pre
                className='modal-pre'
                style={{
                  backgroundColor: '#f5f5f5',
                  padding: '16px',
                  borderRadius: '4px',
                  overflow: 'auto',
                  maxHeight: '500px',
                }}
              >
                <code>{JSON.stringify(results, null, 2)}</code>
              </pre>
              <div
                style={{
                  position: 'absolute',
                  top: '8px',
                  right: '8px',
                }}
              >
                <CopyButton
                  text={JSON.stringify(results, null, 2)}
                  successMessage='Results copied to clipboard'
                  tooltip='Copy results'
                />
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
};

export default TaskResults;
