<div align="center">
  <img src="docs/images/logo.png" alt="LMeterX Logo" width="400"/>
  <p>
    <a href="README_CN.md">简体中文</a> |
    <strong>English</strong>
  </p>
</div>

# LMeterX

## 📋 Project Overview

LMeterX is a professional large language model performance testing platform that supports comprehensive load testing for any LLM service compatible with the OpenAI API format. Through an intuitive Web interface, users can easily create and manage test tasks, monitor testing processes in real-time, and obtain detailed performance analysis reports, providing reliable data support for model deployment and performance optimization.

<div align="center">
  <img src="docs/images/images.gif" alt="LMeterX Demo" width="800"/>
</div>

## ✨ Core Features

### 🔌 OpenAI API Ecosystem Compatibility
- **Wide Compatibility**: Perfect support for all large language model services following OpenAI API standards
- **Flexible Configuration**: Support for custom API endpoints, models, request headers, authentication methods, and other parameters

### 🎯 Multi-Scenario Test Coverage
- **Text Conversation Testing**: In-depth performance evaluation for pure text conversation scenarios
- **Multimodal Testing**: Professional performance benchmarking for image-text mixed conversations
- **Model Type Support**:
  - General language models (GPT, Claude, Llama, etc.)
  - Reasoning-enhanced models (o1, DeepSeek-R1 and other chain-of-thought models)
  - Vision understanding models (GPT-4V, Claude-3.5-Sonnet, etc.)

### ⚡ Precise Concurrent Load Testing
- **Intelligent Load Control**: Precisely simulate real user concurrent access patterns
- **Flexible Time Control**: Support both short-term burst and long-term stability testing scenarios
- **Progressive Load Adjustment**: Controllable user generation rate to avoid impact on target services

### 📈 Professional Performance Metrics System
- **Latency Performance Analysis**:
  - TTFT (Time to First Token) - Measure model response speed
  - End-to-end response time - Complete request processing duration analysis
- **Throughput Statistics**:
  - RPS (Requests Per Second) - Service processing capability assessment
  - TPS (Tokens Per Second) - Layered token throughput (reasoning/generation/total)
- **Reliability Monitoring**:
  - Error rate statistics and detailed error information collection
  - Success rate trend analysis

### 📊 Real-time Monitoring and Data Visualization
- **Real-time Monitoring**: Full-process real-time monitoring with transparent log tracking
- **Dynamic Charts**: Performance trend visualization with key metrics at a glance
- **Performance Comparison**: Version evolution tracking and horizontal model comparison with multi-metric deep insights
- **Professional Reports**: Automatically generate detailed test reports with data export and in-depth analysis support

### 🌐 Enterprise-Grade Deployment Solutions
- **Cloud-Native Architecture**: Support for deployment on mainstream cloud platforms including Alibaba Cloud, AWS, Azure, Tencent Cloud
- **Elastic Scaling**: Support for multi-replica deployment, enabling parallel execution of multiple tasks and dynamic scaling
- **One-Click Deployment**: Docker Compose rapid deployment, ready to use in 5 minutes
- **Visual Management**: Intuitive Web management console with full lifecycle task management

## 🏗️ System Architecture

LMeterX adopts a microservices architecture design, consisting of four core components:

1. **Backend API Service**: FastAPI-based REST API service responsible for task management and result storage
2. **Load Testing Engine**: Locust-based load testing engine that executes actual performance testing tasks
3. **Frontend Interface**: Modern Web interface based on React + TypeScript + Ant Design
4. **MySQL Database**: Stores test tasks, result data, and configuration information

<div align="center">
  <img src="docs/images/tech-arch.png" alt="LMeterX tech arch" width="800"/>
</div>

## 🚀 Quick Start

### Environment Requirements
- Docker 20.10.0+
- Docker Compose 2.0.0+
- At least 4GB available memory
- At least 5GB available disk space

### One-Click Deployment (Recommended)

> **Complete Deployment Guide**: See [Complete Deployment Guide](docs/DEPLOYMENT_GUIDE.md) for detailed instructions on all deployment methods

Use pre-built Docker images to start all services with one click:

```bash
# Download and run one-click deployment script
curl -fsSL https://raw.githubusercontent.com/LuckyYC/LMeterX/main/quick-start.sh | bash
```
### Usage Guide

1. **Access Web Interface**: http://localhost:8080
2. **Create Test Task**:
   - Configure target API address and model parameters
   - Select test type (text conversation/image-text conversation)
   - Set concurrent user count and test duration
   - Configure other advanced parameters (optional)
3. **Monitor Test Process**: Real-time view of test logs and performance metrics
4. **Analyze Test Results**: View detailed performance analysis reports and export data

## 🔧 Configuration

### Environment Variable Configuration

#### General Configuration
```bash
SECRET_KEY=your_secret_key_here        # Application security key
FLASK_DEBUG=false                      # Debug mode switch
```

#### Database Configuration
```bash
DB_HOST=mysql                          # Database host address
DB_PORT=3306                           # Database port
DB_USER=lmeterx                        # Database username
DB_PASSWORD=lmeterx_password           # Database password
DB_NAME=lmeterx                        # Database name
```

#### Frontend Configuration
```bash
VITE_API_BASE_URL=/api                # API base path
```

## 🤝 Development Guide

> We welcome all forms of contributions! Please read our [Contributing Guide](docs/CONTRIBUTING.md) for details.

### Technology Stack

LMeterX adopts a modern technology stack to ensure system reliability and maintainability:

- **Backend Service**: Python + FastAPI + SQLAlchemy + MySQL
- **Load Testing Engine**: Python + Locust + Custom Extensions
- **Frontend Interface**: React + TypeScript + Ant Design + Vite
- **Deployment & Operations**: Docker + Docker Compose + Nginx

### Project Structure

```
LMeterX/
├── backend/                  # Backend service
├── st_engine/                # Load testing engine service
├── frontend/                 # Frontend service
├── docs/                     # Documentation directory
├── docker-compose.yml        # Docker Compose configuration
├── Makefile                  # Run complete code checks
├── README.md                 # English README
└── README_CN.md              # Chinese README
```

### Development Environment Setup

1. **Fork the Project** to your GitHub account
2. **Clone Your Fork**, create a development branch for development
3. **Follow Code Standards**, use clear commit messages (follow conventional commit standards)
4. **Run Code Checks**: Before submitting PR, ensure code checks, formatting, and tests all pass, you can run `make all`
5. **Write Clear Documentation**: Write corresponding documentation for new features or changes
6. **Actively Participate in Review**: Actively respond to feedback during the review process

## 🗺️ Development Roadmap

### Completed
- [x] OpenAI compatible API testing support
- [x] Pure text and image-text conversation scenario testing
- [x] Basic performance metrics collection and analysis
- [x] Test report export functionality
- [x] Web interface management system
- [x] Docker Compose one-click deployment
- [x] Test result comparison analysis functionality

### In Development
- [ ] Support for custom API paths and performance metrics collection
- [ ] Support for user-defined load test datasets
- [ ] Support for client resource monitoring

### Planned
- [ ] CLI command-line tool
- [ ] User system support

## 📚 Related Documentation

- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) - Detailed deployment instructions and configuration guide
- [Contributing Guide](docs/CONTRIBUTING.md) - How to participate in project development and contribute code

## 🤝 Contributors

Thanks to all developers who have contributed to the LMeterX project:

- [@LuckyYC](https://github.com/LuckyYC) - Project maintainer
- [@Charm](https://github.com/charm) - Core developer
- [@del-zhenwu](https://github.com/del-zhenwu) - Core developer

## 📄 Open Source License

This project is licensed under the [Apache 2.0 License](LICENSE).

---

**⭐ If this project helps you, please give us a Star! Your support is our motivation for continuous improvement.**
