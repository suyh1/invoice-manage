# 发票集中存储与多运营商 OCR 识别系统

这是一个已实现的私有化发票管理应用，面向企业内部的发票上传、项目归档、OCR 识别、人工校对、重复检测与结构化导出。应用提供 React 前端、FastAPI API、Celery 异步任务、PostgreSQL、Redis 和 `linux/amd64` Docker 镜像。

## 已实现功能

- 首次访问通过落地页创建第一位管理员，之后关闭公开注册
- 管理员创建和维护用户，支持普通用户、财务、管理员三种固定角色
- 系统内置不可修改的“未分类”项目，支持私有项目与共享项目
- 上传时选择项目；未选择时自动归入“未分类”
- PNG、JPG、JPEG、单页 PDF 上传与异步 OCR
- 发票字段、明细行校对，重复发票提示与确认
- 待校对队列、批量确认、重新识别
- 按项目、状态、日期等条件筛选并导出 JSON、CSV、XLSX
- Dashboard、OCR 运营商配置、额度提醒和审计记录

## 角色与权限

| 角色 | 发票范围 | 项目能力 | 管理能力 |
|---|---|---|---|
| 普通用户 | 自己上传的发票 | 创建自己的私有项目，使用共享项目 | 无用户和 OCR 设置权限 |
| 财务 | 全部发票 | 创建私有或共享项目 | 跨用户校对、导出和重复项处理 |
| 管理员 | 全部发票 | 创建私有或共享项目 | 用户、角色、状态、密码重置和 OCR 设置 |

第一位通过初始化页面创建的用户自动成为管理员。管理员后续创建的账号默认是普通用户，可在用户管理中调整角色。

## 使用 Docker 启动

部署前直接编辑 `docker-compose.yml`：

- 将 `app` 和 `worker` 的 `image` 改为实际镜像地址或本地镜像标签。
- 在 `x-postgres-credentials` 中替换数据库密码。
- 替换 `OCR_CONFIG_ENCRYPTION_KEY` 和 `APP_SECRET_KEY`。
- 如需自定义访问端口，只修改 `ports` 左侧，例如 `18080:8080`。

真实密码和应用密钥会保存在部署用 Compose 文件中，不要把修改后的生产配置提交到公开仓库。OCR 运营商的 `SecretId`、`SecretKey` 不写入 Compose，启动后由管理员在设置页录入。

构建、迁移并启动：

```bash
docker buildx build --platform linux/amd64 --load -t invoice-ocr-app:0.2.0 .
docker compose run --rm app migrate
docker compose up -d
docker compose ps
```

本地构建时，应将 Compose 中 `app` 和 `worker` 的 `image` 设置为 `invoice-ocr-app:0.2.0`。

打开 [http://localhost:8080](http://localhost:8080)。新数据库会显示初始化落地页，创建的第一个账号拥有管理员权限。已经初始化的数据库会显示登录表单。

健康检查：

```bash
curl -fsS http://localhost:8080/healthz
curl -fsS http://localhost:8080/readyz
```

停止服务但保留数据：

```bash
docker compose down
```

不要在日常停止或升级时运行 `docker compose down -v`，该参数会删除数据库、上传文件和导出文件 volumes。

## 首次功能检查

1. 在首页创建首位管理员并登录。
2. 在“用户管理”创建普通用户，确认默认角色为“普通用户”。
3. 在“项目管理”创建共享项目和私有项目。
4. 在“上传发票”选择项目上传一张发票；再不选项目上传一次，确认进入“未分类”。
5. 在“待校对”修正发票字段或明细行并确认。
6. 在“导出记录”按项目创建导出并下载文件。
7. 在“设置”配置 OCR 运营商和额度提醒。

## 升级现有部署

升级前备份 PostgreSQL、上传和导出 volumes，然后运行：

```bash
docker buildx build --platform linux/amd64 --load -t invoice-ocr-app:0.2.0 .
docker compose run --rm app migrate
docker compose up -d
```

这些命令不会删除现有 volumes。详细备份、恢复和生产 HTTPS 配置见部署文档。

## 本地开发与测试

后端：

```bash
cd backend
uv run --frozen --extra test pytest -v
```

前端：

```bash
cd frontend
npm ci
npm test
npm run build
```

隔离 Docker E2E：

```bash
tests/e2e/run.sh
```

E2E 使用独立 Compose 项目和独立 volumes，覆盖首用户初始化、用户和项目权限、OCR、明细校对、确认、项目筛选导出及服务重启后的持久化。

## 文档

- [完整设计文档](docs/design/01-overall-design.md)
- [数据模型与 API 设计](docs/design/02-api-data-model.md)
- [登录落地页设计方向](docs/design/auth-landing-direction-2.md)
- [运维手册](docs/operations/runbook.md)
- [Linux x86_64 Docker 部署指南](docs/deployment/linux-amd64-docker-deployment.md)
- [用户、项目、校对与导出设计](docs/plans/2026-07-10-user-project-review-export-design.md)
