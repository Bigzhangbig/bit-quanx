# 北理工第二课堂 Quantumult X 助手

本项目包含用于 Quantumult X 的脚本，实现北理工第二课堂新活动监控通知及自动/手动报名功能。

## 功能特性

- **活动监控**：定时检查第二课堂新发布的活动，并发送通知。
- **自动/手动报名**：配置课程 ID 后，可一键报名指定课程。
- **多维度筛选**：支持按学院、年级、活动类型筛选通知。
- **BoxJS 支持**：可视化配置参数，无需修改脚本代码。

## 使用说明

### 1. 添加重写规则 (Rewrite)

在 Quantumult X 的配置文件中添加以下重写规则，用于获取 Token 和 Headers。

```conf
[rewrite_local]
# 获取第二课堂 Token
^https:\/\/qcbldekt\.bit\.edu\.cn\/api\/user\/info url script-request-header https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/bit_cookie.js
```

### 2. 添加任务 (Task)

#### 监控脚本
建议设置为每 2 小时运行一次（8:00 - 22:00）。

```conf
[task_local]
30 8-22/2 * * * https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/bit_monitor.js, tag=第二课堂监控, enabled=true
```

#### 报名脚本
此脚本通常手动运行，或在需要抢课时设置高频定时任务。

```conf
[task_local]
0 0 0 0 0 https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/bit_signup.js, tag=第二课堂报名, enabled=true
```

### 3. 配置 BoxJS

1. 在 Quantumult X 中添加 BoxJS 订阅（如果尚未添加）。
2. 添加本项目的 BoxJS 订阅链接：`https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/bit_boxjs.json`
3. 在 BoxJS 应用中找到 "北理工第二课堂助手"。
4. **获取 Token**：
   - 打开 "i北理" 小程序 -> 第二课堂。
   - 此时 Quantumult X 应该会弹出 "获取 Token 成功" 的通知。
   - 回到 BoxJS，确认 `bit_sc_token` 已有值。
5. **配置筛选**（可选）：设置感兴趣的学院、年级等。
6. **配置报名**（可选）：
   - 在 "报名课程ID" 中输入你想报名的课程 ID（例如 `370`）。
   - 监控脚本在运行时会优先尝试报名此 ID 的课程。
   - 也可以手动运行 "第二课堂报名" 任务来尝试报名。

## 高级功能

### 自动设置报名 ID
当监控脚本检测到状态为 **"未开始"** 的新活动时，会自动将该活动的 ID 填入 BoxJS 的 `bit_sc_signup_course_id` 中。
你只需要在活动开始前，确保已添加并开启了报名脚本的定时任务（或手动运行一次报名脚本）。

### 自动捡漏报名
在 BoxJS 中开启 **"开启调试日志"** (Debug 模式) 后，监控脚本会尝试自动报名所有 **"进行中"**、**"未报名"** 且 **"有名额"** 的课程。
- 适用于捡漏热门课程。
- 成功捡漏后会发送通知。

### 点击通知跳转
收到新活动通知时，点击通知即可直接跳转到 "i北理" 小程序（需确保手机已安装微信）。

## 注意事项

- Token 有效期较短，如果脚本提示 Token 失效，请重新进入小程序刷新。
- 报名功能依赖于固定的 Template ID，如果学校更改了接口，可能需要更新脚本。
- 请勿滥用高频请求，以免被封禁。

## 抓包分析 (开发者参考)

- 监控接口: `/api/course/list`
- 报名接口: `/api/course/apply` (POST)
- 报名参数: `{"course_id": 123, "template_id": "..."}`