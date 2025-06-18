/**
 * @file SystemLogs.tsx
 * @description System logs component
 * @author Charm
 * @copyright 2025
 * */

import {
  DownloadOutlined,
  DownOutlined,
  FullscreenExitOutlined,
  FullscreenOutlined,
  SearchOutlined,
  SyncOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Input,
  Select,
  Space,
  Spin,
  Switch,
  theme,
  Typography,
} from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import { logApi } from '../api/services';

const { Title } = Typography;
const { Search } = Input;

interface SystemLogsProps {
  serviceName: string;
  displayName: string;
  isActive: boolean;
}

const SystemLogs: React.FC<SystemLogsProps> = ({
  serviceName,
  displayName,
  isActive,
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string>('');
  const [filteredLogs, setFilteredLogs] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [fullscreen, setFullscreen] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [tailLines, setTailLines] = useState<number>(100);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const autoRefreshTimerRef = useRef<number | null>(null);
  const { token } = theme.useToken();

  // Track if it should scroll to the bottom
  const shouldScrollToBottom = useRef(true);

  // Automatically calculate height
  const getLogContainerHeight = () => {
    if (fullscreen) {
      return 'calc(100vh - 170px)';
    }
    return 'calc(100vh - 250px)';
  };

  // Scroll to bottom
  const scrollToBottom = () => {
    if (shouldScrollToBottom.current && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  };

  // Listen for scroll events
  useEffect(() => {
    const container = logContainerRef.current;
    // Make sure to add the event listener after the container is rendered and loaded
    if (!container || loading) {
      return;
    }

    let lastScrollTop = container.scrollTop;

    const handleScroll = () => {
      const currentScrollTop = container.scrollTop;
      const scrollDirection = currentScrollTop > lastScrollTop ? 'down' : 'up';
      // Handle the case where scrollTop may be negative when scrolling to the top
      lastScrollTop = currentScrollTop <= 0 ? 0 : currentScrollTop;

      const distanceFromBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight;

      // When the user scrolls up, pause auto-refresh and show the button
      if (scrollDirection === 'up' && distanceFromBottom > 50) {
        shouldScrollToBottom.current = false;

        // Use functional updates to avoid making state variables a dependency of the effect
        setShowScrollToBottom(prev => {
          if (prev === false) return true; // Only update the state when necessary
          return prev;
        });

        setAutoRefresh(prev => {
          if (prev === true) {
            return false;
          }
          return prev;
        });
      }

      // When the user manually scrolls back to the bottom, hide the button
      if (distanceFromBottom < 10) {
        shouldScrollToBottom.current = true;
        setShowScrollToBottom(prev => {
          if (prev === true) return false; // Only update the state when necessary
          return prev;
        });
      }
    };

    container.addEventListener('scroll', handleScroll);
    // Remove the event listener during effect cleanup
    return () => container.removeEventListener('scroll', handleScroll);
    // The dependency array includes loading to ensure correct execution after the loading state changes
  }, [serviceName, loading]);

  // Unified log acquisition function
  const fetchLogs = async () => {
    // This function is called by initial load and polling
    // It does not directly manage the `loading` state
    try {
      // A new fetch attempt will clear old polling errors
      if (fetchError) setFetchError(null);

      const contentResponse = await logApi.getServiceLogContent(
        serviceName,
        0,
        tailLines
      );

      if (
        contentResponse.data &&
        typeof contentResponse.data.content === 'string'
      ) {
        const newLogs = contentResponse.data.content;
        setLogs(newLogs);

        // If a search term exists, reapply the filter on the new logs
        if (searchTerm.trim()) {
          const lines = newLogs.split('\n');
          const filtered = lines
            .filter(line =>
              line.toLowerCase().includes(searchTerm.toLowerCase())
            )
            .join('\n');
          setFilteredLogs(filtered);
        } else {
          setFilteredLogs(newLogs);
        }
      } else {
        setLogs('');
        setFilteredLogs('');
      }
      // Clear serious errors after successful acquisition
      if (error) setError(null);
    } catch (err: any) {
      const errorMessage =
        err?.response?.data?.error ||
        err?.message ||
        `Failed to fetch ${displayName}`;
      console.error(`Failed to fetch ${displayName} content:`, err);
      // Show serious errors on initial load, and non-blocking errors on polling
      if (loading) {
        setError(errorMessage);
      } else {
        setFetchError(errorMessage);
      }
    } finally {
      if (shouldScrollToBottom.current) {
        setTimeout(scrollToBottom, 100);
      }
    }
  };

  // Effect for initial load and when service or line count settings change
  useEffect(() => {
    // Reset component state for the new view
    setSearchTerm('');
    shouldScrollToBottom.current = true;

    const load = async () => {
      setLoading(true);
      setError(null);
      setFetchError(null);
      await fetchLogs();
      setLoading(false);
    };

    load();
  }, [serviceName, tailLines]);

  // Effect for auto-refresh polling
  useEffect(() => {
    if (autoRefreshTimerRef.current) {
      clearInterval(autoRefreshTimerRef.current);
    }

    if (isActive && autoRefresh && !loading) {
      autoRefreshTimerRef.current = window.setInterval(() => {
        // If there is an error, pause polling
        if (!fetchError) {
          fetchLogs();
        }
      }, 3000);
    }

    return () => {
      if (autoRefreshTimerRef.current) {
        clearInterval(autoRefreshTimerRef.current);
      }
    };
  }, [isActive, autoRefresh, loading, fetchError, serviceName, tailLines]);

  // Add window size change listener
  useEffect(() => {
    const handleResize = () => {
      // Force re-render to adapt to the new window size
      if (logContainerRef.current) {
        const currentHeight = logContainerRef.current.style.height;
        logContainerRef.current.style.height = '0px';
        setTimeout(() => {
          if (logContainerRef.current) {
            logContainerRef.current.style.height = currentHeight;
          }
        }, 0);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleSearch = (value: string) => {
    setSearchTerm(value);

    // When a search is triggered, pause auto-refresh
    if (value.trim()) {
      if (autoRefresh) {
        setAutoRefresh(false);
      }
    }

    if (!value.trim()) {
      setFilteredLogs(logs);
      return;
    }

    // Filter lines containing the search term
    const lines = logs.split('\n');
    const filtered = lines
      .filter(line => line.toLowerCase().includes(value.toLowerCase()))
      .join('\n');

    setFilteredLogs(filtered);
  };

  const handleScrollToBottomClick = () => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
    shouldScrollToBottom.current = true;
    setShowScrollToBottom(false);

    // Restart polling after 2 seconds
    setTimeout(() => {
      setAutoRefresh(true);
      // message.success('Log auto-refresh resumed');
    }, 2000);
  };

  const handleDownload = () => {
    // Create a download link using the current log content
    if (logs) {
      const blob = new Blob([logs], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${serviceName}_log_${new Date().toISOString().slice(0, 10)}.txt`; // Update download file name
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  const toggleFullscreen = () => {
    setFullscreen(!fullscreen);
  };

  // Format log line
  const formatLogLine = (line: string) => {
    // Only match log level, ensure there's a space or line start, and there's a space or colon
    const levelRegex =
      /(^|\s)(INFO|ERROR|WARN|WARNING|DEBUG|CRITICAL|FATAL)(\s|:)/i;
    const levelMatch = line.match(levelRegex);

    if (!levelMatch) {
      // Lines without log level use normal style
      return <div className='log-line'>{line}</div>;
    }

    // Determine color based on log level
    const level = levelMatch[2].toUpperCase();
    let levelColor = '';

    switch (level) {
      case 'ERROR':
      case 'FATAL':
      case 'CRITICAL':
        levelColor = token.colorError;
        break;
      case 'WARN':
      case 'WARNING':
        levelColor = token.colorWarning;
        break;
      case 'INFO':
        levelColor = token.colorInfo;
        break;
      case 'DEBUG':
        levelColor = token.colorSuccess;
        break;
      default:
        levelColor = token.colorText;
    }

    // Find full match position (including prefix and suffix)
    const fullMatchIndex = line.indexOf(levelMatch[0]);
    const levelIndex = fullMatchIndex + levelMatch[1].length; // Adjust real log level start position
    const levelEnd = levelIndex + levelMatch[2].length; // Log level end position

    // Split log line
    const beforeLevel = line.substring(0, levelIndex);
    const levelPart = line.substring(levelIndex, levelEnd);
    const afterLevel = line.substring(levelEnd);

    return (
      <div className='log-line'>
        <span>{beforeLevel}</span>
        <span style={{ color: levelColor, fontWeight: 'bold' }}>
          {levelPart}
        </span>
        <span>{afterLevel}</span>
      </div>
    );
  };

  // Manual refresh and clear error state
  const handleManualRefresh = () => {
    const refresh = async () => {
      setLoading(true);
      setError(null);
      setFetchError(null);
      await fetchLogs();
      setLoading(false);
    };
    refresh();
  };

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '80vh',
          flexDirection: 'column',
        }}
      >
        <Spin size='large' />
        <div style={{ marginTop: 16 }}>Loading {displayName} data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '80vh',
        }}
      >
        <Alert
          description={error}
          type='error'
          showIcon
          style={{ background: 'transparent', border: 'none' }}
        />
      </div>
    );
  }

  if (!loading && !logs && !error) {
    // Ensure display when not loading and no error
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '80vh',
        }}
      >
        <Alert
          description={`No ${displayName} available`}
          type='info'
          showIcon
          style={{ background: 'transparent', border: 'none' }}
        />
      </div>
    );
  }

  return (
    <div
      style={{
        padding: fullscreen ? '0' : '0px',
        height: fullscreen ? '100vh' : 'auto',
        width: fullscreen ? '100vw' : 'auto',
        position: fullscreen ? 'fixed' : 'relative',
        top: fullscreen ? 0 : 'auto',
        left: fullscreen ? 0 : 'auto',
        zIndex: fullscreen ? 1000 : 'auto',
        backgroundColor: fullscreen ? token.colorBgContainer : 'transparent',
      }}
    >
      <Card
        variant={!fullscreen ? 'outlined' : 'borderless'}
        style={{
          height: fullscreen ? '100vh' : 'auto',
          boxShadow: fullscreen ? 'none' : undefined,
        }}
        title={
          <Space
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              width: '100%',
            }}
          >
            <Title level={4}>{displayName}</Title> {/* Use displayName */}
            <Space>
              <Select
                value={tailLines}
                onChange={value => setTailLines(value)}
                style={{ width: 140 }}
              >
                <Select.Option value={100}>Last 100 lines</Select.Option>
                <Select.Option value={500}>Last 500 lines</Select.Option>
                <Select.Option value={1000}>Last 1000 lines</Select.Option>
                <Select.Option value={0}>All logs</Select.Option>
              </Select>
              <Switch
                checkedChildren='Auto Refresh'
                unCheckedChildren='Stop Refresh'
                checked={autoRefresh}
                onChange={setAutoRefresh}
              />
              <Button icon={<SyncOutlined />} onClick={handleManualRefresh}>
                Refresh
              </Button>
              <Search
                placeholder='Search log content'
                allowClear
                enterButton={<SearchOutlined />}
                onSearch={handleSearch}
                style={{ width: 250 }}
              />
              <Button
                type='primary'
                icon={<DownloadOutlined />}
                onClick={handleDownload}
              >
                Download
              </Button>
              <Button
                icon={
                  fullscreen ? (
                    <FullscreenExitOutlined />
                  ) : (
                    <FullscreenOutlined />
                  )
                }
                onClick={toggleFullscreen}
              >
                {fullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
              </Button>
            </Space>
          </Space>
        }
        styles={{
          body: {
            padding: fullscreen ? '8px' : '24px',
            height: fullscreen ? 'calc(100vh - 70px)' : 'auto',
            position: 'relative',
          },
        }}
      >
        <div
          ref={logContainerRef}
          style={{
            backgroundColor: token.colorBgElevated,
            padding: '16px',
            borderRadius: '4px',
            height: getLogContainerHeight(),
            overflowY: 'auto',
            fontFamily:
              '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace',
            fontSize: '14px',
            lineHeight: '1.6',
            border: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          {searchTerm && (
            <Alert
              message={`Search results: "${searchTerm}"`}
              type='info'
              showIcon
              closable
              onClose={() => {
                setSearchTerm('');
                setFilteredLogs(logs);
              }}
              style={{ marginBottom: '16px' }}
            />
          )}

          {/* Display incremental fetch error */}
          {fetchError && (
            <Alert
              message='Log auto-refresh error'
              description={
                <div>
                  <p>{fetchError}</p>
                  <p>
                    Auto-refresh has been paused. Please check the service
                    status and click the "Refresh" button to retry.
                  </p>
                </div>
              }
              type='warning'
              showIcon
              icon={<WarningOutlined />}
              closable
              action={
                <Button
                  size='small'
                  type='primary'
                  onClick={handleManualRefresh}
                >
                  Refresh Now
                </Button>
              }
              onClose={() => setFetchError(null)}
              style={{ marginBottom: '16px' }}
            />
          )}

          {filteredLogs.split('\n').map((line, index) => (
            <React.Fragment key={index}>{formatLogLine(line)}</React.Fragment>
          ))}
        </div>
        {showScrollToBottom && (
          <Button
            type='text'
            onClick={handleScrollToBottomClick}
            style={{
              position: 'absolute',
              bottom: fullscreen ? '24px' : '40px',
              right: '40px',
              zIndex: 10,
            }}
            icon={
              <DownOutlined
                style={{ fontSize: '24px', color: token.colorPrimary }}
              />
            }
          />
        )}
      </Card>
    </div>
  );
};

export default SystemLogs;
