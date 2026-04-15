/*
 * 脚本名称：本地工具-校园卡Gist校验
 * 描述：读取 .env 中的 Gist 配置并拉取 openid/JSESSIONID 进行展示。
 * 用法：pwsh 中执行：node .\local_card_gist_check.js
 */
const fs = require('fs');
const path = require('path');
const https = require('https');

const envFilePath = path.join(__dirname, '.env');

function loadEnv() {
  if (!fs.existsSync(envFilePath)) return {};
  const content = fs.readFileSync(envFilePath, 'utf8');
  const result = {};
  content.split('\n').forEach(line => {
    line = line.trim();
    if (!line || line.startsWith('#')) return;
    const idx = line.indexOf('=');
    if (idx < 0) return;
    const key = line.slice(0, idx).trim();
    let val = line.slice(idx + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith('\'') && val.endsWith('\''))) {
      val = val.slice(1, -1);
    }
    result[key] = val;
  });
  return result;
}

function fetchGist(gistId, filename, token) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.github.com',
      path: `/gists/${gistId}`,
      method: 'GET',
      headers: {
        'User-Agent': 'Local-Card-Gist-Check',
        'Accept': 'application/vnd.github.v3+json',
        ...(token ? { 'Authorization': `token ${token}` } : {})
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          return reject(new Error(`Gist fetch failed: ${res.statusCode} ${res.statusMessage}`));
        }
        try {
          const json = JSON.parse(data);
          const file = json && json.files && json.files[filename];
          if (!file || !file.content) return resolve(null);
          const content = JSON.parse(file.content);
          resolve(content);
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.end();
  });
}

(async () => {
  const env = loadEnv();
  const token = env.bit_sc_github_token || '';
  const gistId = env.bit_sc_gist_id;
  const filename = env.bit_card_gist_filename || 'bit_card_cookies.json';

  if (!gistId) {
    console.error('❌ 缺少 Gist 配置：bit_sc_gist_id');
    console.log('请在 .env 中配置 bit_sc_gist_id（可选：bit_sc_github_token, bit_card_gist_filename）');
    process.exit(1);
  }

  try {
    console.log(`[Gist] 读取 ${gistId}/${filename} ...`);
    const content = await fetchGist(gistId, filename, token);
    if (!content) {
      console.log('ℹ️ 未找到该文件或文件为空');
      process.exit(0);
    }
    const jsid = content.jsessionid || '';
    const oid = content.openid || '';
    const time = content.updated_at || '';

    const trunc = (v) => !v ? '' : (v.length <= 10 ? v : `${v.slice(0,4)}...${v.slice(-4)}`);

    console.log('✅ Gist 内容读取成功：');
    console.log(`- JSESSIONID: ${trunc(jsid)}`);
    console.log(`- openid    : ${trunc(oid)}`);
    console.log(`- updated_at: ${time}`);

    if (!jsid || !oid) {
      console.log('⚠️ 提示：当前 Gist 信息不完整（可能尚未抓到全部字段）。建议再走一次校园卡入口。');
    }
  } catch (e) {
    console.error('❌ 读取失败：', e.message || e);
    process.exit(1);
  }
})();
