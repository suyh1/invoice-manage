# 发票集中存储与腾讯云 OCR 识别系统

本仓库当前处于初始设计阶段。项目目标是在 `linux x86_64` 架构上交付可私有化部署的 Docker 镜像，用于集中存储、管理、识别出差、采购、餐饮、交通、住宿等场景的发票。

识别能力对接腾讯云 OCR `VatInvoiceOCR`。部署用户只需要填写腾讯云 `SecretId` 和 `SecretKey`，系统内部固定封装腾讯云 OCR 的 endpoint、Action、Version、文件限制、异步队列、限流、错误映射和结果归一化。

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
- OCR：Tencent Cloud SDK 3.0，接口 `VatInvoiceOCR`
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

后续项目实现必须以 `docs/` 下文档为准。

