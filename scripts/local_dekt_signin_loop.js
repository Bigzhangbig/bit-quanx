/*
 * 脚本名称：本地循环-第二课堂签到/签退
 * 描述：循环调用 local_dekt_signin.js，持续检测并处理今天处于签到/签退窗口的全部课程。
 *
 * 用法：
 *   node local_dekt_signin_loop.js
 *   node local_dekt_signin_loop.js --interval=60
 *   node local_dekt_signin_loop.js --interval=30 --max-loops=20
 *
 * 参数：
 *   --interval=<秒>     每轮检测间隔（默认 60 秒）
 *   --max-loops=<次数>  最大循环次数（默认不限，直到手动停止）
 */

const path = require('path');
const { spawnSync } = require('child_process');
const Env = require('./local_env');

const env = new Env('LocalSignLoop');

function nowTs() {
    const d = new Date();
    const pad = (n, w = 2) => String(n).padStart(w, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function log(msg) {
    console.log(`[${nowTs()}] ${msg}`);
}

function parseArgs(argv) {
    let intervalSec = 60;
    let maxLoops = 0;

    for (const arg of argv) {
        if (arg.startsWith('--interval=')) {
            const v = Number(arg.split('=')[1]);
            if (Number.isFinite(v) && v > 0) intervalSec = v;
        } else if (arg.startsWith('--max-loops=')) {
            const v = Number(arg.split('=')[1]);
            if (Number.isFinite(v) && v > 0) maxLoops = Math.floor(v);
        }
    }

    return { intervalSec, maxLoops };
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function isToday(d) {
    const now = new Date();
    return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
}

async function run() {
    const { intervalSec, maxLoops } = parseArgs(process.argv.slice(2));

    // 开启“处理全部课程”模式，依赖 dekt_signin.js 在窗口内自动判断签到或签退。
    env.setdata('true', 'bit_sc_auto_sign_all');
    env.setdata('', 'bit_sc_runtime_sign_ids');

    const runner = path.join(__dirname, 'local_dekt_signin.js');
    let loop = 0;

    log(`启动循环检测：interval=${intervalSec}s, maxLoops=${maxLoops || '无限'}`);
    log('已设置 bit_sc_auto_sign_all=true，脚本将尝试处理今天窗口内的全部课程。');

    while (true) {
        const startAt = Date.now();
        const now = new Date();

        if (!isToday(now)) {
            log('日期已切换到次日，自动停止循环。');
            break;
        }

        loop += 1;
        log(`第 ${loop} 轮开始`);

        const res = spawnSync(process.execPath, [runner], {
            stdio: 'inherit',
            env: {
                ...process.env,
                DEKT_FORCE_AUTO_SIGN_ALL: '1'
            }
        });

        if (res.error) {
            log(`第 ${loop} 轮执行异常: ${res.error.message || res.error}`);
        } else {
            log(`第 ${loop} 轮完成，exitCode=${res.status}`);
        }

        if (maxLoops > 0 && loop >= maxLoops) {
            log(`达到最大循环次数 ${maxLoops}，停止运行。`);
            break;
        }

        const spent = Date.now() - startAt;
        const waitMs = Math.max(0, intervalSec * 1000 - spent);
        log(`等待 ${(waitMs / 1000).toFixed(1)} 秒进入下一轮...`);
        await sleep(waitMs);
    }

    log('循环任务结束。');
}

run().catch(err => {
    log(`脚本异常退出: ${err && err.stack ? err.stack : err}`);
    process.exitCode = 1;
});
