/*
 * 脚本名称：本地调试-第二课堂签到
 * 描述：在本地 Node.js 环境中运行 dekt_signin.js，支持虚拟定位签到。
 * 用法：node local_dekt_signin.js
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

const scriptPath = path.join(__dirname, 'dekt_signin.js');

if (!fs.existsSync(scriptPath)) {
    console.error(`Script not found: ${scriptPath}`);
    process.exit(1);
}

const scriptContent = fs.readFileSync(scriptPath, 'utf8');

// 获取命令行参数中的 course_id
const args = process.argv.slice(2);
const forceAllFromEnv = String(process.env.DEKT_FORCE_AUTO_SIGN_ALL || '').toLowerCase() === 'true'
    || String(process.env.DEKT_FORCE_AUTO_SIGN_ALL || '') === '1';
const forceAllFromArg = args.includes('--all') || args.includes('--auto-sign-all');
const forceAll = forceAllFromEnv || forceAllFromArg;
const targetIds = args.filter(a => !a.startsWith('--'));

if (targetIds.length > 0) {
    global.DEKT_TARGET_IDS = targetIds;
    console.log(`[Local Debug] 指定课程 ID: ${global.DEKT_TARGET_IDS.join(', ')}`);
} else if (forceAll) {
    console.log('[Local Debug] 未指定课程 ID，但已启用批量签到模式');
    global.DEKT_BLOCK_LIST_MODE = false;
} else {
    console.log(`[Local Debug] 未指定课程 ID，默认禁用批量签到 (防止误操作)`);
    global.DEKT_BLOCK_LIST_MODE = true;
}

// Remove the Env definition from the script content to avoid conflict and use our local Env
const cleanScriptContent = scriptContent.replace(/function Env\s*\(.*?\)\s*\{[\s\S]*\}/, '// Env definition removed');

console.log("=== Starting Local Debug: bit_signin.js ===");

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
