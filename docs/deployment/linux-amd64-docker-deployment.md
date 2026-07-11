# Linux x86_64 Docker 部署指南

版本：v0.2

日期：2026-07-10

本文档描述已实现系统的标准部署、首次初始化和升级方式。

## 1. 部署目标

- 目标系统：Linux x86_64
- Docker 平台：`linux/amd64`
- 运行方式：Docker Compose
- OCR 运营商凭据：首次登录后在管理员设置页配置，不写入部署文件或 Docker `environment`
- 数据持久化：PostgreSQL volume + Redis volume + 上传文件 volume
- HTTPS：如有需要，由部署平台在项目外部提供

## 2. 腾讯云准备

1. 登录腾讯云控制台。
2. 开通文字识别 OCR 服务。
3. 创建 CAM 子账号或子用户密钥，不使用主账号密钥。
4. 为子账号授予 OCR 调用权限。若支持接口级权限，限制到 `VatInvoiceOCR`；否则限制到 OCR 服务访问。
5. 获取 `SecretId` 和 `SecretKey`，仅在系统设置页录入。
6. 确认账号未欠费，免费额度、资源包或后付费状态正常。
7. 在腾讯云控制台确认当前免费额度或资源包余量，后续在系统设置页填写提醒阈值。

## 3. 推荐拓扑

```text
app      Web/API/React 静态资源
worker   OCR 与导出异步任务，复用 app 镜像
postgres 结构化数据
redis    队列、限流、短期缓存
```

数据持久化：

```text
postgres_data -> PostgreSQL 数据
app_uploads   -> /data/uploads
app_exports   -> /data/exports
app_tmp       -> /data/tmp
```

## 4. Compose 配置

标准部署不使用 dotenv 配置文件。部署者只需编辑仓库根目录的 `docker-compose.yml`：

```yaml
x-postgres-credentials: &postgres-credentials
  POSTGRES_DB: invoice_app
  POSTGRES_USER: invoice_app
  POSTGRES_PASSWORD: 请替换为数据库密码

x-app-environment: &app-environment
  <<: *postgres-credentials
  POSTGRES_HOST: postgres
  POSTGRES_PORT: 5432
  OCR_CONFIG_ENCRYPTION_KEY: 请替换为32字节以上随机字符串

services:
  app:
    image: 请替换为实际镜像地址或标签
    environment:
      <<: *app-environment
      APP_SECRET_KEY: 请替换为至少32字节随机字符串
    ports:
      - "8080:8080"

  worker:
    image: 请使用与app相同的镜像
```

只修改 `ports` 左侧即可改变宿主机访问端口，容器内端口始终为 `8080`。例如 `18080:8080` 表示通过宿主机 `18080` 访问。

应用会从拆分后的 PostgreSQL 字段安全生成数据库连接地址，部署者不需要拼接 URL。Redis 地址、存储路径、临时目录和 worker 并发数使用镜像内默认值。

OCR 运营商、上传约束、QPS、重试策略和额度提醒使用系统默认值，并可在管理员设置页维护。不要在 `docker-compose.yml`、运行命令或 shell history 中填写腾讯云 `SecretId` / `SecretKey`；这些值只能在管理员设置页录入，并由应用加密保存。

应用不会自动读取 dotenv 配置文件。测试或特殊的非 Compose 部署仍可通过真实进程环境变量提供配置，并可用 `DATABASE_URL` 覆盖拆分后的 PostgreSQL 字段；标准生产 Compose 不使用该覆盖项。

## 5. 镜像构建

构建发布镜像：

```bash
docker buildx build \
  --platform linux/amd64 \
  --load \
  -t invoice-ocr-app:0.2.0 \
  .

docker inspect invoice-ocr-app:0.2.0 \
  --format '{{.Config.User}} {{.Architecture}}'
```

发布时使用不可变 tag，不使用 `latest` 作为生产部署版本。

镜像检查预期输出为 `invoice amd64`。如果构建机是 Apple Silicon，仍必须保留 `--platform linux/amd64`。

## 6. Compose 参考结构

仓库中的 `docker-compose.yml` 是自包含部署入口，核心结构如下：

```yaml
x-postgres-credentials: &postgres-credentials
  POSTGRES_DB: invoice_app
  POSTGRES_USER: invoice_app
  POSTGRES_PASSWORD: change-me

x-app-environment: &app-environment
  <<: *postgres-credentials
  POSTGRES_HOST: postgres
  POSTGRES_PORT: 5432
  OCR_CONFIG_ENCRYPTION_KEY: change-me-use-openssl-rand-base64-32

services:
  app:
    image: docker.io/your-dockerhub-username/invoice-ocr-app:0.2.0
    command: ["web"]
    environment:
      <<: *app-environment
      APP_SECRET_KEY: change-me-use-openssl-rand-hex-32
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      # 只修改左侧宿主机端口。
      - "8080:8080"
    volumes:
      - app_uploads:/data/uploads
      - app_exports:/data/exports
      - app_tmp:/data/tmp
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8080/readyz', timeout=2)\""]
      interval: 30s
      timeout: 5s
      retries: 3

  worker:
    image: docker.io/your-dockerhub-username/invoice-ocr-app:0.2.0
    command: ["worker"]
    environment: *app-environment
    depends_on:
      app:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - app_uploads:/data/uploads
      - app_exports:/data/exports
      - app_tmp:/data/tmp
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL

  postgres:
    image: postgres:16.3-bookworm
    environment: *postgres-credentials
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7.2-bookworm
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:
  app_uploads:
  app_exports:
  app_tmp:
```

## 7. 首次启动

首次启动流程：

```bash
vim docker-compose.yml
docker compose up -d
docker compose ps
```

编辑时必须替换镜像地址、数据库密码、`APP_SECRET_KEY` 和 `OCR_CONFIG_ENCRYPTION_KEY`。如修改了宿主机端口，后续访问地址和健康检查命令也使用该端口。

`app` 容器启动时会先执行 `alembic upgrade head`，成功后再启动 Web/API。首次空数据库会自动创建表结构；已有数据库只会应用尚未执行的迁移版本，不会重建表。若高级运维需要单独执行迁移，仍可运行 `docker compose run --rm app migrate`。

健康检查：

```bash
HOST_PORT=8080
curl -fsS "http://localhost:${HOST_PORT}/healthz"
curl -fsS "http://localhost:${HOST_PORT}/readyz"
```

然后打开 `http://<服务器地址>:<HOST_PORT>`：

1. 新数据库会显示初始化落地页。
2. 创建第一位用户，该用户自动成为管理员并立即登录。
3. 首位用户创建后，公开初始化永久关闭。
4. 后续账号由管理员在“用户管理”创建，默认角色为普通用户。

CLI `invoice-app create-admin` 仅用于网页不可用时的运维恢复，不是正常首次初始化步骤。CLI 创建用户后，浏览器初始化也会关闭。

### 7.1 用户与项目初始化

- 普通用户：只能查看自己的发票，可创建自己的私有项目，并可使用共享项目。
- 财务：可查看全部发票，可创建私有或共享项目，处理跨用户校对与导出。
- 管理员：拥有财务能力，并可管理用户、角色、状态、密码重置和 OCR 设置。
- 系统自动提供不可修改的“未分类”项目。
- 上传时未选择项目的发票自动进入“未分类”。

首次配置 OCR：

1. 使用管理员账号登录系统。
2. 打开“设置 -> OCR 运营商”。
3. 选择“腾讯云 OCR”，录入 `SecretId` 和 `SecretKey`。
4. 确认 endpoint 为 `ocr.tencentcloudapi.com`，Action 为 `VatInvoiceOCR`，Version 为 `2018-11-19`。
5. 设置内部 QPS，默认 8，不应超过腾讯云官方默认限制。
6. 填写免费额度或资源包总量、已用量、重置日和提醒阈值。
7. 点击连接测试，成功后设为默认启用运营商。

OCR 连接测试应在管理员设置页手动触发，不应由健康检查自动调用真实 OCR。

首次配置完成后，上传一张测试发票，确认它经过 OCR 后进入“待校对”；修正字段或明细行并确认，再按项目创建导出并下载文件。

## 8. 外部 HTTPS（可选）

项目 Compose 只负责将宿主机端口映射到容器 `8080`，不配置或信任反向代理头，也没有代理信任名单参数。

如部署平台需要 HTTPS，应由 NAS、负载均衡器、网关或独立 Web 服务器在项目外部完成证书和转发配置。外部代理还应自行限制上传大小并配置读写超时；这些设置不属于本项目 Compose 的职责范围。

## 9. 资源规划

| 规模 | CPU | 内存 | 存储 |
|---|---:|---:|---:|
| 个人/小团队 | 2 vCPU | 4GB | 50-100GB SSD |
| 中等团队 | 4 vCPU | 8GB | 200GB+ SSD |
| 大批量归档 | 8 vCPU | 16GB | 按发票原件估算并预留备份空间 |

OCR 调用受运营商官方频率限制。腾讯云 `VatInvoiceOCR` 默认限制为 10 次/秒，系统设置页默认内部限流应为 8 次/秒，避免贴边触发限流。

## 10. 备份

需要备份：

- PostgreSQL 数据
- `/data/uploads`
- `/data/exports`
- 部署用 `docker-compose.yml` 的加密备份
- 数据库中的 OCR 运营商加密配置，以及对应的 `OCR_CONFIG_ENCRYPTION_KEY`

数据库备份：

```bash
docker compose exec postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/invoice_app.dump'

docker compose cp postgres:/tmp/invoice_app.dump ./backups/invoice_app-$(date +%F).dump
```

文件备份：

```bash
docker run --rm \
  -v invoice_app_uploads:/data/uploads:ro \
  -v "$PWD/backups:/backup" \
  alpine:3.20 \
  tar czf /backup/uploads-$(date +%F).tar.gz -C /data uploads
```

建议：

- 每日增量或快照
- 每周全量
- 至少保留 7-30 天
- 企业环境异地备份
- 定期恢复演练

## 11. 恢复

1. 停止服务：

```bash
docker compose down
```

2. 恢复数据库 volume。
3. 恢复上传文件 volume。
4. 启动 PostgreSQL 和 Redis。
5. 执行数据库恢复。
6. 启动 app 和 worker。
7. 抽样检查发票列表、原件下载、OCR 结果和导出。

恢复后必须校验数据库中的 `storage_key` 与文件实际存在性。

## 12. 升级与回滚

### 12.1 首次从旧版 dotenv 部署升级

旧版 dotenv 文件在本版本中不再被应用或 Compose 读取。第一次升级前，先把旧配置中的以下原值迁入新版 `docker-compose.yml`：

- `POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD`：写入 `x-postgres-credentials`
- `OCR_CONFIG_ENCRYPTION_KEY`：写入 `x-app-environment`
- `APP_SECRET_KEY`：写入 `app` 服务的 `environment`
- 旧的宿主机访问端口：写入 `ports` 左侧

这些值必须保持与旧部署一致，尤其不要重新生成 `POSTGRES_PASSWORD` 或 `OCR_CONFIG_ENCRYPTION_KEY`。否则可能无法连接已有数据库，或无法解密数据库中保存的 OCR 运营商凭据。

迁移配置并确认新服务可以登录、读取历史发票和测试 OCR 配置后，旧 dotenv 文件才可以退出部署流程。

### 12.2 常规升级

升级前：

- 备份数据库和文件
- 阅读 release notes
- 确认数据库迁移是否可逆
- 测试环境先升级

升级：

```bash
HOST_PORT=8080
docker compose up -d
curl -fsS "http://localhost:${HOST_PORT}/readyz"
```

执行前先将 Compose 中 `app` 和 `worker` 的镜像更新为目标版本。

`app` 会在启动 Web/API 前自动执行缺失的迁移。上述命令会复用现有命名 volumes，不会删除 PostgreSQL、上传原件或导出文件。不要在升级流程中执行 `docker compose down -v`。

升级后检查：

1. 管理员和普通用户可以登录，权限菜单正确。
2. “未分类”、共享项目和私有项目仍存在，发票项目归属正确。
3. 待校对队列可保存明细修改并完成确认。
4. 按项目筛选的导出可创建和下载。
5. 重启 `app` 与 `worker` 后，上述数据仍可读取。

回滚：

- 使用旧镜像 tag
- 恢复升级前数据库备份
- 恢复升级前的 Compose 配置

如果迁移不可逆，发布说明必须明确标注。

## 13. 密钥轮换

1. 在腾讯云创建新的 SecretId/SecretKey。
2. 登录管理员设置页，打开“腾讯云 OCR”配置。
3. 使用“轮换凭据”录入新 SecretId/SecretKey。
4. 执行 OCR 测试。
5. 测试成功后保存并启用新凭据。
6. 确认生产识别成功后，在腾讯云控制台禁用旧密钥。

OCR 运营商密钥轮换不需要修改部署文件，也不需要重启 app 或 worker。只有轮换 `OCR_CONFIG_ENCRYPTION_KEY` 时才需要更新 Compose 并重启相关服务。

## 14. 故障排查

### 14.1 凭证错误

- 在管理员设置页检查 OCR 运营商是否启用并设为默认
- 在管理员设置页重新执行连接测试
- 检查是否使用 CAM 子账号
- 检查 OCR 权限和服务是否开通

### 14.2 OCR 限流

- 在设置页降低当前 OCR 运营商的 QPS
- 查看 worker 数和队列积压
- 检查是否批量重新识别

### 14.2.1 免费额度或资源包即将耗尽

- 查看设置页的当前免费额度、资源包余量和阈值
- 若运营商无法自动同步额度，按腾讯云控制台数据手动校准
- 额度不足时购买资源包、开通后付费或暂停批量识别
- 确认提醒处理后，可在设置页标记为已确认

### 14.3 文件不支持

- 仅支持 PNG/JPG/JPEG/PDF
- GIF 不支持
- PDF 一期仅支持单页
- Base64 后不得超过 10MB
- 图片宽高需在 20-10000px

### 14.4 网络问题

容器内检查：

```bash
docker compose exec worker getent hosts ocr.tencentcloudapi.com
docker compose exec worker curl -I https://ocr.tencentcloudapi.com
```

检查代理、防火墙、出口 ACL、DNS。

### 14.5 上传被外部网关拦截

- 在项目外部的 Nginx 检查 `client_max_body_size`
- 在项目外部的 Caddy 检查 `request_body max_size`
- 应用检查当前上传限制设置和 OCR 运营商输入约束

## 15. 安全加固清单

- 使用 HTTPS
- 使用 CAM 子账号
- 限制生产 `docker-compose.yml` 的读取权限并加密备份
- 不在部署文件或 Docker `environment` 中放 OCR 运营商密钥
- 保护 `OCR_CONFIG_ENCRYPTION_KEY`，并随数据库备份一起做加密备份
- 容器非 root 运行
- 不暴露 PostgreSQL 和 Redis 到公网
- 不记录 Secret 和完整 Base64
- 上传文件鉴权下载
- 默认不开远程 URL 识别
- 启用审计日志
- 定期备份和恢复演练
- 镜像漏洞扫描无高危未解释项
