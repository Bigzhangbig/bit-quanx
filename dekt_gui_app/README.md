# DEKT 桌面 GUI（Alpha）

这是一个面向 DEKT 流程的独立 Python 桌面应用。
该应用与现有 JS 脚本相互独立。

## 当前 Alpha 范围

- 手动输入 Token
- 从 GitHub Gist 拉取 Token
- 通过 `GET /api/user/info` 验证 Token
- 手动监控查询页（6 个栏目一键查询、标签切换）
- 监控表格右键操作（报名/取消报名，含报名前置校验）
- 监控/打卡/活动表格右键查看二维码
- 监控表格按内容自动调整列宽
- 打卡页（加载我的活动 + 手动签到/签退）
- 活动页（我的活动列表 + 双击查看详情）
- GUI 中已移除退课页
- 本地凭据持久化：`~/.dekt_gui/config.json`
- 自动读取 `dekt_gui_app/` 下 `.env` 默认值

## 约束

- 使用 PySide6 Qt Widgets 原生桌面 GUI
- 不嵌入浏览器/WebView

## 二维码说明

- 二维码内容是活动的签到链接 URL
- 二维码图像由本地 `qrcode` 库生成，不再依赖 DEKT 远端取图接口
- 若本地缺少 `qrcode[pil]` / `pillow` 依赖，二维码对话框会提示生成失败

可在“监控”、“打卡”或“活动”表格中右键点击某一行，然后选择“查看二维码”打开二维码对话框。

## TLS 说明

- 默认允许不安全 TLS（自签名证书）
- 可在“凭据”页取消勾选“忽略 TLS 证书校验（仅调试）”以恢复严格校验

## 运行

```bash
cd dekt_gui_app
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## 后端模式（前后端分离）

当 GUI 仅作为客户端、运行配置保存在后端时，请使用该模式。

1. 先启动后端服务（见 `../dekt_backend/README.md`）。
2. 打开 GUI 的“凭据”标签页。
3. 启用“后端模式（签名 API 调用）”。
4. 填写后端连接信息：
   - 后端地址（示例：`http://127.0.0.1:8000`）
   - 后端 API key（需与后端 `DEKT_BACKEND_API_KEY` 一致）
5. 点击“测试后端连接”，验证 `/health` 与签名配置读取。
6. 在 GUI 设置或粘贴 Token 后，点击“同步 Token 到后端”。
7. 填写白名单字段（栏目、年级、学院）后，点击“同步白名单到后端”。
8. 可选：点击“从后端加载白名单”拉取服务端当前配置。

启用后端模式后：

- “验证 Token”走后端 `/api/v1/auth/verify`
- “监控”列表与右键“报名/取消报名”走后端课程 API
- “签到/签退”走后端 `checkin-info` 与打卡 API

若存在 `dekt_gui_app/.env`，应用会自动读取以下默认值：

- `bit_sc_token`
- `bit_sc_github_token`
- `bit_sc_gist_id`
- `bit_sc_gist_filename`
- `bit_sc_tencent_map_key`
- `bit_sc_tls_insecure`（可选，`true/false`）
- `dekt_backend_mode`（可选，`true/false`）
- `dekt_backend_base_url`（可选）
- `dekt_backend_api_key`（可选）

## 打包（macOS）

使用 PyInstaller 构建桌面应用：

```bash
cd dekt_gui_app
.venv/bin/python -m pip install -r requirements.txt pyinstaller
.venv/bin/python -m PyInstaller --noconfirm --clean --windowed --name DEKT-GUI --paths . main.py
```

构建产物：

- App 包：`dekt_gui_app/dist/DEKT-GUI.app`
- 可执行文件：`dekt_gui_app/dist/DEKT-GUI.app/Contents/MacOS/DEKT-GUI`

## 打包（Windows）

推荐用 GitHub Actions 在真实 Windows Runner 上打包（本机是 macOS 时尤其推荐）：

1. 将当前修改推送到 GitHub 仓库。
2. 打开 Actions，手动运行工作流 `Build DEKT GUI (Windows)`。
3. 在工作流结果中下载产物 `DEKT-GUI-windows`。
4. 解压 `DEKT-GUI-windows.zip`，运行 `DEKT-GUI/DEKT-GUI.exe`。

工作流文件：

- `.github/workflows/build-dekt-gui-windows.yml`

如需本地 Windows 打包（不走 GitHub）：

```bat
cd dekt_gui_app
build_windows.bat
```

Windows 本地产物：

- 目录：`dekt_gui_app\\dist\\DEKT-GUI`
- 可执行文件：`dekt_gui_app\\dist\\DEKT-GUI\\DEKT-GUI.exe`

说明：

- PyInstaller 不支持在 macOS/Linux 直接构建 Windows `.exe`
- 若需本地打 Windows 包，请在 Windows 主机（或 Windows VM）运行 `build_windows.bat`

## 项目状态

当前阶段：**Alpha（手动流程可用）**

### 阶段清单

- ✅ 凭据页（手动 Token / Gist / 验证 / 本地持久化）
- ✅ 监控页（6 个栏目手动刷新，表格操作）
- ✅ 打卡页（手动签到/签退，含时间窗校验）
- ✅ 活动页（我的活动列表 + 详情弹窗）
- ✅ 二维码查看（监控/打卡/活动表格右键）
- ✅ 课程详情增强（封面、地图预览、分区详情）
- ⏳ 报名队列页（UI 尚未接线）
- ⏳ 定时调度 / 后台任务（尚未开始）

### 下一阶段里程碑

- 报名队列页
- 定时调度 + 后台任务
- 更完善的发布流程（产物命名/版本化）
