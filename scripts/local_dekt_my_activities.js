/*
 * 脚本名称：本地调试-第二课堂我的活动
 * 描述：在本地 Node.js 环境中运行 dekt_my_activities.js，用于验证“时长”等字段获取逻辑与日志。
 * 用法：
 *   1) 在项目根目录创建 .env 文件，写入：
 *        bit_sc_token=你的BearerToken
 *   2) 运行：
 *        node local_dekt_my_activities.js
 */
const path = require('path');
const Env = require('./local_env');
const { spawnSync } = require('child_process');

// 将本地 Env 注入到全局，供脚本使用
global.Env = Env;

// 本地调试：默认开启 debug（bit_sc_debug=true），若用户未显式设置
try {
  const _envProbe = new Env('LocalProbe');
  const cur = String(_envProbe.getdata('bit_sc_debug') || '').toLowerCase();
  if (cur !== 'true') {
    _envProbe.setdata('true', 'bit_sc_debug');
    console.log('[LocalDebug] 设置 bit_sc_debug=true (本地默认)');
  } else {
    console.log('[LocalDebug] 已开启 bit_sc_debug=true');
  }
} catch (e) {
  console.log('[LocalDebug] 无法设置本地 debug 标志：', e.message || e);
}

// 模拟 $done（兼容脚本结束调用）
global.$done = (val) => {
  console.log('[System] $done called with:', val);
};

console.log('=== Starting Local Debug: dekt_my_activities.run() ===');

(async () => {
  try {
    // 先同步 .env（从 Gist 拉取最新 Token/Headers）
    try {
      const syncPath = path.join(__dirname, 'local_sync_gist.js');
      spawnSync(process.execPath, [syncPath], { stdio: 'inherit' });
    } catch (e) {
      console.log('[LocalSync] 同步环境失败（忽略继续）:', e.message || e);
    }

    const { run } = require('./dekt_my_activities.js');
    const result = await run();
    console.log('[LocalResult] notifyItems count:', Array.isArray(result) ? result.length : 'n/a');
  } catch (e) {
    console.error('Runtime Error:', e);
  }
})();
