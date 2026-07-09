# Linux x86_64 Docker 部署指南

版本：v0.1

日期：2026-07-09

本文档描述项目实现完成后的标准部署方式。后续代码必须按本文档交付可执行配置。

## 1. 部署目标

- 目标系统：Linux x86_64
- Docker 平台：`linux/amd64`
- 运行方式：Docker Compose
- 用户必填腾讯云参数：`TENCENTCLOUD_SECRET_ID`、`TENCENTCLOUD_SECRET_KEY`
- 生产建议：HTTPS 反向代理 + PostgreSQL volume + Redis volume + 上传文件 volume

## 2. 腾讯云准备

1. 登录腾讯云控制台。
2. 开通文字识别 OCR 服务。
3. 创建 CAM 子账号或子用户密钥，不使用主账号密钥。
4. 为子账号授予 OCR 调用权限。若支持接口级权限，限制到 `VatInvoiceOCR`；否则限制到 OCR 服务访问。
5. 获取 `SecretId` 和 `SecretKey`。
6. 确认账号未欠费，资源包或后付费状态正常。

## 3. 推荐拓扑

```text
app      Web/API/React 静态资源
worker   OCR 与导出异步任务，复用 app 镜像
postgres 结构化数据
redis    队列、限流、短期缓存
proxy    Caddy/Nginx/Traefik，可选但生产推荐
```

数据持久化：

```text
postgres_data -> PostgreSQL 数据
app_uploads   -> /data/uploads
app_exports   -> /data/exports
app_tmp       -> /data/tmp
```

## 4. 环境变量

### 4.1 最小必填

```env
TENCENTCLOUD_SECRET_ID=请填写腾讯云SecretId
TENCENTCLOUD_SECRET_KEY=请填写腾讯云SecretKey
APP_SECRET_KEY=请生成至少32字节随机字符串
POSTGRES_PASSWORD=请生成数据库密码
```

### 4.2 完整示例

```env
APP_ENV=production
APP_BASE_URL=https://invoice.example.com
APP_PORT=8080
TZ=Asia/Shanghai

APP_SECRET_KEY=change-me-use-openssl-rand-hex-32
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=Lax
TRUSTED_PROXIES=127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16

POSTGRES_DB=invoice_app
POSTGRES_USER=invoice_app
POSTGRES_PASSWORD=change-me
DATABASE_URL=postgresql+psycopg://invoice_app:change-me@postgres:5432/invoice_app

REDIS_URL=redis://redis:6379/0

STORAGE_PATH=/data/uploads
EXPORT_PATH=/data/exports
TMP_PATH=/data/tmp

TENCENTCLOUD_SECRET_ID=change-me
TENCENTCLOUD_SECRET_KEY=change-me
TENCENTCLOUD_REGION=ap-guangzhou
TENCENTCLOUD_OCR_ENDPOINT=ocr.tencentcloudapi.com
TENCENTCLOUD_OCR_ACTION=VatInvoiceOCR
TENCENTCLOUD_OCR_VERSION=2018-11-19
TENCENTCLOUD_OCR_QPS=8
OCR_TIMEOUT_SECONDS=15
OCR_REMOTE_DOWNLOAD_TIMEOUT_SECONDS=3

OCR_ALLOWED_TYPES=png,jpg,jpeg,pdf
OCR_MAX_BASE64_MB=10
OCR_MIN_IMAGE_PX=20
OCR_MAX_IMAGE_PX=10000
OCR_PDF_SINGLE_PAGE_ONLY=true

WORKER_CONCURRENCY=4
OCR_RETRY_MAX=3
OCR_RETRY_BACKOFF_SECONDS=10,30,120
```

`.env` 文件权限建议：

```bash
chmod 600 .env
```

不要把 `.env` 提交到 Git。

## 5. 镜像构建

后续实现必须支持：

```bash
docker buildx build \
  --platform linux/amd64 \
  -t invoice-ocr-app:0.1.0 \
  .
```

发布时使用不可变 tag，不使用 `latest` 作为生产部署版本。

## 6. Compose 参考结构

实现完成后，`docker-compose.yml` 应等价于：

```yaml
services:
  app:
    image: invoice-ocr-app:0.1.0
    command: ["web"]
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
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
      test: ["CMD", "curl", "-fsS", "http://localhost:8080/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3

  worker:
    image: invoice-ocr-app:0.1.0
    command: ["worker"]
    env_file: .env
    depends_on:
      postgres:
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
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
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

实现完成后，首次启动流程：

```bash
cp .env.example .env
vim .env
chmod 600 .env
docker compose pull
docker compose up -d
docker compose logs -f app worker
```

初始化管理员：

```bash
docker compose exec app invoice-app create-admin \
  --email admin@example.com \
  --password 'change-me'
```

健康检查：

```bash
curl -fsS http://localhost:8080/healthz
curl -fsS http://localhost:8080/readyz
```

OCR 连接测试应在管理员设置页手动触发，不应由健康检查自动调用真实 OCR。

## 8. HTTPS 反向代理

生产必须走 HTTPS。推荐 Caddy：

```caddyfile
invoice.example.com {
  encode gzip zstd
  reverse_proxy app:8080
  request_body {
    max_size 12MB
  }
}
```

Nginx 需要设置：

```nginx
client_max_body_size 12m;
proxy_set_header Host $host;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_read_timeout 120s;
proxy_send_timeout 120s;
```

Cookie 要求：

- `Secure`
- `HttpOnly`
- `SameSite=Lax`

## 9. 资源规划

| 规模 | CPU | 内存 | 存储 |
|---|---:|---:|---:|
| 个人/小团队 | 2 vCPU | 4GB | 50-100GB SSD |
| 中等团队 | 4 vCPU | 8GB | 200GB+ SSD |
| 大批量归档 | 8 vCPU | 16GB | 按发票原件估算并预留备份空间 |

OCR 调用受腾讯云默认 10 次/秒限制。系统默认应设置 `TENCENTCLOUD_OCR_QPS=8`，避免贴边触发限流。

## 10. 备份

需要备份：

- PostgreSQL 数据
- `/data/uploads`
- `/data/exports`
- `.env` 的加密备份
- 当前 `docker-compose.yml`

数据库备份：

```bash
docker compose exec postgres pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  -Fc \
  -f /tmp/invoice_app.dump

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

升级前：

- 备份数据库和文件
- 阅读 release notes
- 确认数据库迁移是否可逆
- 测试环境先升级

升级：

```bash
docker compose pull
docker compose run --rm app invoice-app migrate
docker compose up -d
```

回滚：

- 使用旧镜像 tag
- 恢复升级前数据库备份
- 恢复升级前 compose 和 `.env`

如果迁移不可逆，发布说明必须明确标注。

## 13. 密钥轮换

1. 在腾讯云创建新的 SecretId/SecretKey。
2. 更新 `.env`。
3. 重启 app 和 worker：

```bash
docker compose up -d app worker
```

4. 在管理员设置页执行 OCR 测试。
5. 确认成功后禁用旧密钥。

## 14. 故障排查

### 14.1 凭证错误

- 检查 `TENCENTCLOUD_SECRET_ID`
- 检查 `TENCENTCLOUD_SECRET_KEY`
- 检查是否使用 CAM 子账号
- 检查 OCR 权限和服务是否开通

### 14.2 OCR 限流

- 降低 `TENCENTCLOUD_OCR_QPS`
- 查看 worker 数和队列积压
- 检查是否批量重新识别

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

### 14.5 上传被反代拦截

- Nginx 检查 `client_max_body_size`
- Caddy 检查 `request_body max_size`
- 应用检查 `OCR_MAX_BASE64_MB`

## 15. 安全加固清单

- 使用 HTTPS
- 使用 CAM 子账号
- `.env` 权限 600
- 容器非 root 运行
- 不暴露 PostgreSQL 和 Redis 到公网
- 不记录 Secret 和完整 Base64
- 上传文件鉴权下载
- 默认不开远程 URL 识别
- 启用审计日志
- 定期备份和恢复演练
- 镜像漏洞扫描无高危未解释项

