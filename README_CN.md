<div align="center">
  <img src="docs/images/logo.png" alt="LMeterX Logo" width="400"/>
  <p>
    <strong>简体中文</strong> |
    <a href="README.md">English</a>
  </p>
</div>

# LMeterX

## 📋 项目简介

LMeterX 是一个专业的大语言模型性能测试平台，支持对 LLM 服务进行全面的负载测试。通过直观的 Web 界面，用户可以轻松创建和管理测试任务，实时监控测试过程，并获得详细的性能分析报告，为模型部署和性能优化提供可靠的数据支撑。

<div align="center">
  <img src="docs/images/images.gif" alt="LMeterX Demo" width="700"/>
</div>

## ✨ 核心特性

- **全模型兼容** - 支持 GPT、Claude、Llama 等主流大模型，一键发起压测
- **高负载压测** - 模拟高并发请求，精准探测模型性能极限
- **多场景覆盖** - 支持流式/非流式、文本/多模态/自定义数据集<sup>![NEW](https://img.shields.io/badge/NEW-brightgreen?style=flat-square)</sup>
- **专业指标统计** - 首Token延迟、吞吐量(RPS、TPS)、成功率等核心性能指标
- **AI智能报告** - AI智能分析报告<sup>![NEW](https://img.shields.io/badge/NEW-brightgreen?style=flat-square)</sup>，多维度多模型可视化结果对比
- **Web控制台** - 提供任务创建、停止、状态跟踪、全链路日志监控等一站式管理
- **企业级部署** - Docker容器化，支持弹性扩展与分布式部署

## 🏗️ 系统架构

LMeterX 采用微服务架构，由四个核心组件构成：

- **后端API服务** - FastAPI REST API，负责任务管理和数据存储
- **压测引擎** - Locust负载测试引擎，执行性能测试任务
- **前端界面** - React + TypeScript + Ant Design 现代化Web界面
- **MySQL数据库** - 存储测试任务、结果数据和配置信息

<div align="center">
  <img src="docs/images/tech-arch.png" alt="LMeterX tech arch" width="800"/>
</div>

## 🚀 快速开始

### 环境要求
- Docker 20.10.0+
- Docker Compose 2.0.0+
- 至少 4GB 可用内存
- 至少 5GB 可用磁盘空间

### 一键部署（推荐）

> **完整部署指南**：查看 [完整部署指南](docs/DEPLOYMENT_GUIDE_CN.md) 了解所有部署方式的详细说明

使用预构建的 Docker 镜像，一键启动所有服务：

```bash
# 一键启动所有服务
curl -fsSL https://raw.githubusercontent.com/MigoXLab/LMeterX/main/quick-start.sh | bash
```

### 使用指南

1. **访问界面** - 打开 http://localhost:8080
2. **创建任务** - 配置API地址、模型参数、测试类型
3. **实时监控** - 查看测试日志和性能指标
4. **结果分析** - 查看详细性能结果，导出报告
5. **AI分析** - 配置AI服务后，获得智能性能评估

## 🔧 配置说明

### 环境变量

```bash
# 通用配置
SECRET_KEY=your_secret_key_here
FLASK_DEBUG=false

# 数据库配置
DB_HOST=mysql
DB_PORT=3306
DB_USER=lmeterx
DB_PASSWORD=lmeterx_password
DB_NAME=lmeterx

# 前端配置
VITE_API_BASE_URL=/api
```

## 🤝 开发指南

> 💡 **欢迎贡献**！查看 [贡献指南](docs/CONTRIBUTING.md) 了解详情

### 技术栈

- **后端** - Python + FastAPI + SQLAlchemy + MySQL
- **压测引擎** - Python + Locust + 自定义扩展
- **前端** - React + TypeScript + Ant Design + Vite
- **部署** - Docker + Docker Compose + Nginx


```
LMeterX/
├── backend/          # 后端服务
├── st_engine/        # 压测引擎
├── frontend/         # 前端服务
├── docs/             # 文档
├── docker-compose.yml
└── README_CN.md      # 中文说明
```

### 开发环境搭建

1. **Fork项目** → 克隆到本地
2. **创建分支** → 进行功能开发
3. **代码检查** → 运行 `make all` 确保质量
4. **提交PR** → 遵循约定式提交规范
5. **文档更新** → 为新功能撰写文档

## 🗺️ 发展路线图

### 开发中
- [ ] 支持客户端资源监控

### 规划中
- [ ] CLI 命令行工具

## 📚 相关文档

- [部署指南](docs/DEPLOYMENT_GUIDE_CN.md) - 详细部署说明
- [贡献指南](docs/CONTRIBUTING.md) - 参与开发指南

## 👥 贡献者

感谢所有为 LMeterX 做出贡献的开发者：

- [@LuckyYC](https://github.com/LuckyYC) - 项目维护者 & 核心开发者
- [@del-zhenwu](https://github.com/del-zhenwu) - 核心开发者

## 📄 开源许可

本项目采用 [Apache 2.0 许可证](LICENSE)。

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给我们一个 Star！您的支持是我们持续改进的动力。**

</div>
