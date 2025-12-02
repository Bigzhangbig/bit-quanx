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
    // Parse CLI args: default no auto-enroll, allow specifying enroll id
    // Usage examples:
    //   node local_dekt_monitor.js                  -> no auto enroll
    //   node local_dekt_monitor.js --enrollId=123   -> target enroll id 123
    //   node local_dekt_monitor.js 123              -> positional enroll id
    const argv = process.argv.slice(2);
    let enrollId = null;
    for (const a of argv) {
        const m = a.match(/^--?enrollId=(\d+)$/i);
        if (m) {
            enrollId = m[1];
            break;
        }
        if (/^\d+$/.test(a)) {
            enrollId = a;
            break;
        }
    }
    // Expose control flags for downstream script
    global.DEKT_DEBUG = true; // 本地默认打开 Debug 模式
    global.DEKT_AUTO_ENROLL = false; // 默认不自动报名
    if (enrollId) {
        global.DEKT_ENROLL_ID = enrollId;
        console.log(`[LocalDebug] 指定报名ID: ${enrollId}`);
    } else {
        console.log('[LocalDebug] 未指定报名ID，保持仅监控模式');
    }

    // 增强 Debug：详细打印请求，且在无参数时禁止报名请求
    try {
        const originalRequest = Env.prototype.request;
        Env.prototype.request = function(method, options, callback) {
            const urlStr = typeof options === 'string' ? options : (options && options.url) || '';
            const body = typeof options === 'object' ? options.body : undefined;
            if (global.DEKT_DEBUG) {
                console.log(`[Debug][${method}] url=${urlStr}`);
                if (body) console.log(`[Debug][${method}] body=${typeof body === 'string' ? body : JSON.stringify(body)}`);
            }
            const isSignup = /enroll|signup|apply|register|enrol|join/i.test(urlStr);
            const hasIdParam = !!global.DEKT_ENROLL_ID;
            if (!hasIdParam && isSignup && global.DEKT_AUTO_ENROLL === false) {
                console.log(`[LocalDebug] 已阻止报名请求: ${urlStr}`);
                const fakeResBody = JSON.stringify({ data: null, code: -999, message: '本地调试：已禁用自动报名' });
                const fakeRes = { statusCode: 200, headers: {} };
                return callback(null, fakeRes, fakeResBody);
            }
            return originalRequest.call(this, method, options, callback);
        };
        // 拦截待报名列表写入，避免监控阶段累积 signup_list
        const originalSetdata = Env.prototype.setdata;
        Env.prototype.setdata = function(val, key) {
            if (!global.DEKT_ENROLL_ID && global.DEKT_AUTO_ENROLL === false && key === 'bit_sc_signup_list') {
                console.log('[LocalDebug] 阻止写入待报名列表，保持为空 []');
                return originalSetdata.call(this, '[]', key);
            }
            return originalSetdata.call(this, val, key);
        };
    } catch (patchErr) {
        console.log('[LocalDebug] Patch Env.request 失败（继续运行监控）:', patchErr?.message || patchErr);
    }

    // 先同步 .env（从 Gist 拉取最新 Token/Headers）
    try {
        const syncPath = path.join(__dirname, 'local_sync_gist.js');
        spawnSync(process.execPath, [syncPath], { stdio: 'inherit' });
    } catch (e) {
        console.log('[LocalSync] 同步环境失败（忽略继续）:', e.message || e);
    }

    // 默认本地 Debug 模式：关闭捡漏与全量自动报名，并清空报名清单（覆盖 .env 和 boxjs）
    try {
        // 覆盖 .env 中的相关键，确保监控脚本读取到本地调试配置
        const env = new Env('LocalDebug');
        env.setdata('true', 'bit_sc_debug');
        env.setdata('false', 'bit_sc_pickup_mode');
        env.setdata('[]', 'bit_sc_signup_list');
        if (!enrollId) {
            env.setdata('', 'dekt_course_id');
            env.setdata('', 'DEKT_COURSE_ID');
        } else {
            env.setdata(String(enrollId), 'dekt_course_id');
            env.setdata(String(enrollId), 'DEKT_COURSE_ID');
        }

        const boxjsPath = path.join(__dirname, 'boxjs.json');
        if (fs.existsSync(boxjsPath)) {
            const box = JSON.parse(fs.readFileSync(boxjsPath, 'utf8'));
            box.boxjs = box.boxjs || {};
            const argPickup = argv.find(a => /^--?pickup=(true|false)$/i.test(a));
            const forcePickup = argPickup ? /true$/i.test(argPickup) : null;
            // 默认关闭，除非用户明确 --pickup=true
            box.boxjs.pickup_mode = forcePickup === null ? "false" : String(forcePickup);
            box.boxjs.auto_sign_all = "false";
            box.boxjs.signup_list = "[]";
            // 清空运行时报名ID，避免脚本残留触发
            if (!enrollId) {
                box.boxjs.runtime_sign_ids = "";
            } else {
                box.boxjs.runtime_sign_ids = String(enrollId);
            }
            fs.writeFileSync(boxjsPath, JSON.stringify(box, null, 2));
            console.log(`[LocalDebug] 已设置本地调试：pickup_mode=${box.boxjs.pickup_mode}, auto_sign_all=${box.boxjs.auto_sign_all}, signup_list=${box.boxjs.signup_list}, runtime_sign_ids=${box.boxjs.runtime_sign_ids}`);
        } else {
            console.log('[LocalDebug] 未找到 boxjs.json，跳过捡漏配置调整');
        }
    } catch (e) {
        console.log('[LocalDebug] 调整 boxjs.json 失败（忽略继续）:', e.message || e);
    }

    // 带参数时：调用报名脚本报名指定 ID；否则仅监控
    if (enrollId) {
        try {
            // 读取报名脚本源码并移除其内置 Env，使其使用本地 Env
            const repoSignupPath = path.join(__dirname, 'dekt_signup.js');
            if (!fs.existsSync(repoSignupPath)) {
                console.log('[LocalDebug] 未找到 dekt_signup.js，回退为监控模式');
                eval(cleanScriptContent);
            } else {
                const signupContent = fs.readFileSync(repoSignupPath, 'utf8');
                const cleanSignup = signupContent.replace(/function Env\s*\(.*?\)\s*\{[\s\S]*\}/, '// Env definition removed');
                const env = new Env('LocalDebug');
                // 构造只包含指定ID的待报名列表，不改动 boxjs.json
                const nowStr = new Date().toISOString().slice(0,16).replace('T',' ');
                const list = [{ id: parseInt(enrollId), title: `指定报名(${enrollId})`, time: nowStr }];
                env.setdata(JSON.stringify(list), 'bit_sc_signup_list');
                console.log(`[LocalDebug] 注入待报名列表: ${env.getdata('bit_sc_signup_list')}`);
                // 执行报名脚本
                console.log(`[LocalDebug] 执行报名脚本(dekt_signup.js): ID=${enrollId}`);
                eval(cleanSignup);
            }
        } catch (e) {
            console.log('[LocalDebug] 执行报名脚本失败，回退为监控模式:', e.message || e);
            eval(cleanScriptContent);
        }
    } else {
        // Execute the script content (monitor-only)
        eval(cleanScriptContent);
    }
} catch (e) {
    console.error("Runtime Error:", e);
}
