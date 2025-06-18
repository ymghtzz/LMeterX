from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class TaskResult(Base):
    __tablename__ = "task_results"
    __table_args__ = (Index("idx_task_id", "task_id"),)
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    task_id = Column(String(36), nullable=False, comment="任务ID")
    metric_type = Column(String(36), comment="指标类型")
    num_requests = Column(Integer, default=0, comment="请求总数量")
    num_failures = Column(Integer, default=0, comment="请求失败数量")
    avg_latency = Column(Float, default=0, comment="请求平均响应时间")
    min_latency = Column(Float, default=0, comment="请求最小响应时间")
    max_latency = Column(Float, default=0, comment="请求最大响应时间")
    median_latency = Column(Float, default=0, comment="请求中位响应时间")
    p90_latency = Column(Float, default=0, comment="请求90%响应时间")
    rps = Column(Float, default=0, comment="每秒请求数")
    avg_content_length = Column(Float, default=0, comment="平均输出的字符长度")
    completion_tps = Column(Float, default=0, comment="每秒输出的token数量")
    total_tps = Column(Float, default=0, comment="每秒输入输出的总token数量")
    avg_total_tokens_per_req = Column(
        Float, default=0, comment="每个请求的平均输入输出的总token数量"
    )
    avg_completion_tokens_per_req = Column(
        Float, default=0, comment="每个请求的平均输出token数量"
    )

    created_at = Column(DateTime, default=datetime.now(timezone(timedelta(hours=8))))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone(timedelta(hours=8))),
        onupdate=datetime.now(timezone(timedelta(hours=8))),
    )
