# Docker Compose 与数据库配置精简设计

日期：2026-07-10

## 目标

在 `main` 分支上简化生产 `docker-compose.yml`，让部署者只接触实际需要修改的配置：镜像、宿主机端口、应用密钥、OCR 配置加密密钥和 PostgreSQL 凭据。容器内 Web 端口固定为 `8080`，项目不负责反向代理配置。

## Compose 结构

- `app` 保留 Web 进程真正需要的应用密钥、OCR 配置加密密钥和拆分后的 PostgreSQL 连接字段。
- `worker` 保留 OCR 配置加密密钥和拆分后的 PostgreSQL 连接字段。
- `postgres` 使用相同的数据库名、用户名和密码。
- 使用 YAML anchor 共享 PostgreSQL 基础字段，避免用户在多个服务中重复修改同一份凭据。
- `ports` 保持 `8080:8080` 示例；部署者只修改左侧宿主机端口。
- 删除与代码默认值一致或当前没有运行时作用的环境变量，包括 `APP_ENV`、`APP_BASE_URL`、`APP_PORT`、`TZ`、Cookie 默认配置、`TRUSTED_PROXIES`、Redis 默认地址、存储路径和 worker 默认并发数。

## 数据库配置

应用配置增加以下字段：

- `POSTGRES_HOST`，默认 `postgres`
- `POSTGRES_PORT`，默认 `5432`
- `POSTGRES_DB`，默认 `invoice_app`
- `POSTGRES_USER`，默认 `invoice_app`
- `POSTGRES_PASSWORD`，默认 `change-me`

后端使用 SQLAlchemy `URL.create()` 生成 `postgresql+psycopg` 连接地址，避免部署者手动拼接 URL，并正确处理密码中的 `@`、`:`、`/` 等保留字符。

为兼容现有测试、Alembic 命令和非 Compose 部署，`DATABASE_URL` 继续作为可选覆盖项存在；生产 Compose 和标准部署示例不再设置它。读取方继续通过 `settings.database_url` 获得最终字符串，因此数据库会话、迁移和业务代码不需要改动。

## 代理与端口

`TRUSTED_PROXIES` 当前没有连接到 FastAPI 中间件或 Uvicorn 的 forwarded-IP 配置，因此删除它不会改变运行行为。项目不承诺处理反向代理头；如部署者在外层使用代理，由其自行配置代理和网络边界。

应用镜像内部继续监听 `8080`。Compose 只通过 `HOST_PORT:8080` 映射宿主机端口，不再通过 `APP_PORT` 改变容器内端口。

## 错误处理与安全

- PostgreSQL 端口继续由类型化配置校验为整数。
- 生成的数据库 URL 仅在诊断输出中通过现有 `redact_url_password()` 隐藏密码。
- Compose 中仍提供明显的占位密钥和密码，部署说明要求上线前替换。
- 不把腾讯云 SecretId/SecretKey 放入 Compose；该规则保持不变。

## 验证

- 先增加配置测试，证明拆分字段可生成预期 URL、特殊字符会正确编码、`DATABASE_URL` 可覆盖拆分字段、诊断输出不会泄露密码。
- 运行后端配置测试和完整后端测试。
- 使用 `docker compose config` 验证精简后的 Compose 结构。
- 检查渲染后的 app、worker、postgres 环境，确认 `DATABASE_URL` 和 `TRUSTED_PROXIES` 均不存在，且数据库凭据在需要的服务间保持一致。
