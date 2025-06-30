"""
测试自定义API的prompt更新功能
"""

import json
import unittest
from queue import Queue
from unittest.mock import Mock, patch

from engine.locustfile import GLOBAL_CONFIG, ConfigManager, LLMTestUser


class TestCustomApiPromptUpdate(unittest.TestCase):
    """测试自定义API的prompt更新功能"""

    def setUp(self):
        """设置测试环境"""
        # 重置全局配置
        GLOBAL_CONFIG.task_id = "test_task"
        GLOBAL_CONFIG.api_path = "/custom/api"
        GLOBAL_CONFIG.request_payload = json.dumps(
            {"model": "test-model", "input": "original_prompt", "temperature": 0.7}
        )
        GLOBAL_CONFIG.field_mapping = json.dumps(
            {
                "prompt": "input",
                "content": "output.text",
                "stream_prefix": "data:",
                "stop_flag": "[DONE]",
            }
        )

        # 创建模拟的用户实例
        self.user = LLMTestUser()
        self.user.environment = Mock()
        self.user.environment.prompt_queue = Queue()

        # 添加测试prompt到队列
        self.user.environment.prompt_queue.put(("test_id", "这是测试prompt"))

    def test_prepare_custom_api_request_with_prompt_update(self):
        """测试自定义API请求中的prompt更新功能"""
        task_logger = Mock()

        # 调用准备请求的方法
        request_kwargs, prompt_content = self.user._prepare_custom_api_request(
            task_logger
        )

        # 验证返回值不为空
        self.assertIsNotNone(request_kwargs)
        self.assertIsNotNone(prompt_content)

        # 验证payload中的prompt已被更新
        payload = request_kwargs["json"]
        self.assertEqual(payload["input"], "这是测试prompt")

        # 验证其他字段保持不变
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["temperature"], 0.7)

        # 验证返回的prompt内容正确
        self.assertEqual(prompt_content, "这是测试prompt")

    def test_prepare_custom_api_request_with_nested_field(self):
        """测试嵌套字段的prompt更新"""
        # 设置嵌套字段的payload
        GLOBAL_CONFIG.request_payload = json.dumps(
            {
                "messages": [{"role": "user", "content": "original_content"}],
                "model": "test-model",
            }
        )
        GLOBAL_CONFIG.field_mapping = json.dumps({"prompt": "messages.0.content"})

        task_logger = Mock()

        # 调用准备请求的方法
        request_kwargs, prompt_content = self.user._prepare_custom_api_request(
            task_logger
        )

        # 验证嵌套字段被正确更新
        payload = request_kwargs["json"]
        self.assertEqual(payload["messages"][0]["content"], "这是测试prompt")

    def test_prepare_custom_api_request_without_field_mapping(self):
        """测试没有field_mapping配置的情况"""
        GLOBAL_CONFIG.field_mapping = ""

        task_logger = Mock()

        # 调用准备请求的方法
        request_kwargs, prompt_content = self.user._prepare_custom_api_request(
            task_logger
        )

        # 验证原始payload保持不变
        payload = request_kwargs["json"]
        self.assertEqual(payload["input"], "original_prompt")

        # 验证会记录warning日志
        task_logger.warning.assert_called_with(
            "No prompt field mapping configured, using original payload"
        )

    def test_prepare_custom_api_request_with_multimodal_data(self):
        """测试多模态数据的处理"""
        # 清空队列并添加多模态数据
        while not self.user.environment.prompt_queue.empty():
            self.user.environment.prompt_queue.get()

        multimodal_data = {
            "prompt": "描述这张图片",
            "image_base64": "base64_encoded_image_data",
        }
        self.user.environment.prompt_queue.put(("multimodal_id", multimodal_data))

        task_logger = Mock()

        # 调用准备请求的方法
        request_kwargs, prompt_content = self.user._prepare_custom_api_request(
            task_logger
        )

        # 验证只提取了文本prompt部分
        payload = request_kwargs["json"]
        self.assertEqual(payload["input"], "描述这张图片")
        self.assertEqual(prompt_content, "描述这张图片")

    def test_set_field_value_simple_field(self):
        """测试设置简单字段值"""
        data = {"field1": "value1", "field2": "value2"}
        self.user._set_field_value(data, "field1", "new_value")
        self.assertEqual(data["field1"], "new_value")

    def test_set_field_value_nested_field(self):
        """测试设置嵌套字段值"""
        data = {"level1": {"level2": {"target": "old_value"}}}
        self.user._set_field_value(data, "level1.level2.target", "new_value")
        self.assertEqual(data["level1"]["level2"]["target"], "new_value")

    def test_set_field_value_array_index(self):
        """测试设置数组索引字段值"""
        data = {"messages": [{"content": "old_content"}, {"content": "other_content"}]}
        self.user._set_field_value(data, "messages.0.content", "new_content")
        self.assertEqual(data["messages"][0]["content"], "new_content")
        # 验证其他元素未被修改
        self.assertEqual(data["messages"][1]["content"], "other_content")


if __name__ == "__main__":
    unittest.main()
