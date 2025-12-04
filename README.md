# 北理工 Quantumult X 脚本合集

本项目包含用于北理工**第二课堂**（微信小程序）和**校园卡**的 Quantumult X 脚本，支持自动获取 Token、监控新活动、自动报名、活动签到提醒、校园卡余额监控等功能。

## 更新日志

### 2025-12-03
- 修复：在 BoxJS 指定运行时课程 ID 或本地脚本传入课程 ID 时，未自动签到/签退的问题。现在即使列表接口有返回，也会单独处理目标 ID。
- 优化：当仅传入单个课程 ID 时（如 `node local_dekt_signin.js 451`），执行完毕不再等待 15–30 秒随机延时。
- 修复：通知与日志中偶发的 `undefined` 标题；目标 ID 路径下会尽量解析并展示课程名称。
- 逻辑：`autoSignAll=false` 时，目标 ID 一定会处理；`autoSignAll=true` 时，若该课程已在列表阶段处理过则跳过以避免重复。

## 脚本列表

### 1. 第二课堂 (Second Classroom)

前缀: `dekt_`

*   **`dekt_cookie.js` (获取 Token)**
    *   **功能**: 监听第二课堂小程序的网络请求，自动提取并保存 Token 和 Headers。
    *   **使用**: 配置 Rewrite 规则，进入小程序刷新列表即可触发。
    *   **Gist 同步**: 支持将 Token 同步到 GitHub Gist。

*   **`dekt_monitor.js` (监控与报名)**
    *   **功能**: 定时监控第二课堂的新活动。
    *   **特性**: 支持按学院/年级筛选、捡漏模式、指定 ID 报名、自动报名栏目过滤。

*   **`dekt_my_activities.js` (我的活动)**
    *   **功能**: 定时检查"我的活动"列表，在签到/签退时间内发送通知并提供二维码链接。

*   **`dekt_signup.js` (自动报名)**
    *   **功能**: 从 BoxJS 读取待报名列表，自动等待并在报名时间进行并发报名，成功后通知。
    *   **特性**: 支持并发报名（T-0.5s ~ T+0.5s 窗口），提高抢课成功率。

*   **`dekt_signin.js` (自动签到)**
    *   **功能**: 自动检查已报名课程并进行签到/签退（需配合 BoxJS 配置）。
    *   **特性**: 支持虚拟定位、自动检测签到/签退时间窗口。

*   **`dekt_unenroll.js` (取消报名)**
    *   **功能**: 取消已报名的第二课堂课程。
    *   **使用**: 手动运行，需在 BoxJS 配置课程 ID 和用户 ID。

*   **`dekt_clean_blacklist.js` (清理黑名单)**
    *   **功能**: 自动移除黑名单中已结束/已取消的课程 ID，保持黑名单整洁。

### 2. 校园卡 (Campus Card)

前缀: `card_`

*   **`card_cookie.js` (获取 Cookie)**
    *   **功能**: 监听校园卡查询页面的请求，获取 Session ID 和 OpenID。
    *   **使用**: 进入"北理工校园卡"微信公众号 -> 账单查询，触发重写。
    *   **特性**: 从 URL/Cookie/Referer/Location/响应体多信源提取凭证。

*   **`card_balance.js` (余额监控)**
    *   **功能**: 定时查询校园卡余额，低于设定值时发送通知。
    *   **特性**: 支持 Gist 兜底读取凭证。

*   **`card_query_trade.py` (交易查询)**
    *   **功能**: Python 脚本，用于查询校园卡交易流水并导出为 CSV/Excel。
    *   **使用**: `python card_query_trade.py -d 60 -o output.xlsx`

### 3. 本地调试工具 (Node.js)

前缀: `local_`

*   **`local_env.js`**: 本地 Env 环境模拟模块，为其他本地脚本提供配置读写和网络请求能力。
*   **`local_dekt_monitor.js`**: 本地运行 `dekt_monitor.js` 的封装，支持指定报名 ID。
    *   用法: `node local_dekt_monitor.js [--enrollId=123]`
*   **`local_dekt_signin.js`**: 本地签到工具，支持虚拟定位。
    *   用法: `node local_dekt_signin.js [课程ID1] [课程ID2] ...`
*   **`local_dekt_my_activities.js`**: 本地运行我的活动脚本，验证时长字段获取逻辑。
    *   用法: `node local_dekt_my_activities.js`
*   **`local_dekt_unenroll.js`**: 本地取消报名工具。
    *   用法: `node local_dekt_unenroll.js [--course=451] [--user=9028711]`
*   **`local_dekt_get_qr.js`**: 获取活动二维码并保存到 `qrcodes/` 目录。
    *   用法: `node local_dekt_get_qr.js`
*   **`local_sync_gist.js`**: 从 Gist 同步配置到本地 `.env`。
    *   用法: `node local_sync_gist.js`
*   **`local_card_probe.js`**: 校园卡凭证探测工具，通过学工号获取 openid/JSESSIONID。
    *   用法: 配置 `.env` 中的 `bit_card_idserial`，运行 `node local_card_probe.js`
*   **`local_card_gist_check.js`**: 校园卡 Gist 校验工具，拉取并展示已存储的凭证。
    *   用法: `node local_card_gist_check.js`

### 4. 辅助工具

*   **`audit_duration.js`**: 审计脚本，统计课程时长字段来源可靠性。
    *   用法: `node audit_duration.js`
*   **`unpack_capture.py`**: 抓包解包工具，解压 Proxyman/Charles 导出的数据。
    *   用法: `python unpack_capture.py <root_dir> [keyword] [path_contains]`

## 使用说明
### Copilot 提示词

- 说明文件：`.github/copilot-instructions.md`
- 用法：在 Copilot Chat 提问时可加上“请遵循仓库的 copilot-instructions.md”，或使用 `@workspace` 让其读取仓库上下文。
- 建议：在需要更强上下文的脚本顶部加入短注释块，声明目标、环境（QX/本地）、约束（不泄露敏感信息、CommonJS 等）。

### 1. Quantumult X 配置

**Rewrite (重写):**
请参考 `dekt_rewrite.snippet` (第二课堂) 和 `card_rewrite.snippet` (校园卡)。

```conf
# 第二课堂 Cookie
^https:\/\/qcbldekt\.bit\.edu\.cn\/api\/course\/list url script-request-header https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/dekt_cookie.js

# 校园卡 Cookie
^https:\/\/dkykt\.info\.bit\.edu\.cn\/.* url script-request-header https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/card_cookie.js
^https:\/\/dkykt\.info\.bit\.edu\.cn\/.* url script-response-header https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/card_cookie.js
^https:\/\/dkykt\.info\.bit\.edu\.cn\/.* url script-response-body https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/card_cookie.js
```

**Task (定时任务):**
请参考 `dekt_task.json`。

```conf
# 第二课堂监控 (建议 2 分钟一次)
*/2 8-22 * * * https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/dekt_monitor.js, tag=第二课堂监控, enabled=true

# 第二课堂提醒
0 8-22 * * * https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/dekt_my_activities.js, tag=第二课堂提醒, enabled=true

# 校园卡余额监控 (每天中午 12 点)
0 12 * * * https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/card_balance.js, tag=校园卡余额监控, enabled=true
```

### 2. BoxJS 配置

订阅地址: `https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/boxjs.json`

> 提示：`card_cookie.js` 会从 URL/Cookie/Referer/Location/响应体多处提取 openid 与 JSESSIONID，并尝试自动捕获学工号（idserial）；信息不全时先写本地，补全后再同步 Gist（字段包含 jsessionid/openid/idserial/updated_at）。

如需同步/兜底读取 Gist，请在 BoxJS 配置：

- `bit_sc_github_token`：GitHub Token（访问 Gist，可选）
- `bit_sc_gist_id`：Gist ID（可选）
- `bit_card_gist_filename`：Gist 文件名（默认 `bit_card_cookies.json`）
- `bit_card_idserial`：学工号（自动捕获失败时可手动填写，用于主动刷新与本地探测）

`card_balance.js` 会优先使用本地 BoxJS 值；若缺失，会尝试从上述 Gist 兜底读取。

#### 第二课堂签到相关键

- `bit_sc_auto_sign_all`: 是否根据“签到列表接口”批量自动签到/签退（默认 `false`）。开启后会对列表中的“按时长计分”的活动在时间窗口内尝试签到/签退。
- `bit_sc_runtime_sign_ids`: 运行时目标课程 ID（逗号/空格分隔）。
    - 目标 ID 总是会被单独处理；即使列表接口返回了该课程，也会在 `autoSignAll=false` 时再次按目标 ID 尝试。
    - 当仅设置了一个 ID 时，执行完成后会跳过 15–30 秒的随机等待。
    - 本地脚本 `node local_dekt_signin.js <id1> <id2> ...` 的传参与该键等效（会合并去重）。
    - 若 `autoSignAll=true` 且某课程已在“列表阶段”处理过，则会跳过重复处理以避免重复请求。

#### 自动报名栏目（`bit_sc_auto_categories`）

- **用途**: 在 BoxJS 中多选要自动报名/捡漏的栏目。脚本将仅对选中的栏目执行自动报名或捡漏；对于未选中的栏目仍会发送通知，但不会尝试自动报名。
- **Key**: `bit_sc_auto_categories`
- **类型**: 多选（`selects`），项的 `key` 为栏目 ID（1-6），`label` 为栏目名称。默认包含 `不限` 选项表示允许所有栏目自动报名。
- **支持的值格式**: 脚本兼容多种 BoxJS 返回格式：
    - JSON 数组（例如 `[1,3]` 或 `["理想信念","社会贡献"]`）
    - 逗号分隔字符串（例如 `1,3` 或 `理想信念,社会贡献`）
    - 单项字符串或数字（例如 `1` 或 `理想信念`）
    - 字符串 `不限`（表示允许所有栏目自动报名）
- **示例**:
    - 选中“理想信念”和“社会贡献”（ID 为 1 和 3），BoxJS 可能保存为 `[1,3]`，脚本会识别为只对这两个栏目自动报名。
    - 若想对所有栏目自动报名，请选择 `不限`，或不配置该项。

该功能兼容通过栏目名称或 ID 设置的旧配置，因此即使 BoxJS 返回名称（例如 `"理想信念"`），脚本仍会正确识别。

### 3. 本地调试

1.  安装依赖: `npm install`
2.  配置 `.env` (或通过 `local_sync_gist.js` 同步)。
3.  运行对应脚本，例如 `node local_dekt_debug.js`。

## 注意事项

*   **Token/Cookie 有效期**: 需定期进入相应的小程序/页面刷新以更新 Token。
*   **Gzip**: 本地脚本需注意处理 Gzip 压缩的响应。

## 声明

仅供学习交流使用，请勿用于非法用途。
