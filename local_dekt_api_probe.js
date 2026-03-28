/*
 * 脚本名称：本地只读接口探测-第二课堂
 * 用途：批量测试多个 API 的连通性与稳定性，定位 socket hang up/timeout 的具体分布。
 * 用法：
 *   node local_dekt_api_probe.js
 *   node local_dekt_api_probe.js --rounds=5 --timeout=12000
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

function parseArgs(argv) {
  const out = { rounds: 3, timeout: 12000 };
  for (const a of argv) {
    const m = a.match(/^--([^=]+)=(.*)$/);
    if (!m) continue;
    const k = m[1];
    const v = m[2];
    if (k === 'rounds') {
      const n = Number(v);
      if (Number.isFinite(n) && n > 0) out.rounds = Math.floor(n);
    } else if (k === 'timeout') {
      const n = Number(v);
      if (Number.isFinite(n) && n > 0) out.timeout = Math.floor(n);
    }
  }
  return out;
}

function readEnvMap() {
  const file = path.join(__dirname, '.env');
  if (!fs.existsSync(file)) return {};
  const map = {};
  const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  for (const lineRaw of lines) {
    const line = lineRaw.trim();
    if (!line || line.startsWith('#')) continue;
    const idx = line.indexOf('=');
    if (idx <= 0) continue;
    const k = line.slice(0, idx).trim();
    const v = line.slice(idx + 1).trim();
    map[k] = v;
  }
  return map;
}

function getToken(envMap) {
  let token = envMap.bit_sc_token || envMap.dekt_token || '';
  token = String(token || '').trim();
  if (!token) return '';
  if (!/^Bearer\s+/i.test(token)) token = `Bearer ${token}`;
  return token;
}

function httpGet(url, headers, timeoutMs) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const req = https.request(
      {
        protocol: u.protocol,
        hostname: u.hostname,
        port: u.port || 443,
        path: u.pathname + u.search,
        method: 'GET',
        headers,
      },
      (res) => {
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (c) => (body += c));
        res.on('end', () => resolve({ status: res.statusCode, body }));
      }
    );

    req.on('error', reject);
    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error('timeout'));
    });
    req.end();
  });
}

function parseJsonSafe(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function isOkResult(r) {
  if (!r || r.status !== 200) return false;
  const obj = parseJsonSafe(r.body);
  if (!obj) return false;
  return obj.code === 200;
}

function maskToken(t) {
  if (!t) return '(empty)';
  return t.replace(/Bearer\s+(.{6}).+(.{4})$/i, 'Bearer $1***$2');
}

function initStat() {
  return { ok: 0, fail: 0, errs: {} };
}

function markFail(stat, errText) {
  stat.fail += 1;
  const key = String(errText || 'unknown').toLowerCase();
  stat.errs[key] = (stat.errs[key] || 0) + 1;
}

async function probeOne(url, headers, timeout, stat) {
  try {
    const r = await httpGet(url, headers, timeout);
    if (isOkResult(r)) {
      stat.ok += 1;
    } else {
      const obj = parseJsonSafe(r.body) || {};
      markFail(stat, `http_${r.status}_code_${obj.code || 'unknown'}`);
    }
  } catch (e) {
    markFail(stat, e && e.message ? e.message : String(e));
  }
}

async function run() {
  const { rounds, timeout } = parseArgs(process.argv.slice(2));
  const envMap = readEnvMap();
  const token = getToken(envMap);
  if (!token) {
    console.log('❌ 未找到 token（.env 的 bit_sc_token/dekt_token）');
    process.exitCode = 1;
    return;
  }

  const headers = {
    Authorization: token,
    'Content-Type': 'application/json;charset=utf-8',
    Accept: 'application/json, text/plain, */*',
  };

  console.log(`🔐 token: ${maskToken(token)}`);
  console.log(`🔎 rounds=${rounds}, timeout=${timeout}ms`);

  // 先探测一次新版我的课程列表以提取 course_id，失败也继续测其它 API。
  let cid = String(envMap.bit_sc_unenroll_course_id || envMap.dekt_course_id || '').trim();
  try {
    // OLD: https://qcbldekt.bit.edu.cn/api/transcript/course/signIn/list?page=1&limit=1&type=1
    const listUrl = 'https://qcbldekt.bit.edu.cn/api/course/list/my?page=1&limit=1';
    const listR = await httpGet(listUrl, headers, timeout);
    const listObj = parseJsonSafe(listR.body) || {};
    const item = listObj.data && Array.isArray(listObj.data.items) ? listObj.data.items[0] : null;
    const fromList = item ? String(item.course_id || item.id || '') : '';
    if (fromList) cid = fromList;
    console.log(`📥 course/list/my preflight: status=${listR.status}, code=${listObj.code}, course_id=${cid || '(none)'}`);
  } catch (e) {
    console.log(`⚠️ course/list/my preflight 异常: ${e && e.message ? e.message : String(e)}`);
  }

  const stats = {
    userInfo: initStat(),
    warningList: initStat(),
    courseList: initStat(),
    myCourseList: initStat(),
    checkInInfo: initStat(),
    courseInfo: initStat(),
  };

  for (let i = 1; i <= rounds; i++) {
    await probeOne('https://qcbldekt.bit.edu.cn/api/user/info', headers, timeout, stats.userInfo);
    await probeOne('https://qcbldekt.bit.edu.cn/api/transcript/warning/list', headers, timeout, stats.warningList);
    await probeOne('https://qcbldekt.bit.edu.cn/api/course/list?page=1&limit=1&sign_status=1&transcript_index_id=1&transcript_index_type_id=0', headers, timeout, stats.courseList);
    await probeOne('https://qcbldekt.bit.edu.cn/api/course/list/my?page=1&limit=1', headers, timeout, stats.myCourseList);

    if (cid) {
      await probeOne(`https://qcbldekt.bit.edu.cn/api/transcript/checkIn/info?course_id=${cid}`, headers, timeout, stats.checkInInfo);
      await probeOne(`https://qcbldekt.bit.edu.cn/api/course/info/${cid}`, headers, timeout, stats.courseInfo);
    }
  }

  console.log('\n=== 探测结果 ===');
  console.log(`[user/info]                     ok=${stats.userInfo.ok}, fail=${stats.userInfo.fail}, errs=${JSON.stringify(stats.userInfo.errs)}`);
  console.log(`[transcript/warning/list]      ok=${stats.warningList.ok}, fail=${stats.warningList.fail}, errs=${JSON.stringify(stats.warningList.errs)}`);
  console.log(`[course/list]                  ok=${stats.courseList.ok}, fail=${stats.courseList.fail}, errs=${JSON.stringify(stats.courseList.errs)}`);
  console.log(`[course/list/my]               ok=${stats.myCourseList.ok}, fail=${stats.myCourseList.fail}, errs=${JSON.stringify(stats.myCourseList.errs)}`);
  if (cid) {
    console.log(`[transcript/checkIn/info]      ok=${stats.checkInInfo.ok}, fail=${stats.checkInInfo.fail}, errs=${JSON.stringify(stats.checkInInfo.errs)}`);
    console.log(`[course/info/${cid}]            ok=${stats.courseInfo.ok}, fail=${stats.courseInfo.fail}, errs=${JSON.stringify(stats.courseInfo.errs)}`);
  } else {
    console.log('⚠️ 未获取到 course_id，已跳过 checkIn/info 与 course/info 的对比探测');
  }
}

run().catch((e) => {
  console.log(`❌ probe 异常: ${e && e.stack ? e.stack : e}`);
  process.exitCode = 1;
});
