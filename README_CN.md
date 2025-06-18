<div align="center">
  <img src="docs/images/logo.png" alt="LMeterX Logo" width="400"/>
  <p>
    <strong>简体中文</strong> |
    <a href="README.md">English</a>
  </p>
</div>

# LMeterX

## 📋 项目简介

LMeterX 是一个专业的大语言模型性能测试平台，支持对任何兼容 OpenAI API 格式的 LLM 服务进行全面的负载测试。通过直观的 Web 界面，用户可以轻松创建和管理测试任务，实时监控测试过程，并获得详细的性能分析报告，为模型部署和性能优化提供可靠的数据支撑。

<div align="center">
  <img src="docs/images/images.gif" alt="LMeterX Demo" width="800"/>
</div>

## ✨ 核心功能

### 🔌 OpenAI API 生态兼容
- **广泛兼容**：完美支持所有遵循 OpenAI API 标准的大语言模型服务
- **灵活配置**：支持自定义 API 端点、模型、请求头、认证方式等参数

### 🎯 多场景测试覆盖
- **文本对话测试**：针对纯文本对话场景的深度性能评估
- **多模态测试**：支持图文混合对话的专业性能基准测试
- **模型类型支持**：
  - 通用语言模型（GPT、Claude、Llama 等）
  - 推理增强模型（o1、DeepSeek-R1 等思维链模型）
  - 视觉理解模型（GPT-4V、Claude-3.5-Sonnet 等）

### ⚡ 精准并发压力测试
- **智能负载控制**：精确模拟真实用户并发访问模式
- **灵活时间控制**：支持短期突发和长期稳定性测试场景
- **渐进式压力调节**：可控的用户生成速率，避免对目标服务造成冲击

### 📈 专业性能指标体系
- **延迟性能分析**：
  - TTFT（首 Token 延迟）- 衡量模型响应速度
  - 端到端响应时间 - 完整请求处理耗时分析
- **吞吐量统计**：
  - RPS（每秒请求数）- 服务处理能力评估
  - TPS（每秒 Token 数）- 分层 Token 吞吐量（推理/生成/总计）
- **可靠性监控**：
  - 错误率统计和错误信息详细收集
  - 成功率趋势分析

### 📊 实时监控与数据可视化
- **实时监控**：测试过程全程实时监控，日志透明化追踪
- **动态图表**：性能趋势可视化展示，关键指标一目了然
- **性能对比**：版本演进追踪与模型横向对比，多指标深度洞察
- **专业报告**：自动生成详细测试报告，支持数据导出和深度分析

### 🌐 企业级部署方案
- **云原生架构**：支持阿里云、AWS、Azure、腾讯云等主流云平台部署
- **弹性扩展**：支持多副本部署，实现多任务并行执行和动态扩容
- **一键部署**：Docker Compose 快速部署，5分钟即可上手使用
- **可视化管理**：直观的 Web 管理控制台，全流程任务管理

## 🏗️ 系统架构

LMeterX 采用微服务架构设计，由以下四个核心组件构成：

1. **后端 API 服务**：基于 FastAPI 的 REST API 服务，负责任务管理和结果存储
2. **压测引擎**：基于 Locust 的负载测试引擎，执行实际的性能测试任务
3. **前端界面**：基于 React + TypeScript + Ant Design 的现代化 Web 界面
4. **MySQL 数据库**：存储测试任务、结果数据和配置信息

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
# 下载并运行一键部署脚本
curl -fsSL https://raw.githubusercontent.com/LuckyYC/LMeterX/main/quick-start.sh | bash
```

### 使用指南

1. **访问 Web 界面**：http://localhost:8080
2. **创建测试任务**：
   - 配置目标 API 地址和模型参数
   - 选择测试类型（文本对话/图文对话）
   - 设置并发用户数和测试持续时间
   - 配置其他高级参数（可选）
3. **监控测试过程**：实时查看测试日志和性能指标
4. **分析测试结果**：查看详细的性能分析报告并导出数据

## 🔧 配置说明

### 环境变量配置

#### 通用配置
```bash
SECRET_KEY=your_secret_key_here        # 应用安全密钥
FLASK_DEBUG=false                      # 调试模式开关
```

#### 数据库配置
```bash
DB_HOST=mysql                         # 数据库主机地址
DB_PORT=3306                          # 数据库端口
DB_USER=lmeterx                       # 数据库用户名
DB_PASSWORD=lmeterx_password          # 数据库密码
DB_NAME=lmeterx                       # 数据库名称
```

#### 前端配置
```bash
VITE_API_BASE_URL=/api                # API 基础路径
```

## 🤝 开发指南

> 我们欢迎所有形式的贡献！请阅读我们的 [贡献指南](docs/CONTRIBUTING.md) 了解详情。

### 技术栈

LMeterX 采用现代化的技术栈，确保系统的可靠性和可维护性：

- **后端服务**：Python + FastAPI + SQLAlchemy + MySQL
- **压测引擎**：Python + Locust + 自定义扩展
- **前端界面**：React + TypeScript + Ant Design + Vite
- **部署运维**：Docker + Docker Compose + Nginx

### 项目结构

```LMeterX/
├── backend/                  # 后端服务
├── st_engine/                # 压测引擎服务
├── frontend/                 # 前端服务
├── docs/                     # 文档目录
├── docker-compose.yml        # Docker Compose配置
├── Makefile                  # 运行完整代码检查
├── README.md                 # 英文README
└── README_CN.md              # 中文README
```

### 开发环境搭建

1. **Fork 项目**到您的 GitHub 账户
2. **克隆您的 Fork**，创建开发分支进行开发
3. **遵循代码规范**，使用清晰的提交信息（遵循约定式提交规范）
4. **运行代码检查**：在提交 PR 之前，确保代码检查、格式化和测试均已通过，可执行 `make all`
5. **编写清晰文档**：为新功能或变更撰写相应的文档
6. **积极参与 Review**：在审核过程中积极响应反馈

## 🗺️ 发展路线图

### 已完成
- [x] OpenAI 兼容 API 测试支持
- [x] 纯文本和图文对话场景测试
- [x] 基础性能指标收集和分析
- [x] 测试报告导出功能
- [x] Web 界面管理系统
- [x] Docker Compose 一键部署
- [x] 测试结果对比分析功能

### 开发中
- [ ] 支持自定义 API 路径和性能指标收集
- [ ] 支持用户自定义压测数据集
- [ ] 支持客户端资源监控

### 规划中
- [ ] CLI 命令行工具
- [ ] 用户系统支持

## 📚 相关文档

- [部署指南](docs/DEPLOYMENT_GUIDE_CN.md) - 详细的部署说明和配置指南
- [贡献指南](docs/CONTRIBUTING.md) - 如何参与项目开发和贡献代码

## 🤝 贡献者

感谢所有为 LMeterX 项目做出贡献的开发者：

- [@LuckyYC](https://github.com/LuckyYC) - 项目维护者
- [@Charm](https://github.com/charm) - 核心开发者
- [@del-zhenwu](https://github.com/del-zhenwu) - 核心开发者

## 📄 开源许可

本项目采用 [Apache 2.0 许可证](LICENSE)。

---

**⭐ 如果这个项目对您有帮助，请给我们一个 Star！您的支持是我们持续改进的动力。**
