# Copilot Workspace Instructions

本文件定义仓库级默认行为，目标是让代理能在本项目中快速、安全、可验证地完成开发任务。

## 项目定位
- 仓库是三层混合架构：
  - Quantumult X 脚本：`scripts/dekt_*.js`、`scripts/card_*.js`
  - 本地 Node 调试封装：`scripts/local_*.js`
  - Python 后端与 GUI：`dekt_backend/`、`dekt_gui_app/`
- 核心目标：实现 DEKT 全链路操作（抓取鉴权、监控、报名、签到/签退、后端网页服务、桌面 GUI）。

## 代码风格
- JavaScript：`CommonJS`（`require` / `module.exports`），ES2020+，优先 `async/await`。
- Python：保持现有类型标注风格（`from __future__ import annotations`），优先复用现有模块而非新增重复实现。
- 注释与说明：简洁中文，聚焦边界条件与业务原因。
- 变更策略：最小化改动，不重构无关代码，不破坏现有任务/重写片段格式。

## 架构边界
- QX 与本地 Node 共享脚本逻辑：本地通过 `scripts/local_env.js` 适配 `Env`，`scripts/local_*.js` 仅做包装与调试入口。
- Python 后端 `dekt_backend/` 提供网页页面（`/`、`/health`、`/runtime`）与运行时轮询。
- Python GUI `dekt_gui_app/` 仅直连 DEKT 接口；后端运行时复用 GUI 客户端层（`dekt_gui_app/dekt_gui/api_client.py`）。

## 构建与测试
- JavaScript 依赖安装：优先 `bun install`（兼容 `npm install`）。
- 本地脚本运行：`node scripts/local_dekt_monitor.js`、`node scripts/local_card_probe.js` 等。
- 后端启动（从仓库根目录）：
  - `cd dekt_backend`
  - `python -m venv .venv`
  - `.venv/bin/pip install -r requirements.txt`
  - `.venv/bin/uvicorn dekt_backend.main:app --host 0.0.0.0 --port 8000`
- 后端测试：`pytest -q dekt_backend/tests`
- 语法检查：`python -m compileall dekt_backend dekt_gui_app`
- GUI 启动：`cd dekt_gui_app && .venv/bin/python main.py`

## 关键约定与坑点
- 配置优先级：
  - QX 脚本读 BoxJS；本地脚本读仓库根 `.env`。
  - 后端启动会依次加载根 `.env` 与 `dekt_backend/.env`（系统环境变量优先）。
- 安全红线：禁止输出或提交真实 Token/Cookie/OpenID/API Key。
- DEKT 取消报名链路依赖 `user_id`，应通过 token 对应接口获取，不要硬编码。
- 后端不再暴露 `/api/v1/*` 接口，网页模式仅保留页面访问与运行时展示。
- 生成 QX 片段时，保持现有 `*.snippet`、`task.json` 风格与字段顺序，避免破坏可导入性。

## 文档索引
- 总览与脚本说明：`README.md`
- Python 后端：`dekt_backend/README.md`
- Python GUI：`dekt_gui_app/README.md`
- 额外仓库约定：`CLAUDE.md`

## 代理默认行为
- 先说明简短方案（输入/输出、边界、错误处理），再实施改动。
- 涉及网络请求时明确 headers 来源，处理超时、重试、压缩响应与非 2xx 返回。
- 优先复用现有实现与文件结构，避免引入重量级框架。
- 若需偏离本说明，先明确说明原因与影响。