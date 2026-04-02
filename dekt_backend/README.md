# DEKT 后端（MVP）

该服务是 DEKT 前后端分离架构中的后端部分。
它负责本地持久化运行配置，并向 GUI 暴露带签名的 HTTP API。

## 安全模型（MVP）

- 除健康检查外，所有接口都需要 HMAC 请求头：
  - `X-API-Key`
  - `X-Timestamp`
  - `X-Nonce`
  - `X-Signature`
- 签名算法：`HMAC-SHA256`
- 签名消息格式：
  - `{timestamp}.{nonce}.{METHOD}.{PATH}.{sha256(body_bytes)}`

## 环境变量

```bash
export DEKT_BACKEND_API_KEY="replace-with-strong-secret"
export DEKT_BACKEND_HOST="0.0.0.0"
export DEKT_BACKEND_PORT="8000"
export DEKT_BACKEND_RUNTIME_ENABLED="false"
export DEKT_BACKEND_RUNTIME_INTERVAL_SECONDS="300"
export DEKT_BACKEND_RUNTIME_INITIAL_DELAY_SECONDS="0"
export DEKT_BACKEND_RUNTIME_FETCH_DELAY_MAX_SECONDS="3"
```

## 启动

```bash
cd dekt_backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn dekt_backend.main:app --host 0.0.0.0 --port 8000
```

快速启动（与上面行为一致）：

```bash
cd dekt_backend
DEKT_BACKEND_API_KEY="replace-with-strong-secret" \
.venv/bin/uvicorn dekt_backend.main:app --host 0.0.0.0 --port 8000
```

## 本地冒烟检查

执行最小连通性与鉴权检查：

```bash
cd dekt_backend
python local_smoke.py --base-url http://127.0.0.1:8000 --api-key "replace-with-strong-secret"
```

脚本会验证：

- `GET /health`（无需签名）
- `GET /api/v1/config`（需要签名）
- `POST /api/v1/auth/verify`（需要签名）

## 课程相关接口

- `GET /api/v1/courses/list?sign_status=1|2|3`：按状态获取课程列表
- `GET /api/v1/courses/started`：获取已开始课程，等价于 `sign_status=2`
- `GET /api/v1/courses/unstarted`：获取未开始课程，等价于 `sign_status=1`
- `GET /api/v1/courses/my`：获取我的课程
- `GET /api/v1/courses/{course_id}/qrcode`：返回活动二维码链接
- `POST /api/v1/courses/{course_id}/apply`：报名
- `POST /api/v1/courses/{course_id}/cancel`：取消报名
- `GET /api/v1/courses/{course_id}/checkin-info`：获取签到信息
- `POST /api/v1/courses/{course_id}/sign-in`：签到
- `POST /api/v1/courses/{course_id}/sign-out`：签退

## 后台定时运行

当 `DEKT_BACKEND_RUNTIME_ENABLED=true` 时，服务启动后会进入后台轮询，周期性拉取已开始课程、未开始课程和我的课程，并在每轮中加入随机抖动，避免请求过于集中。

可用接口查看或手动触发：

- `GET /api/v1/runtime/status`
- `POST /api/v1/runtime/run-now`

可选 token 验证：

```bash
cd dekt_backend
python local_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --api-key "replace-with-strong-secret" \
  --token "Bearer your-token"
```

## 配置存储

后端配置保存于：

- `~/.dekt_backend/config.json`

该文件包含 DEKT token 以及监控过滤白名单配置。
