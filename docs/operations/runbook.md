# Invoice OCR Operations Runbook

适用版本：`0.2.0`

## 发布检查

- 为 `linux/amd64` 构建不可变版本标签的镜像。
- 确认镜像用户为 `invoice`，架构为 `amd64`。
- 审阅 CI 生成的 SBOM 和漏洞扫描结果。
- 确认生产 `docker-compose.yml` 中的数据库密码和应用加密密钥已替换，并受到访问控制。
- 确认腾讯云 `SecretId`、`SecretKey` 不存在于 Compose、shell history 和 CI 日志。
- 确认 `app` 容器启动时自动执行数据库迁移；高级排障时可手动运行 `docker compose run --rm app migrate`。
- 升级时保留 PostgreSQL、Redis、上传、导出和临时文件 volumes。
- 检查 `/healthz`、`/readyz`、用户、项目、待校对和导出流程。

## 标准发布命令

```bash
docker buildx build --platform linux/amd64 --load -t invoice-ocr-app:0.2.0 .
docker inspect invoice-ocr-app:0.2.0 --format '{{.Config.User}} {{.Architecture}}'
docker compose up -d
docker compose ps
```

执行前将 Compose 中 `app` 和 `worker` 的 `image` 更新为本次发布标签。`app` 容器会在启动 Web/API 前自动执行 Alembic 迁移。

镜像检查预期输出：

```text
invoice amd64
```

## 首次初始化

1. 启动服务；`app` 容器会自动完成数据库迁移。
2. 打开 `http://<host>:<HOST_PORT>`。
3. 初始化落地页只在系统没有用户时显示。
4. 创建第一位用户，该账号自动获得管理员角色并立即登录。
5. 公开初始化随后关闭；后续账号由管理员在“用户管理”创建，默认角色为普通用户。
6. 在“设置”中配置 OCR 运营商、凭据、限流和额度提醒。

不再把 CLI 创建管理员作为正常首次启动步骤。仅在无法访问网页且确认需要运维恢复时使用：

```bash
docker compose exec app invoice-app create-admin \
  --email recovery-admin@example.com \
  --password 'use-a-strong-recovery-password' \
  --display-name 'Recovery Administrator'
```

CLI 创建任何用户都会使公开初始化关闭。执行后应立即登录、审查管理员列表，并妥善处理恢复账号。

## 健康检查

```bash
HOST_PORT=8080
curl -fsS "http://localhost:${HOST_PORT}/healthz"
curl -fsS "http://localhost:${HOST_PORT}/readyz"
docker compose ps
```

- `/healthz`：API 进程正在运行。
- `/readyz`：数据库和 Redis 可连接。
- OCR 运营商连通性不属于 readiness，必须从管理员设置页手动测试。

## 业务冒烟检查

每次首次部署或版本升级后检查：

1. 管理员可以登录；普通用户无法访问“用户管理”和 OCR 设置。
2. 新建用户默认角色为普通用户，角色、状态和密码重置可由管理员维护。
3. “未分类”项目存在且不可修改；共享和私有项目的可见范围符合角色规则。
4. 上传时能选择项目；不选项目时返回“未分类”。
5. OCR 完成后发票进入“待校对”，字段和明细行修改可保存。
6. 发票确认后从待校对队列移出，项目筛选结果正确。
7. 按项目创建 JSON、CSV 或 XLSX 导出，任务完成后可以下载。
8. 重启 `app` 和 `worker` 后，用户、项目、发票校对结果和导出仍存在。

## 升级

升级前备份数据库与文件 volumes，并记录当前镜像标签：

首次从旧版 dotenv 部署升级时，先把旧配置中的 `POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD`、`APP_SECRET_KEY` 和 `OCR_CONFIG_ENCRYPTION_KEY` 原值迁入新版 Compose，并把原宿主机端口写到 `ports` 左侧。不得在同一次升级中重新生成数据库密码或 OCR 配置加密密钥。验证历史数据和 OCR 配置可正常读取后，再退出旧 dotenv 配置流程。

```bash
HOST_PORT=8080
docker compose up -d
curl -fsS "http://localhost:${HOST_PORT}/readyz"
```

不要运行 `docker compose down -v`。正常 `docker compose down` 和 `docker compose up -d` 会保留命名 volumes。

## 日志与故障定位

```bash
docker compose logs --tail=200 app
docker compose logs --tail=200 worker
docker compose logs --tail=200 postgres redis
```

- OCR 失败：使用管理员可见的 `request_id` 和运营商错误码定位，避免把完整 OCR 原始响应写入外部工单。
- 队列延迟：检查 Redis、worker 存活状态和 Celery 日志。
- 数据库错误：检查 `/readyz`、PostgreSQL 日志和 Alembic 当前版本。
- 额度告警：核对当前资源包、用量和提醒阈值，再调整 QPS。
- 导出失败：检查 worker 日志、`app_exports` volume 空间和任务错误类型。

## 审计日志

系统记录登录、用户变更、项目变更、上传、OCR 完成、发票修正、确认、导出创建、OCR 运营商变更、凭据轮换、额度校准与告警确认。

审计元数据在持久化前会脱敏。不得在审计日志中保存明文密码、OCR 凭据、上传文件内容或完整 OCR 原始载荷。

## 备份与恢复

- PostgreSQL 与 `app_uploads`、`app_exports` 必须按同一时间点备份。
- 部署用 `docker-compose.yml` 及其中的 `OCR_CONFIG_ENCRYPTION_KEY` 需要加密备份，否则数据库中的 OCR 凭据无法解密。
- 恢复后运行 `/readyz`，抽查最近发票、项目归属、校对明细和已知导出文件。
- Redis 主要承载队列和限流状态，恢复时仍应保留其 volume 或明确接受短期任务状态丢失。
