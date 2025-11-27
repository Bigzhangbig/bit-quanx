/*
 * 脚本名称：本地调试-第二课堂我的活动
 * 描述：在本地 Node.js 环境中运行 dekt_my_activities.js，用于验证“时长”等字段获取逻辑与日志。
 * 用法：
 *   1) 在项目根目录创建 .env 文件，写入：
 *        bit_sc_token=你的BearerToken
 *   2) 运行：
 *        node local_dekt_my_activities.js
 */
const fs = require('fs');
const path = require('path');
const Env = require('./local_env');

// 将本地 Env 注入到全局，供脚本使用
global.Env = Env;
// 模拟 $done（兼容脚本结束调用）
global.$done = (val) => {
  console.log('[System] $done called with:', val);
};

const scriptPath = path.join(__dirname, 'dekt_my_activities.js');

if (!fs.existsSync(scriptPath)) {
  console.error(`Script not found: ${scriptPath}`);
  process.exit(1);
}

const scriptContent = fs.readFileSync(scriptPath, 'utf8');

// 移除脚本内置的 Env 定义，避免与本地 Env 冲突
const cleanScriptContent = scriptContent.replace(/function Env\s*\(.*?\)\s*\{[\s\S]*\}/, '// Env definition removed');

console.log('=== Starting Local Debug: dekt_my_activities.js ===');

try {
  eval(cleanScriptContent);
} catch (e) {
  console.error('Runtime Error:', e);
}
