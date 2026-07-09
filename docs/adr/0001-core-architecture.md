# ADR 0001: 核心架构选型

日期：2026-07-09

## 决策

采用 FastAPI + React + PostgreSQL + Redis/Celery + Docker Compose。

## 原因

- FastAPI 与 Python 生态适合 OCR、文件、PDF、导出和 SDK 接入。
- React SPA 适合上传队列、发票列表、详情校对和批量操作。
- PostgreSQL 支持 JSONB、索引、审计和多用户并发。
- Redis/Celery 适合异步 OCR、限流和重试。
- Compose 在保持部署简单的同时明确 app、worker、db、queue 边界。

## 后果

部署需要多个容器，但用户仍只面对一个业务镜像和一份基础设施 `.env`。OCR 运营商凭据不进入 `.env`，由管理员在系统设置页配置并加密保存。后续可以扩展对象存储、SSO、查验接口、多 OCR 运营商和横向 worker。
