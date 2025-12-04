/*
 * 脚本名称：第二课堂时长字段审计工具
 * 作者：Gemini for User
 * 描述：本地 Node.js 脚本，用于统计第二课堂课程时长字段的来源可靠性。
 *       帮助开发者判断是否需要保留各种时长获取的兜底逻辑。
 * 
 * 用法：
 * 1. 在项目根目录创建 .env 文件，写入：
 *      bit_sc_token=你的BearerToken
 * 2. 运行：
 *      node audit_duration.js
 * 
 * 输出内容：
 * - 列表顶层有/缺失 duration 的课程数量
 * - transcript_index_type.duration 可用数量
 * - completion_flag_text 可解析分钟数的课程数量
 * - REST 详情缺失 duration 的课程数量
 * - 开发建议（是否可删除兜底逻辑）
 */
const fs = require('fs');
const https = require('https');
const zlib = require('zlib');
const path = require('path');

function loadEnv() {
  const file = path.join(__dirname, '.env');
  const data = {};
  if (fs.existsSync(file)) {
    fs.readFileSync(file, 'utf8').split(/\r?\n/).forEach(line => {
      line = line.trim();
      if (!line || line.startsWith('#')) return;
      const idx = line.indexOf('=');
      if (idx === -1) return;
      const k = line.slice(0, idx).trim();
      let v = line.slice(idx + 1).trim();
      if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1,-1);
      data[k] = v;
    });
  }
  return data;
}

function httpGet(url, headers) {
  return new Promise((resolve) => {
    const u = new URL(url);
    const opts = { method: 'GET', hostname: u.hostname, path: u.pathname + u.search, headers };
    const req = https.request(opts, res => {
      let stream = res;
      const enc = res.headers['content-encoding'];
      if (enc === 'gzip') stream = res.pipe(zlib.createGunzip());
      else if (enc === 'deflate') stream = res.pipe(zlib.createInflate());
      else if (enc === 'br') stream = res.pipe(zlib.createBrotliDecompress());
      let buf = '';
      stream.setEncoding('utf8');
      stream.on('data', c => buf += c);
      stream.on('end', () => {
        try { resolve({ status: res.statusCode, json: JSON.parse(buf) }); } catch { resolve({ status: res.statusCode, raw: buf }); }
      });
    });
    req.on('error', e => resolve({ error: e }));
    req.end();
  });
}

(async () => {
  const env = loadEnv();
  const tokenRaw = env['bit_sc_token'];
  if (!tokenRaw) {
    console.error('缺少 bit_sc_token');
    process.exit(1);
  }
  const token = tokenRaw.startsWith('Bearer ') ? tokenRaw.slice(7) : tokenRaw;
  const headers = {
    'Authorization': `Bearer ${token}`,
    'User-Agent': 'AuditScript/1.0',
    'Accept-Encoding': 'gzip'
  };

  const listUrl = 'https://qcbldekt.bit.edu.cn/api/course/list/my?page=1&limit=200';
  const listResp = await httpGet(listUrl, headers);
  if (!(listResp.json && listResp.json.code === 200)) {
    console.error('获取课程列表失败', listResp.status, listResp.raw || listResp.json);
    process.exit(1);
  }
  const items = listResp.json.data.items || [];
  console.log(`总课程数: ${items.length}`);

  let topDuration = 0;
  let nullDurationIds = [];
  let typeDurationAvailable = 0;
  let completionTextParsed = 0;
  let restMissingDuration = 0;

  const sampleMissing = [];

  for (const it of items) {
    const id = it.id || it.course_id;
    const d = it.duration;
    if (d != null) topDuration++;
    else nullDurationIds.push(id);

    const typeDuration = it.transcript_index_type && it.transcript_index_type.duration;
    if (typeDuration != null) typeDurationAvailable++;

    const cText = it.completion_flag_text;
    if (cText) {
      const m = String(cText).match(/(\d{1,3})\s*分钟/);
      if (m) completionTextParsed++;
    }

    // 获取 REST 详情看是否有 duration
    const detail = await httpGet(`https://qcbldekt.bit.edu.cn/api/course/info/${id}`, headers);
    let restDuration = null;
    if (detail.json && detail.json.code === 200 && detail.json.data) {
      restDuration = detail.json.data.duration;
    }
    if (restDuration == null) {
      restMissingDuration++;
      if (sampleMissing.length < 5) sampleMissing.push({ id, listDuration: d, typeDuration, cText });
    }
  }

  console.log('\n=== 时长来源统计 ===');
  console.log(`列表顶层有 duration 的课程: ${topDuration}`);
  console.log(`列表顶层缺失 duration 的课程: ${nullDurationIds.length}`);
  console.log(`transcript_index_type.duration 可用数量: ${typeDurationAvailable}`);
  console.log(`completion_flag_text 可解析分钟数的课程: ${completionTextParsed}`);
  console.log(`REST 详情缺失 duration 的课程: ${restMissingDuration}`);
  if (sampleMissing.length) {
    console.log('\n缺失 REST duration 示例(最多5条):');
    sampleMissing.forEach(s => console.log(JSON.stringify(s)));
  }

  // 建议：如果 REST 全部都有，则兜底可删除；否则保留必要的补齐链路。
  if (restMissingDuration === 0) {
    console.log('\n建议: REST 详情全部包含 duration，可删除 myCourseList/type/completion_flag_text 兜底逻辑。');
  } else {
    console.log('\n建议: 存在 REST 缺失 duration，保留 myCourseList 和 completion_flag_text 的兜底。');
  }
})();
