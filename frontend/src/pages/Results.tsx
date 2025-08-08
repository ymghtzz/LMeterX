/**
 * @file Results.tsx
 * @description Results page component
 * @author Charm
 * @copyright 2025
 * */
import {
  DownloadOutlined,
  DownOutlined,
  FileTextOutlined,
  InfoCircleOutlined,
  RobotOutlined,
  UpOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  message,
  Modal,
  Row,
  Space,
  Statistic,
  Table,
  Tooltip,
} from 'antd';
import html2canvas from 'html2canvas';
import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { analysisApi, benchmarkJobApi, resultApi } from '../api/services';
import { CopyButton } from '../components/ui/CopyButton';
import { IconTooltip } from '../components/ui/IconTooltip';
import { LoadingSpinner } from '../components/ui/LoadingState';
import MarkdownRenderer from '../components/ui/MarkdownRenderer';
import { PageHeader } from '../components/ui/PageHeader';

const TaskResults: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<any[]>([]);
  const [taskInfo, setTaskInfo] = useState<any>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisModalVisible, setAnalysisModalVisible] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [showAnalysisReport, setShowAnalysisReport] = useState(false);
  const [isAnalysisExpanded, setIsAnalysisExpanded] = useState(true);
  const configCardRef = useRef<HTMLDivElement | null>(null);
  const overviewCardRef = useRef<HTMLDivElement | null>(null);
  const detailsCardRef = useRef<HTMLDivElement | null>(null);
  const responseTimeCardRef = useRef<HTMLDivElement | null>(null);

  // Function to fetch analysis result
  const fetchAnalysisResult = async () => {
    if (!id) return;

    try {
      const response = await analysisApi.getAnalysis(id);
      if (response.data?.status === 'success' && response.data?.data) {
        setAnalysisResult(response.data.data);
        // 如果有分析结果，自动展开显示
        setShowAnalysisReport(true);
        setIsAnalysisExpanded(true);
      } else if (response.data?.status === 'error') {
        // Log the error but don't show to user as this is just fetching existing analysis
        console.warn('Failed to fetch analysis result:', response.data?.error);
      }
    } catch (err: any) {
      // Analysis not found or other error - ignore for fetching
      console.warn('Error fetching analysis result:', err);
    }
  };

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

    // Fetch analysis result if available
    fetchAnalysisResult();
  }, [id]);

  // Define metric results
  const TpsResult = results.find(item => item.metric_type === 'token_metrics');
  const CompletionResult = results.find(
    item => item.metric_type === 'Total_time'
  );
  const firstReasoningToken = results.find(
    item => item.metric_type === 'Time_to_first_reasoning_token'
  );
  const firstOutputToken = results.find(
    item => item.metric_type === 'Time_to_first_output_token'
  );
  // Use Time_to_first_reasoning_token if available, otherwise use Time_to_first_output_token
  const firstTokenResult = firstReasoningToken || firstOutputToken;
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
    Time_to_output_completion: 'Generation time for the final answer ',
    Total_time: 'Total time to complete the entire request',
    Time_to_first_reasoning_token:
      'Time to output the first token in the reasoning part (reasoning_content field)',
    Time_to_reasoning_completion: 'Generation time for the reasoning part',
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

  // Function to handle AI Summary
  const handleAnalysis = async () => {
    if (!id) return;

    setIsAnalyzing(true);
    try {
      const response = await analysisApi.analyzeTask(id);

      // Check if the response indicates an error
      if (
        response.data?.status === 'error' ||
        response.data?.status === 'failed'
      ) {
        // Extract the most specific error message
        const errorMessage =
          response.data?.error_message ||
          response.data?.error ||
          'AI analysis failed';

        // If backend returns error_message, show it directly without prefix
        if (response.data?.error_message) {
          message.error(errorMessage);
        } else {
          // Only add prefix for generic errors
          message.error(`AI summary failed: ${errorMessage}`);
        }
        return;
      }

      setAnalysisResult(response.data);
      setAnalysisModalVisible(false);
      setShowAnalysisReport(true); // 分析成功后自动展开显示
      setIsAnalysisExpanded(true); // 默认展开
      message.success('AI summary completed!');

      // Fetch the analysis result to display
      await fetchAnalysisResult();
    } catch (err: any) {
      // Handle different types of errors
      let errorMessage = 'AI summary failed';

      if (err.data) {
        // API error response - prioritize error_message over error
        if (err.data.error_message) {
          errorMessage = err.data.error_message;
        } else if (err.data.error) {
          errorMessage = err.data.error;
        } else if (err.data.detail) {
          errorMessage = err.data.detail;
        }
      } else if (err.message) {
        // Network or other error
        errorMessage = err.message;
      }

      // If backend returns error_message, show it directly without prefix
      if (err.data?.error_message) {
        message.error(errorMessage);
      } else {
        // Only add prefix for generic errors
        message.error(`AI summary failed: ${errorMessage}`);
      }

      // Log the error for debugging
      console.error('AI analysis error:', err);
    } finally {
      setIsAnalyzing(false);
    }
  };

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
          title=' Results report'
          icon={<FileTextOutlined />}
          level={3}
          className='text-center w-full'
        />
      </div>

      <Space className='mb-24'>
        <Button
          type='default'
          icon={<RobotOutlined />}
          onClick={() => setAnalysisModalVisible(true)}
          loading={isAnalyzing}
          disabled={loading || !!error || !results || results.length === 0}
          style={{
            backgroundColor: '#52c41a',
            borderColor: '#52c41a',
            color: '#ffffff',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.backgroundColor = '#73d13d';
            e.currentTarget.style.borderColor = '#73d13d';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.backgroundColor = '#52c41a';
            e.currentTarget.style.borderColor = '#52c41a';
          }}
        >
          AI Summary
        </Button>
        <Button
          type='primary'
          icon={<DownloadOutlined />}
          onClick={handleDownloadReport}
          loading={isDownloading}
          disabled={loading || !!error || !results || results.length === 0}
        >
          Download Report
        </Button>
      </Space>

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
          {/* AI Summary Report - 自适应展开 */}
          {showAnalysisReport && analysisResult && (
            <Card
              title={
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    width: '100%',
                  }}
                >
                  <span
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    AI Summary
                  </span>
                  <Space>
                    <CopyButton
                      text={analysisResult.analysis_report}
                      successMessage='Analysis copied to clipboard'
                      tooltip='Copy analysis'
                    />
                    <Button
                      type='text'
                      size='small'
                      icon={
                        isAnalysisExpanded ? <UpOutlined /> : <DownOutlined />
                      }
                      onClick={() => setIsAnalysisExpanded(!isAnalysisExpanded)}
                      style={{ padding: '4px 8px' }}
                    >
                      {isAnalysisExpanded ? '收起' : '展开'}
                    </Button>
                  </Space>
                </div>
              }
              variant='borderless'
              className='mb-24 form-card'
              style={{
                border: '1px solid #f0f0f0',
                borderRadius: '8px',
                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
              }}
            >
              {isAnalysisExpanded && (
                <div style={{ padding: '16px 0' }}>
                  <MarkdownRenderer
                    content={analysisResult.analysis_report}
                    className='analysis-content'
                  />
                </div>
              )}
            </Card>
          )}

          {/* Test Configuration */}
          <Card
            ref={configCardRef}
            title={
              <div
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                Test Configuration
              </div>
            }
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
                {taskInfo?.target_host && taskInfo?.api_path
                  ? `${taskInfo.target_host}${taskInfo.api_path}`
                  : taskInfo?.target_host || 'N/A'}
              </Descriptions.Item>
              <Descriptions.Item label='Request Payload'>
                {taskInfo?.request_payload ? (
                  <div style={{ maxWidth: '400px', wordBreak: 'break-all' }}>
                    {taskInfo.request_payload.length > 200 ? (
                      <Tooltip
                        title={
                          <div style={{ position: 'relative' }}>
                            <div
                              style={{
                                position: 'absolute',
                                top: '8px',
                                right: '8px',
                                zIndex: 1,
                              }}
                            >
                              <CopyButton
                                text={taskInfo.request_payload}
                                successMessage='Request payload copied to clipboard'
                                tooltip='Copy'
                                size='small'
                              />
                            </div>
                            <pre
                              style={{
                                maxWidth: '600px',
                                maxHeight: '300px',
                                overflow: 'auto',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-all',
                                fontSize: '12px',
                                backgroundColor: '#ffffff',
                                color: '#333333',
                                padding: '12px',
                                borderRadius: '6px',
                                margin: 0,
                                fontFamily:
                                  'Monaco, Menlo, "Ubuntu Mono", monospace',
                                lineHeight: '1.4',
                              }}
                            >
                              {taskInfo.request_payload}
                            </pre>
                          </div>
                        }
                        placement='top'
                        styles={{
                          body: {
                            maxWidth: '600px',
                            backgroundColor: '#ffffff',
                            color: '#ffffff',
                          },
                        }}
                      >
                        <div style={{ cursor: 'pointer' }}>
                          {`${taskInfo.request_payload.substring(0, 200)}...`}
                        </div>
                      </Tooltip>
                    ) : (
                      <div>{taskInfo.request_payload}</div>
                    )}
                  </div>
                ) : (
                  'N/A'
                )}
              </Descriptions.Item>
              <Descriptions.Item label='Dataset Source'>
                {(() => {
                  if (taskInfo?.test_data === 'default') {
                    return 'Built-in Dataset';
                  }
                  if (taskInfo?.test_data && taskInfo.test_data !== 'default') {
                    return 'Custom Dataset';
                  }
                  return '-';
                })()}
              </Descriptions.Item>
              <Descriptions.Item label='Dataset Type'>
                {(() => {
                  if (taskInfo?.test_data === 'default') {
                    if (taskInfo?.chat_type === 1) {
                      return 'Multimodal (Text + Image)';
                    }
                    return 'Text-Only Conversations';
                  }
                  return '-';
                })()}
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
            title={
              <div
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                Results Overview
              </div>
            }
            variant='borderless'
            className='mb-24 form-card'
            style={{
              border: '2px solid #1890ff',
              borderRadius: '12px',
              boxShadow: '0 4px 16px rgba(24, 144, 255, 0.15)',
              backgroundColor: '#f8fbff',
            }}
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
            title={
              <div
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                Response Time
              </div>
            }
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
                  item.metric_type !== 'token_metrics' &&
                  (results.length <= 1 ||
                    item.metric_type !== 'chat_completions')
              )}
              columns={columns}
              rowKey='metric_type'
              pagination={false}
            />
          </Card>

          {/* Test Result Details */}
          <Card
            ref={detailsCardRef}
            title={
              <div
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                Result Details
              </div>
            }
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

      {/* AI Summary Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <RobotOutlined style={{ color: '#52c41a' }} />
            AI Summary
          </div>
        }
        open={analysisModalVisible}
        onCancel={() => setAnalysisModalVisible(false)}
        footer={null}
        width={500}
      >
        <div style={{ padding: '20px 0' }}>
          <Alert
            description='Please ensure that the test results are complete and the AI analysis model has been configured'
            type='info'
            showIcon
            style={{ marginBottom: '16px' }}
          />
        </div>
        <div style={{ textAlign: 'center', marginTop: '20px' }}>
          <Space>
            <Button
              type='primary'
              onClick={handleAnalysis}
              loading={isAnalyzing}
              icon={<RobotOutlined />}
            >
              Start Analysis
            </Button>
            <Button onClick={() => setAnalysisModalVisible(false)}>
              Cancel
            </Button>
          </Space>
        </div>
      </Modal>
    </div>
  );
};

export default TaskResults;
