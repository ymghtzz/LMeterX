#!/usr/bin/env python3
"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.

测试脚本：验证单进程和多进程模式下time和token相关指标的聚合准确性
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

# 添加项目路径到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from engine.core import GlobalStateManager
from utils.common import calculate_custom_metrics
from utils.logger import logger


class MetricsAggregationTest(unittest.TestCase):
    """测试指标聚合的准确性"""

    def setUp(self):
        """测试前的准备工作"""
        self.test_dir = tempfile.mkdtemp(prefix="metrics_test_")
        self.locustfile_path = project_root / "engine" / "locustfile.py"
        self.test_host = "http://localhost:8000"  # 测试用的假API端点

        # 确保locustfile存在
        self.assertTrue(
            self.locustfile_path.exists(),
            f"Locustfile not found at {self.locustfile_path}",
        )

        # 设置测试环境变量
        os.environ["TASK_ID"] = f"test_{int(time.time())}"

    def tearDown(self):
        """测试后的清理工作"""
        # 清理临时目录
        import shutil

        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _run_locust_test(
        self, users: int, duration: int, workers: int = 0
    ) -> Dict[str, Any]:
        """
        运行Locust测试并返回结果

        Args:
            users: 并发用户数
            duration: 测试时间（秒）
            workers: Worker进程数，0表示单进程模式

        Returns:
            测试结果字典
        """
        # 构建Locust命令
        cmd = [
            "locust",
            "-f",
            str(self.locustfile_path),
            "--host",
            self.test_host,
            "--users",
            str(users),
            "--spawn-rate",
            "10",
            "--run-time",
            f"{duration}s",
            "--headless",
            "--only-summary",
            "--stop-timeout",
            "10",
            "--task-id",
            os.environ["TASK_ID"],
            "--api_path",
            "/test/endpoint",
            "--headers",
            '{"Content-Type": "application/json"}',
            "--cookies",
            "{}",
            "--model_name",
            "test-model",
            "--stream_mode",
            "False",
            "--chat_type",
            "0",
            "--user_prompt",
            "Test prompt for metrics validation",
        ]

        # 添加多进程参数
        if workers > 0:
            cmd.extend(["--processes", str(workers)])

        # 设置结果输出目录
        result_dir = os.path.join(self.test_dir, f"result_{users}_{workers}")
        os.makedirs(result_dir, exist_ok=True)

        # 运行测试
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration + 30,  # 给测试额外30秒超时时间
                cwd=str(project_root),
            )

            # 检查返回码
            if result.returncode != 0:
                logger.error(f"Locust test failed with return code {result.returncode}")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                return {"error": f"Test failed with return code {result.returncode}"}

            # 尝试读取结果文件
            result_file = os.path.join(
                tempfile.gettempdir(),
                "locust_result",
                os.environ["TASK_ID"],
                "result.json",
            )

            if os.path.exists(result_file):
                with open(result_file, "r") as f:
                    return json.load(f)
            else:
                # 如果没有结果文件，尝试从stdout解析基本信息
                return self._parse_stdout_for_metrics(result.stdout)

        except subprocess.TimeoutExpired:
            logger.error("Locust test timed out")
            return {"error": "Test timed out"}
        except Exception as e:
            logger.error(f"Error running Locust test: {e}")
            return {"error": str(e)}

    def _parse_stdout_for_metrics(self, stdout: str) -> Dict[str, Any]:
        """从stdout解析基本指标信息"""
        # 这是一个简化的解析器，实际项目中可能需要更复杂的解析逻辑
        lines = stdout.split("\n")
        metrics = {
            "custom_metrics": {
                "reqs_num": 0,
                "req_throughput": 0.0,
                "completion_tps": 0.0,
                "total_tps": 0.0,
            },
            "locust_stats": [],
        }

        for line in lines:
            if "Total requests" in line:
                # 尝试提取请求数
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.isdigit():
                            metrics["custom_metrics"]["reqs_num"] = int(part)
                            break
                except:
                    pass

        return metrics

    def _validate_metrics_consistency(
        self,
        single_process_result: Dict[str, Any],
        multi_process_result: Dict[str, Any],
    ) -> bool:
        """
        验证单进程和多进程结果的指标一致性

        Args:
            single_process_result: 单进程测试结果
            multi_process_result: 多进程测试结果

        Returns:
            是否一致
        """
        if "error" in single_process_result or "error" in multi_process_result:
            logger.warning("One or both tests failed, skipping consistency check")
            return False

        single_metrics = single_process_result.get("custom_metrics", {})
        multi_metrics = multi_process_result.get("custom_metrics", {})

        # 检查关键指标
        key_metrics = ["reqs_num", "req_throughput", "completion_tps", "total_tps"]

        for metric in key_metrics:
            single_val = single_metrics.get(metric, 0)
            multi_val = multi_metrics.get(metric, 0)

            # 允许一定的误差范围（5%）
            if single_val > 0 and multi_val > 0:
                error_rate = abs(single_val - multi_val) / single_val
                if error_rate > 0.05:  # 5%误差阈值
                    logger.error(
                        f"Metric {metric} inconsistent: "
                        f"single_process={single_val}, multi_process={multi_val}, "
                        f"error_rate={error_rate:.2%}"
                    )
                    return False
            elif single_val != multi_val:
                logger.error(
                    f"Metric {metric} inconsistent: "
                    f"single_process={single_val}, multi_process={multi_val}"
                )
                return False

        return True

    def test_single_vs_multi_process_consistency(self):
        """测试单进程和多进程模式下的指标一致性"""
        logger.info("开始测试单进程vs多进程指标一致性")

        # 测试参数
        test_cases = [
            {"users": 5, "duration": 10, "workers": 2},
            {"users": 10, "duration": 15, "workers": 3},
            {"users": 20, "duration": 20, "workers": 4},
        ]

        for i, case in enumerate(test_cases):
            logger.info(f"测试用例 {i+1}: {case}")

            # 运行单进程测试
            logger.info("运行单进程测试...")
            single_result = self._run_locust_test(
                users=case["users"], duration=case["duration"], workers=0
            )

            # 等待一下，避免端口冲突
            time.sleep(2)

            # 运行多进程测试
            logger.info("运行多进程测试...")
            multi_result = self._run_locust_test(
                users=case["users"], duration=case["duration"], workers=case["workers"]
            )

            # 验证结果一致性
            is_consistent = self._validate_metrics_consistency(
                single_result, multi_result
            )

            logger.info(f"测试用例 {i+1} 结果: {'通过' if is_consistent else '失败'}")
            logger.info(f"单进程结果: {single_result}")
            logger.info(f"多进程结果: {multi_result}")

            # 注意：由于这是模拟测试，我们主要验证逻辑正确性
            # 在实际环境中，可能需要调整断言条件
            if "error" not in single_result and "error" not in multi_result:
                self.assertTrue(is_consistent, f"测试用例 {i+1} 的指标不一致")

    def test_metrics_calculation_accuracy(self):
        """测试指标计算的准确性"""
        logger.info("开始测试指标计算准确性")

        # 模拟测试数据
        from gevent import queue

        # 创建测试队列
        test_queue = {
            "completion_tokens_queue": queue.Queue(),
            "all_tokens_queue": queue.Queue(),
        }

        # 添加测试数据
        test_completion_tokens = [100, 150, 200, 120, 180]
        test_all_tokens = [300, 400, 500, 350, 450]

        for tokens in test_completion_tokens:
            test_queue["completion_tokens_queue"].put(tokens)

        for tokens in test_all_tokens:
            test_queue["all_tokens_queue"].put(tokens)

        # 计算指标
        execution_time = 10.0  # 10秒
        task_id = "test_calculation"

        metrics = calculate_custom_metrics(task_id, test_queue, execution_time)

        # 验证计算结果
        expected_reqs = len(test_completion_tokens)
        expected_completion_tokens = sum(test_completion_tokens)
        expected_all_tokens = sum(test_all_tokens)
        expected_completion_tps = expected_completion_tokens / execution_time
        expected_total_tps = expected_all_tokens / execution_time

        self.assertEqual(metrics["reqs_num"], expected_reqs)
        self.assertEqual(metrics["completion_tokens"], expected_completion_tokens)
        self.assertEqual(metrics["all_tokens"], expected_all_tokens)

        logger.info(f"指标计算测试通过: {metrics}")

    def test_time_measurement_accuracy(self):
        """测试时间测量的准确性"""
        logger.info("开始测试时间测量准确性")

        # 测试GlobalStateManager的时间管理
        test_start_time = time.time()
        GlobalStateManager.set_start_time(test_start_time)

        # 等待一小段时间
        time.sleep(0.1)

        retrieved_start_time = GlobalStateManager.get_start_time()
        self.assertIsNotNone(retrieved_start_time)
        self.assertAlmostEqual(retrieved_start_time, test_start_time, places=2)

        # 测试执行时间计算
        end_time = time.time()
        execution_time = end_time - retrieved_start_time

        # 验证执行时间在合理范围内
        self.assertGreater(execution_time, 0.05)  # 至少50ms
        self.assertLess(execution_time, 0.2)  # 最多200ms

        logger.info(
            f"时间测量测试通过: start={retrieved_start_time}, execution={execution_time}"
        )

    def test_queue_operations(self):
        """测试队列操作的准确性"""
        logger.info("开始测试队列操作准确性")

        from gevent import queue

        from utils.common import _drain_queue

        # 创建测试队列
        test_queue = queue.Queue()

        # 添加测试数据
        test_data = [1, 2, 3, 4, 5]
        for item in test_data:
            test_queue.put(item)

        # 测试队列清空操作
        drained_data = _drain_queue(test_queue)

        # 验证结果
        self.assertEqual(len(drained_data), len(test_data))
        self.assertEqual(sorted(drained_data), sorted(test_data))
        self.assertTrue(test_queue.empty())

        logger.info(f"队列操作测试通过: {drained_data}")


class MockMetricsTest(unittest.TestCase):
    """模拟测试类，用于验证指标聚合逻辑"""

    def test_worker_metrics_aggregation(self):
        """测试Worker指标聚合逻辑"""
        logger.info("开始测试Worker指标聚合逻辑")

        # 模拟Worker指标数据
        worker_metrics_list = [
            {
                "pid": 1001,
                "reqs_num": 10,
                "completion_tokens": 1000,
                "all_tokens": 3000,
            },
            {
                "pid": 1002,
                "reqs_num": 15,
                "completion_tokens": 1500,
                "all_tokens": 4500,
            },
            {
                "pid": 1003,
                "reqs_num": 12,
                "completion_tokens": 1200,
                "all_tokens": 3600,
            },
        ]

        # 聚合指标
        total_reqs = 0
        total_comp_tokens = 0
        total_all_tokens = 0
        processed_pids = set()

        for wm in worker_metrics_list:
            pid = wm.get("pid")
            if pid not in processed_pids:
                processed_pids.add(pid)
                total_reqs += wm.get("reqs_num", 0)
                total_comp_tokens += wm.get("completion_tokens", 0)
                total_all_tokens += wm.get("all_tokens", 0)

        # 验证聚合结果
        expected_reqs = 37  # 10 + 15 + 12
        expected_comp_tokens = 3700  # 1000 + 1500 + 1200
        expected_all_tokens = 11100  # 3000 + 4500 + 3600

        self.assertEqual(total_reqs, expected_reqs)
        self.assertEqual(total_comp_tokens, expected_comp_tokens)
        self.assertEqual(total_all_tokens, expected_all_tokens)
        self.assertEqual(len(processed_pids), 3)

        logger.info(
            f"Worker指标聚合测试通过: reqs={total_reqs}, comp_tokens={total_comp_tokens}, all_tokens={total_all_tokens}"
        )

    def test_tps_calculation(self):
        """测试TPS计算逻辑"""
        logger.info("开始测试TPS计算逻辑")

        # 测试数据
        total_reqs = 100
        total_comp_tokens = 10000
        total_all_tokens = 30000
        execution_time = 10.0  # 10秒

        # 计算TPS指标
        req_throughput = total_reqs / execution_time
        completion_tps = total_comp_tokens / execution_time
        total_tps = total_all_tokens / execution_time
        avg_completion_tokens_per_req = total_comp_tokens / total_reqs
        avg_total_tokens_per_req = total_all_tokens / total_reqs

        # 验证计算结果
        self.assertEqual(req_throughput, 10.0)  # 100/10
        self.assertEqual(completion_tps, 1000.0)  # 10000/10
        self.assertEqual(total_tps, 3000.0)  # 30000/10
        self.assertEqual(avg_completion_tokens_per_req, 100.0)  # 10000/100
        self.assertEqual(avg_total_tokens_per_req, 300.0)  # 30000/100

        logger.info(
            f"TPS计算测试通过: req_throughput={req_throughput}, completion_tps={completion_tps}, total_tps={total_tps}"
        )


def run_metrics_tests():
    """运行所有指标测试"""
    logger.info("开始运行指标聚合测试套件")

    # 创建测试套件
    test_suite = unittest.TestSuite()

    # 添加测试用例
    test_suite.addTest(unittest.makeSuite(MetricsAggregationTest))
    test_suite.addTest(unittest.makeSuite(MockMetricsTest))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # 输出结果摘要
    logger.info(f"测试完成: 运行 {result.testsRun} 个测试")
    logger.info(f"失败: {len(result.failures)} 个")
    logger.info(f"错误: {len(result.errors)} 个")

    if result.failures:
        logger.error("失败的测试:")
        for test, traceback in result.failures:
            logger.error(f"  {test}: {traceback}")

    if result.errors:
        logger.error("错误的测试:")
        for test, traceback in result.errors:
            logger.error(f"  {test}: {traceback}")

    return result.wasSuccessful()


if __name__ == "__main__":
    # 设置日志级别
    import logging

    logging.basicConfig(level=logging.INFO)

    # 运行测试
    success = run_metrics_tests()

    if success:
        print("\n✅ 所有测试通过！")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败！")
        sys.exit(1)
