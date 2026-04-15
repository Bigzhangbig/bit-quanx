# DEKT 后端（网页模式）

该服务是 DEKT 架构中的网页后端。
当前版本仅提供网页页面，不再提供签名 API。

## 环境变量

后端启动时会自动读取以下两个位置（按顺序）：

- 仓库根目录 `.env`
- `dekt_backend/.env`

若同名变量已在系统环境中存在，系统环境变量优先。

推荐先复制模板：

```bash
cd dekt_backend
cp .env.example .env
```

然后按需修改：

```bash
DEKT_BACKEND_HOST=0.0.0.0
DEKT_BACKEND_PORT=8000
DEKT_BACKEND_API_KEY=replace-with-strong-secret
DEKT_BACKEND_REQUEST_TTL=300
DEKT_BACKEND_NONCE_TTL=600
DEKT_BACKEND_RUNTIME_ENABLED=false
DEKT_BACKEND_RUNTIME_INTERVAL_SECONDS=300
DEKT_BACKEND_RUNTIME_INITIAL_DELAY_SECONDS=0
DEKT_BACKEND_RUNTIME_FETCH_DELAY_MAX_SECONDS=3
```

## 部署方式

### 方式 1：本地前台运行（开发/调试）

```bash
cd dekt_backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn dekt_backend.main:app --host 0.0.0.0 --port 8000
```

### 方式 2：systemd 常驻（Linux 服务器）

1) 先把项目放到固定路径，例如 `/opt/bit-quanx`，并完成依赖安装。

2) 新建 `/etc/systemd/system/dekt-backend.service`：

```ini
[Unit]
Description=DEKT Backend Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/bit-quanx
EnvironmentFile=/opt/bit-quanx/dekt_backend/.env
ExecStart=/opt/bit-quanx/.venv/bin/python -m uvicorn dekt_backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

3) 启动并开机自启：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dekt-backend
sudo systemctl status dekt-backend
```

### 方式 3：Docker 运行

在仓库根目录新建或使用现有 `Dockerfile` 后，可直接：

```bash
docker run -d \
  --name dekt-backend \
  --restart unless-stopped \
  --env-file ./dekt_backend/.env \
  -p 8000:8000 \
  bit-quanx-dekt-backend
```

若你希望，我可以下一步直接给你补一个适配当前仓库的 `dekt_backend/Dockerfile` 与 `docker-compose.yml`。

## 快速启动（临时覆盖变量）

```bash
cd dekt_backend
.venv/bin/uvicorn dekt_backend.main:app --host 0.0.0.0 --port 8000
```

## 网页入口

- `/`：首页（网页模式说明）
- `/health`：健康检查页面
- `/runtime`：后台轮询状态页
- `POST /runtime/run-now`：从网页触发一次轮询（表单提交）

说明：不再暴露 `/api/v1/*` 路由。

## 后台定时运行

当 `DEKT_BACKEND_RUNTIME_ENABLED=true` 时，服务启动后会进入后台轮询，周期性拉取已开始课程、未开始课程和我的课程，并在每轮中加入随机抖动，避免请求过于集中。

## 配置存储

后端配置保存于：

- `~/.dekt_backend/config.json`

该文件包含 DEKT token 以及监控过滤白名单配置。
