# 北理工 自用学习脚本合集

本项目包含 Quantumult X 脚本。

# 你需要在 24 小时内删除本仓库！！！！！！！！
# 本仓库 不含 任何修改数据的代码！！！！！！！
# 本仓库 不会 提供教程！！！！！！！！！！！！
# 本仓库 不能 帮你修改余额！！！！！！！！！！

## 脚本列表

说明：仓库中的 JS 脚本已统一整理到 `scripts/` 目录。

### 1. 你懂的

前缀: `dekt_`

*   **`dekt_cookie.js` (获取 Token)**
    *   **功能**: 监听小程序的网络请求，自动提取并保存 Token 和 Headers。
    *   **使用**: 配置 Rewrite 规则，进入小程序刷新列表即可触发。
    *   **Gist 同步**: 支持将 Token 同步到 GitHub Gist。

*   **`dekt_monitor.js` (监控)**
    *   **功能**: 定时监控的新活动。
    *   **特性**: 支持按学院/年级筛选过滤。

*   **`dekt_my_activities.js` (我的活动)**
    *   **功能**: 定时检查"我的活动"列表，在签到/签退时间内发送通知。

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
*   **`local_dekt_monitor.js`**: 本地运行 `dekt_monitor.js` 的封装。
    *   用法: `node scripts/local_dekt_monitor.js [--enrollId=123]`
*   **`local_dekt_my_activities.js`**: 本地运行我的活动脚本，验证时长字段获取逻辑。
    *   用法: `node scripts/local_dekt_my_activities.js`
*   **`local_dekt_unenroll.js`**: 本地取消报名工具。
    *   用法: `node scripts/local_dekt_unenroll.js [--course=451]`
*   **`local_dekt_signin_loop.js`**: 本地循环检测签到/签退工具，自动处理今天窗口内全部课程。
    *   用法: `node scripts/local_dekt_signin_loop.js [--interval=60] [--max-loops=20]`
*   **`local_sync_gist.js`**: 从 Gist 同步配置到本地 `.env`。
    *   用法: `node scripts/local_sync_gist.js`
*   **`local_card_probe.js`**: 校园卡凭证探测工具，通过学工号获取 openid/JSESSIONID。
    *   用法: 配置 `.env` 中的 `bit_card_idserial`，运行 `node scripts/local_card_probe.js`
*   **`local_card_gist_check.js`**: 校园卡 Gist 校验工具，拉取并展示已存储的凭证。
    *   用法: `node scripts/local_card_gist_check.js`

## 使用说明

### 第二课堂最小鉴权结论（实测）

* `GET /api/user/info`：仅需 `Authorization: Bearer <token>`，可从返回的 `data.id` 获取当前 `user_id`。
* `POST /api/course/apply`（报名）：不强制要求 `user_id`。
* `POST /api/course/cancelApply`（取消报名）：需要 `user_id`，缺失通常返回参数校验失败。
* 约定：仅在取消报名链路自动补齐 `user_id`；其他脚本（报名/监控/查询）不自动补齐 `user_id`。

### Copilot 提示词

- 说明文件：`.github/copilot-instructions.md`
- 用法：在 Copilot Chat 提问时可加上“请遵循仓库的 copilot-instructions.md”，或使用 `@workspace` 让其读取仓库上下文。
- 建议：在需要更强上下文的脚本顶部加入短注释块，声明目标、环境（QX/本地）、约束（不泄露敏感信息、CommonJS 等）。

# 声明
根据计算机软件保护条例
(2001年12月20日中华人民共和国国务院令第339号公布　根据2011年1月8日《国务院关于废止和修改部分行政法规的决定》第一次修订　根据2013年1月30日《国务院关于修改〈计算机软件保护条例〉的决定》第二次修订)
第十七条 为了学习和研究软件内含的设计思想和原理，通过安装、显示、传输或者存储软件等方式使用软件的，可以不经软件著作权人许可，不向其支付报酬。
请在24小时内删除本仓库
仅供学习交流使用，请勿用于非法用途。
