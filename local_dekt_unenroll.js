/*
 * 脚本名称：本地调试-第二课堂取消报名
 * 描述：在本地 Node.js 环境中运行 dekt_unenroll.js，仅使用抓包 API 与报文
 * 用法：
 *   1) 在项目根目录创建 .env，至少包含：
 *        bit_sc_token=Bearer xxxxx
 *        dekt_user_id=9028711           # 或 bit_sc_user_id
 *        dekt_course_id=451             # 或 bit_sc_unenroll_course_id / DEKT_COURSE_ID（可选，留空则使用最后成功报名的课程）
 *      可选：
 *        bit_sc_headers={"User-Agent":"...","Referer":"...","Host":"qcbldekt.bit.edu.cn"}
 *   2) 运行：
 *        node local_dekt_unenroll.js [--course=451] [--user=9028711]
 */
const fs = require('fs');
const path = require('path');
const Env = require('./local_env');
const { spawnSync } = require('child_process');

// 将本地 Env 注入到全局
global.Env = Env;
// 模拟 $done（兼容脚本结束调用）
global.$done = (val) => {
  console.log('[System] $done called with:', val);
};

// 解析命令行参数
const args = process.argv.slice(2);
const argMap = {};
for (const a of args) {
  const m = a.match(/^--([^=]+)=(.*)$/);
  if (m) argMap[m[1]] = m[2];
}

// 将 CLI 参数写入 .env（覆盖同名键），便于脚本通过 $.getdata 读取
(function seedEnvFromArgs(){
  const $ = new Env('LocalSeed');
  if (argMap.course) {
    $.setdata(String(argMap.course), 'dekt_course_id');
    // 兼容其他键名
    $.setdata(String(argMap.course), 'bit_sc_unenroll_course_id');
    $.setdata(String(argMap.course), 'DEKT_COURSE_ID');
    console.log(`[LocalSeed] 写入课程ID: ${argMap.course}`);
  }
  if (argMap.user) {
    $.setdata(String(argMap.user), 'dekt_user_id');
    $.setdata(String(argMap.user), 'bit_sc_user_id');
    $.setdata(String(argMap.user), 'DEKT_USER_ID');
    console.log(`[LocalSeed] 写入用户ID: ${argMap.user}`);
  }
  if (argMap.token) {
    $.setdata(String(argMap.token), 'bit_sc_token');
    console.log(`[LocalSeed] 写入Token`);
  }
  if (argMap.headers) {
    try {
      // 支持传入 JSON 字符串
      const obj = JSON.parse(argMap.headers);
      $.setdata(JSON.stringify(obj), 'bit_sc_headers');
      console.log(`[LocalSeed] 写入Headers(JSON)`);
    } catch (_) {
      // 直接原样写入
      $.setdata(String(argMap.headers), 'bit_sc_headers');
      console.log(`[LocalSeed] 写入Headers(原样)`);
    }
  }
})();

const scriptPath = path.join(__dirname, 'dekt_unenroll.js');

if (!fs.existsSync(scriptPath)) {
  console.error(`Script not found: ${scriptPath}`);
  process.exit(1);
}

const scriptContent = fs.readFileSync(scriptPath, 'utf8');

// 移除脚本内置的 Env 定义，避免与本地 Env 冲突
const cleanScriptContent = scriptContent.replace(/function Env\s*\(.*?\)\s*\{[\s\S]*\}/, '// Env definition removed');

console.log('=== Starting Local Debug: dekt_unenroll.js ===');

try {
  // 先同步 .env（从 Gist 拉取最新 Token/Headers）
  try {
    const syncPath = path.join(__dirname, 'local_sync_gist.js');
    spawnSync(process.execPath, [syncPath], { stdio: 'inherit' });
  } catch (e) {
    console.log('[LocalSync] 同步环境失败（忽略继续）:', e.message || e);
  }

  eval(cleanScriptContent);
} catch (e) {
  console.error('Runtime Error:', e);
}
