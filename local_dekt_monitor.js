/*
 * 脚本名称：本地调试-第二课堂监控
 * 描述：在本地 Node.js 环境中运行 dekt_monitor.js，用于测试监控逻辑。
 * 用法：node local_dekt_debug.js
 */
const fs = require('fs');
const path = require('path');
const Env = require('./local_env');
const { spawnSync } = require('child_process');

// Make Env available globally
global.Env = Env;
// Mock $done
global.$done = (val) => {
    console.log("[System] $done called with:", val);
};

const scriptPath = path.join(__dirname, 'dekt_monitor.js');

if (!fs.existsSync(scriptPath)) {
    console.error(`Script not found: ${scriptPath}`);
    process.exit(1);
}

const scriptContent = fs.readFileSync(scriptPath, 'utf8');

// Remove the Env definition from the script content to avoid conflict and use our local Env
const cleanScriptContent = scriptContent.replace(/function Env\s*\(.*?\)\s*\{[\s\S]*\}/, '// Env definition removed');

console.log("=== Starting Local Debug: bit_monitor.js ===");

try {
    // 先同步 .env（从 Gist 拉取最新 Token/Headers）
    try {
        const syncPath = path.join(__dirname, 'local_sync_gist.js');
        spawnSync(process.execPath, [syncPath], { stdio: 'inherit' });
    } catch (e) {
        console.log('[LocalSync] 同步环境失败（忽略继续）:', e.message || e);
    }

    // Execute the script content
    eval(cleanScriptContent);
} catch (e) {
    console.error("Runtime Error:", e);
}
