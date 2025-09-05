#!/usr/bin/env python3
"""
修复多进程压测中的问题：
1. Worker进程心跳失败和重连问题
2. 请求聚合失败
3. 增强Worker进程的稳定性和metrics收集
"""

import os
import re

def fix_locustfile():
    """修复locustfile.py中的多进程问题"""
    locustfile_path = "st_engine/engine/locustfile.py"
    
    if not os.path.exists(locustfile_path):
        print(f"文件不存在: {locustfile_path}")
        return
    
    with open(locustfile_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修复Worker进程的metrics发送逻辑
    old_worker_handler = '''            def on_master_msg(environment, msg, **_):
                if msg.type == "request_metrics":
                    # Send metrics immediately when Master requests
                    try:
                        from utils.common import calculate_custom_metrics

                        global_task_queue = GlobalStateManager.get_global_task_queue()
                        start_time = GlobalStateManager.get_start_time()
                        end_time = time.time()
                        execution_time = (end_time - start_time) if start_time else 0

                        custom_metrics = calculate_custom_metrics(
                            os.environ.get("TASK_ID", "unknown"),
                            global_task_queue,
                            execution_time,
                        )

                        # Add PID to metrics for proper identification
                        custom_metrics["pid"] = os.getpid()

                        environment.runner.send_message(
                            "worker_custom_metrics", custom_metrics
                        )
                        task_logger.debug(
                            f"Metrics sent in response to master request: {custom_metrics}"
                        )

                    except Exception as e:
                        task_logger.error(
                            f"Failed to send metrics in response to master request: {e}"
                        )'''
    
    new_worker_handler = '''            def on_master_msg(environment, msg, **_):
                if msg.type == "request_metrics":
                    # Send metrics immediately when Master requests with retry mechanism
                    try:
                        from utils.common import calculate_custom_metrics

                        global_task_queue = GlobalStateManager.get_global_task_queue()
                        start_time = GlobalStateManager.get_start_time()
                        end_time = time.time()
                        execution_time = (end_time - start_time) if start_time else 0

                        custom_metrics = calculate_custom_metrics(
                            os.environ.get("TASK_ID", "unknown"),
                            global_task_queue,
                            execution_time,
                        )

                        # Add process identification
                        custom_metrics["pid"] = os.getpid()
                        custom_metrics["worker_id"] = getattr(environment.runner, "worker_id", f"worker_{os.getpid()}")

                        # Send with retry mechanism
                        for attempt in range(3):
                            try:
                                environment.runner.send_message(
                                    "worker_custom_metrics", custom_metrics
                                )
                                task_logger.debug(
                                    f"Metrics sent in response to master request (attempt {attempt + 1}): {custom_metrics}"
                                )
                                
                                # Send confirmation
                                environment.runner.send_message(
                                    "worker_metrics_sent", {"pid": os.getpid(), "worker_id": custom_metrics["worker_id"]}
                                )
                                break
                            except Exception as e:
                                task_logger.warning(f"Failed to send metrics (attempt {attempt + 1}): {e}")
                                if attempt < 2:
                                    import time
                                    time.sleep(0.5)
                                else:
                                    raise

                    except Exception as e:
                        task_logger.error(
                            f"Failed to send metrics in response to master request: {e}"
                        )'''
    
    if old_worker_handler in content:
        content = content.replace(old_worker_handler, new_worker_handler)
        print("已修复Worker进程的metrics发送逻辑")
    else:
        print("未找到需要修复的Worker进程handler")
    
    # 修复Master进程的Worker消息处理
    old_master_handler = '''            def on_worker_msg(environment, msg, **_):
                if msg.type == "worker_custom_metrics":
                    # Check if we've already received metrics from this Worker
                    worker_pid = msg.data.get("pid", "unknown")
                    if worker_pid not in environment.worker_metrics_received:
                        environment.worker_metrics_received.add(worker_pid)
                        environment.worker_metrics_list.append(msg.data)
                        task_logger.debug(
                            f"Master received worker metrics from PID {worker_pid}: {msg.data}"
                        )
                    else:
                        task_logger.warning(
                            f"Duplicate metrics received from worker PID {worker_pid}"
                        )
                elif msg.type == "worker_metrics_sent":
                    worker_pid = msg.data.get("pid", "unknown")
                    environment.worker_confirmations.add(worker_pid)
                    task_logger.debug(
                        f"Master received confirmation from worker {worker_pid}"
                    )'''
    
    new_master_handler = '''            def on_worker_msg(environment, msg, **_):
                if msg.type == "worker_custom_metrics":
                    # Check if we've already received metrics from this Worker
                    worker_pid = msg.data.get("pid", "unknown")
                    worker_id = msg.data.get("worker_id", f"worker_{worker_pid}")
                    
                    # Use worker_id as primary identifier to avoid PID conflicts
                    if worker_id not in environment.worker_metrics_received:
                        environment.worker_metrics_received.add(worker_id)
                        environment.worker_metrics_list.append(msg.data)
                        task_logger.debug(
                            f"Master received worker metrics from {worker_id} (PID {worker_pid}): {msg.data}"
                        )
                    else:
                        task_logger.warning(
                            f"Duplicate metrics received from worker {worker_id} (PID {worker_pid})"
                        )
                elif msg.type == "worker_metrics_sent":
                    worker_pid = msg.data.get("pid", "unknown")
                    worker_id = msg.data.get("worker_id", f"worker_{worker_pid}")
                    environment.worker_confirmations.add(worker_id)
                    task_logger.debug(
                        f"Master received confirmation from worker {worker_id} (PID {worker_pid})"
                    )'''
    
    if old_master_handler in content:
        content = content.replace(old_master_handler, new_master_handler)
        print("已修复Master进程的Worker消息处理逻辑")
    else:
        print("未找到需要修复的Master进程handler")
    
    # 修复test_stop事件中的Worker metrics聚合逻辑
    old_aggregation = '''    # Wait for Worker metrics in multi-process mode
    if is_multiprocess and worker_count > 0:
        import gevent

        max_wait_time = 10
        wait_time = 0

        # Actively request Worker metrics
        try:
            if hasattr(environment.runner, "send_message"):
                task_logger.debug("Actively requesting metrics from all workers...")
                environment.runner.send_message(
                    "request_metrics", {"request": "all_metrics"}
                )
                gevent.sleep(1)
        except Exception as e:
            task_logger.warning(f"Failed to actively request worker metrics: {e}")

        while len(worker_metrics_list) < worker_count and wait_time < max_wait_time:
            gevent.sleep(0.5)
            wait_time += 0.5
            task_logger.debug(
                f"Waiting for worker metrics... ({len(worker_metrics_list)}/{worker_count}) after {wait_time}s"
            )

        if len(worker_metrics_list) < worker_count:
            task_logger.warning(
                f"Only received {len(worker_metrics_list)} worker metrics out of {worker_count} expected workers"
            )'''
    
    new_aggregation = '''    # Wait for Worker metrics in multi-process mode
    if is_multiprocess and worker_count > 0:
        import gevent

        max_wait_time = 15  # 增加等待时间
        wait_time = 0

        # Actively request Worker metrics with multiple attempts
        for attempt in range(3):
            try:
                if hasattr(environment.runner, "send_message"):
                    task_logger.debug(f"Actively requesting metrics from all workers... (attempt {attempt + 1})")
                    environment.runner.send_message(
                        "request_metrics", {"request": "all_metrics", "attempt": attempt + 1}
                    )
                    gevent.sleep(1)
            except Exception as e:
                task_logger.warning(f"Failed to actively request worker metrics (attempt {attempt + 1}): {e}")

        while len(worker_metrics_list) < worker_count and wait_time < max_wait_time:
            gevent.sleep(0.5)
            wait_time += 0.5
            task_logger.debug(
                f"Waiting for worker metrics... ({len(worker_metrics_list)}/{worker_count}) after {wait_time}s"
            )
            
            # 每5秒重新请求一次metrics
            if wait_time % 5 == 0 and wait_time > 0:
                try:
                    if hasattr(environment.runner, "send_message"):
                        environment.runner.send_message(
                            "request_metrics", {"request": "retry_metrics", "wait_time": wait_time}
                        )
                except Exception as e:
                    task_logger.warning(f"Failed to retry request worker metrics: {e}")

        if len(worker_metrics_list) < worker_count:
            task_logger.warning(
                f"Only received {len(worker_metrics_list)} worker metrics out of {worker_count} expected workers"
            )
            # 记录已收到的worker信息用于调试
            received_workers = [wm.get("worker_id", f"worker_{wm.get('pid', 'unknown')}") for wm in worker_metrics_list]
            task_logger.warning(f"Received metrics from workers: {received_workers}")'''
    
    if old_aggregation in content:
        content = content.replace(old_aggregation, new_aggregation)
        print("已修复Worker metrics聚合逻辑")
    else:
        print("未找到需要修复的聚合逻辑")
    
    # 修复Worker metrics聚合中的PID处理
    old_pid_processing = '''        if worker_metrics_list:
            task_logger.debug(
                f"Multi-process mode: aggregating {len(worker_metrics_list)} worker metrics"
            )

            processed_pids = set()
            for wm in worker_metrics_list:
                pid = wm.get("pid")
                if pid not in processed_pids:
                    processed_pids.add(pid)
                    total_reqs += wm.get("reqs_num", 0)
                    total_comp_tokens += wm.get("completion_tokens", 0)
                    total_all_tokens += wm.get("all_tokens", 0)
                    task_logger.debug(f"Aggregated worker metrics from PID {pid}: {wm}")

            task_logger.debug(
                f"Multi-process mode: aggregated {len(processed_pids)} unique worker metrics"
            )'''
    
    new_pid_processing = '''        if worker_metrics_list:
            task_logger.debug(
                f"Multi-process mode: aggregating {len(worker_metrics_list)} worker metrics"
            )

            processed_workers = set()
            for wm in worker_metrics_list:
                worker_id = wm.get("worker_id", f"worker_{wm.get('pid', 'unknown')}")
                pid = wm.get("pid")
                if worker_id not in processed_workers:
                    processed_workers.add(worker_id)
                    total_reqs += wm.get("reqs_num", 0)
                    total_comp_tokens += wm.get("completion_tokens", 0)
                    total_all_tokens += wm.get("all_tokens", 0)
                    task_logger.debug(f"Aggregated worker metrics from {worker_id} (PID {pid}): {wm}")

            task_logger.debug(
                f"Multi-process mode: aggregated {len(processed_workers)} unique worker metrics"
            )'''
    
    if old_pid_processing in content:
        content = content.replace(old_pid_processing, new_pid_processing)
        print("已修复Worker metrics聚合中的PID处理逻辑")
    else:
        print("未找到需要修复的PID处理逻辑")
    
    # 写回文件
    with open(locustfile_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"已修复 {locustfile_path}")

def fix_multiprocess_config():
    """修复多进程配置，增加稳定性"""
    config_path = "st_engine/config/multiprocess.py"
    
    if not os.path.exists(config_path):
        print(f"文件不存在: {config_path}")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 增加更保守的多进程配置
    old_config = '''                "manager_timeout": int(os.environ.get("MANAGER_TIMEOUT", "30")),'''
    
    new_config = '''                "manager_timeout": int(os.environ.get("MANAGER_TIMEOUT", "60")),'''
    
    if old_config in content:
        content = content.replace(old_config, new_config)
        print("已增加manager_timeout到60秒")
    
    # 增加Worker进程稳定性配置
    old_fallback = '''                "fallback_queue_type": os.environ.get(
                    "FALLBACK_QUEUE_TYPE", "gevent"
                ).lower(),'''
    
    new_fallback = '''                "fallback_queue_type": os.environ.get(
                    "FALLBACK_QUEUE_TYPE", "gevent"
                ).lower(),
                "worker_heartbeat_timeout": int(os.environ.get("WORKER_HEARTBEAT_TIMEOUT", "10")),
                "worker_metrics_timeout": int(os.environ.get("WORKER_METRICS_TIMEOUT", "15")),'''
    
    if old_fallback in content:
        content = content.replace(old_fallback, new_fallback)
        print("已增加Worker进程超时配置")
    
    # 写回文件
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"已修复 {config_path}")

def fix_runner_timeout():
    """修复runner.py中的超时配置"""
    runner_path = "st_engine/engine/runner.py"
    
    if not os.path.exists(runner_path):
        print(f"文件不存在: {runner_path}")
        return
    
    with open(runner_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 增加Locust进程的超时时间
    old_timeout = '''        # Calculate a generous timeout for the process to complete.
        # This includes the task duration, Locust's own stop timeout, and an extra buffer.
        locust_stop_timeout_config = 99
        wait_timeout_total = task_duration_seconds + locust_stop_timeout_config + 30'''
    
    new_timeout = '''        # Calculate a generous timeout for the process to complete.
        # This includes the task duration, Locust's own stop timeout, and an extra buffer.
        # Increased timeout for multi-process mode stability
        locust_stop_timeout_config = 99
        wait_timeout_total = task_duration_seconds + locust_stop_timeout_config + 60'''
    
    if old_timeout in content:
        content = content.replace(old_timeout, new_timeout)
        print("已增加Locust进程超时时间")
    
    # 写回文件
    with open(runner_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"已修复 {runner_path}")

def main():
    """主函数"""
    print("开始修复多进程压测问题...")
    
    try:
        fix_locustfile()
        fix_multiprocess_config()
        fix_runner_timeout()
        print("\n所有修复完成！")
        print("\n修复内容总结：")
        print("1. 增强了Worker进程的metrics发送机制，添加重试逻辑")
        print("2. 改进了Master进程的Worker消息处理，使用worker_id作为主标识符")
        print("3. 增加了Worker metrics聚合的等待时间和重试机制")
        print("4. 增加了多进程配置的超时时间")
        print("5. 增加了Locust进程的超时时间")
        print("\n建议的测试配置：")
        print("- 设置环境变量: export WORKER_HEARTBEAT_TIMEOUT=15")
        print("- 设置环境变量: export WORKER_METRICS_TIMEOUT=20")
        print("- 设置环境变量: export MANAGER_TIMEOUT=60")
        
    except Exception as e:
        print(f"修复过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
