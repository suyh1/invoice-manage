# 发票集中存储与多运营商 OCR 识别系统

本仓库当前处于初始设计阶段。项目目标是在 `linux x86_64` 架构上交付可私有化部署的 Docker 镜像，用于集中存储、管理、识别出差、采购、餐饮、交通、住宿等场景的发票。

识别能力采用可扩展 OCR 运营商适配层。MVP 默认接入腾讯云 OCR `VatInvoiceOCR`，但管理员在系统设置页配置运营商、密钥、限流和免费额度提醒阈值；部署环境变量只保留数据库、Redis、应用密钥、存储路径等基础设施配置。后续可在同一适配层接入阿里云等 OCR 服务。

## 文档入口

- [完整设计文档](docs/design/01-overall-design.md)
- [数据模型与 API 设计](docs/design/02-api-data-model.md)
- [Linux x86_64 Docker 部署指南](docs/deployment/linux-amd64-docker-deployment.md)
- [后续实现计划](docs/plans/2026-07-09-invoice-ocr-implementation-plan.md)
- [腾讯云 OCR 官方约束调研](docs/research/tencent-cloud-ocr-notes.md)

## 核心技术栈

- 后端：Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic
- 前端：React + Vite + TypeScript
- 数据库：PostgreSQL
- 异步任务与限流：Redis + Celery
- 文件存储：Docker volume 本地文件存储，预留 S3/MinIO/COS 扩展接口
- OCR：多运营商适配层，MVP 使用 Tencent Cloud SDK 3.0 和 `VatInvoiceOCR`
- 交付：单业务镜像，多进程 compose 拓扑，目标平台 `linux/amd64`

## MVP 闭环

上传发票 -> 本地预校验 -> 异步 OCR -> 保存原始响应和标准字段 -> 人工校对 -> 重复检测 -> 检索归档 -> 导出。

## 关键约束

- 腾讯云 OCR endpoint：`ocr.tencentcloudapi.com`
- Action：`VatInvoiceOCR`
- Version：`2018-11-19`
- 默认频率：`10 次/秒`
- 支持文件：PNG、JPG、JPEG、PDF
- 不支持：GIF
- Base64 后文件大小不超过 10MB
- 图片像素宽高范围：20-10000px
- PDF 需设置 `IsPdf=true`，一期仅支持单页识别
- 识别结果必须保存 `VatInvoiceInfos`、`Items`、`PdfPageSize`、`Angle`、`RequestId`
- OCR 凭据不得通过 `.env` 或 Docker `environment` 配置，必须由管理员在系统设置页录入、测试和轮换
- 设置页必须展示 OCR 免费额度或资源包余量状态，并在接近用完前通知管理员和财务用户

后续项目实现必须以 `docs/` 下文档为准。
