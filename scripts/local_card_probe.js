/*
 * 脚本名称：本地工具-校园卡凭证探测 (精简稳定版)
 * 功能：通过学工号触发跳转链，遍历所有重定向与最终页面，提取 openid / JSESSIONID / 余额。
 * 用法：.env 中配置：
 *   bit_card_idserial=学工号
 *   (可选) bit_sc_gist_id=GistID
 *   (可选) bit_sc_github_token=GitHubToken(仅gist权限)
 *   (可选) bit_card_gist_filename=bit_card_cookies.json
 *   (可选) bit_card_probe_ua=自定义UA
 * 运行：node local_card_probe.js
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const zlib = require('zlib');

const ENV_PATH = path.join(__dirname, '.env');

function loadEnv() {
  if (!fs.existsSync(ENV_PATH)) return {};
  const out = {};
  fs.readFileSync(ENV_PATH, 'utf8').split(/\r?\n/).forEach(line => {
    line = line.trim();
    if (!line || line.startsWith('#')) return;
    const idx = line.indexOf('=');
    if (idx < 0) return;
    const k = line.slice(0, idx).trim();
    let v = line.slice(idx + 1).trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
    out[k] = v;
  });
  return out;
}

function saveEnv(env) {
  const content = Object.entries(env).map(([k, v]) => `${k}=${v}`).join('\n');
  fs.writeFileSync(ENV_PATH, content);
  console.log('[Env] 已写入 .env');
}

function requestChain(url, headers, maxRedirect = 10) {
  return new Promise((resolve, reject) => {
    const chain = [];
    const visit = (currentUrl, remaining) => {
      let urlObj;
      try { urlObj = new URL(currentUrl); } catch (e) { return reject(e); }
      const opts = {
        method: 'GET',
        hostname: urlObj.hostname,
        port: urlObj.port || 443,
        path: urlObj.pathname + urlObj.search,
        headers
      };
      const req = https.request(opts, res => {
        const status = res.statusCode;
        const resHeaders = res.headers || {};
        let stream = res;
        const enc = resHeaders['content-encoding'];
        if (enc === 'gzip') stream = res.pipe(zlib.createGunzip());
        else if (enc === 'deflate') stream = res.pipe(zlib.createInflate());
        else if (enc === 'br') stream = res.pipe(zlib.createBrotliDecompress());
        let body = '';
        stream.setEncoding('utf8');
        stream.on('data', c => body += c);
        stream.on('end', () => {
          chain.push({ url: currentUrl, status, headers: resHeaders, location: resHeaders.location || resHeaders.Location, body });
          if (status >= 300 && status < 400 && resHeaders.location && remaining > 0) {
            const nextUrl = resHeaders.location.startsWith('http') ? resHeaders.location : `${urlObj.origin}${resHeaders.location}`;
            visit(nextUrl, remaining - 1);
          } else {
            resolve(chain);
          }
        });
      });
      req.on('error', reject);
      req.end();
    };
    visit(url, maxRedirect);
  });
}

function extractOpenId(chain) {
  for (const hop of chain) {
    const loc = hop.location;
    if (loc) {
      const m1 = /[?&#](?:openid|openId|OPENID|dingOpenId)=([^&\s"'>]+)/.exec(loc);
      if (m1) return decodeURIComponent(m1[1]);
    }
    const body = hop.body || '';
    const m2 = /<input[^>]+id=["']openid["'][^>]*value=["']([^"'>]+)["']/i.exec(body);
    if (m2) return m2[1];
    const m3 = /"openid"\s*:\s*"([^"]+)"/i.exec(body);
    if (m3) return m3[1];
    const m4 = /[?&#]openid=([^&\s"'>]+)/i.exec(body);
    if (m4) return decodeURIComponent(m4[1]);
    const m5 = /\b[0-9A-F]{64,128}\b/.exec(body); // 长 Hex 兜底
    if (m5) return m5[1];
  }
  return null;
}

function extractIdSerial(chain) {
  for (const hop of chain) {
    const loc = hop.location;
    if (loc) {
      const m = /[?&#]idserial=([^&\s"'>]+)/i.exec(loc);
      if (m) return decodeURIComponent(m[1]);
    }
    const body = hop.body || '';
    let m = /<input[^>]+id=["']idserial["'][^>]*value=["']([^"'>]+)["']/i.exec(body);
    if (m) return m[1];
    m = /name=["']idserial["'][^>]*value=["']([^"'>]+)["']/i.exec(body);
    if (m) return m[1];
    m = /(?:学工号|idserial)[^\d]{0,20}(\d{8,12})/i.exec(body);
    if (m) return m[1];
    m = />(\d{8,12})<\/p>/i.exec(body);
    if (m) return m[1];
  }
  return null;
}

function extractJsessionFromChain(chain) {
  for (const hop of chain) {
    const setC = hop.headers['set-cookie'] || hop.headers['Set-Cookie'];
    if (setC) {
      const arr = Array.isArray(setC) ? setC.join('; ') : String(setC);
      const m = /JSESSIONID=([^;]+)/i.exec(arr);
      if (m) return m[1];
    }
  }
  return null;
}

function parseBalance(html) {
  if (!html) return null;
  let m = /id="hidebalanceid"[^>]*>([\d.]+)元?<\/span>/i.exec(html);
  if (m) return parseFloat(m[1]);
  m = /showbalanceid[^>]*>(?:余额[:：]￥?|)([\d.]+)元?<\/span>/i.exec(html);
  if (m) return parseFloat(m[1]);
  return null;
}

function buildHeaders(customUA, jsessionid) {
  const h = {
    'User-Agent': customUA || 'Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 Chrome/118.0 DingTalk/7.0.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Connection': 'keep-alive',
    'Referer': 'https://dkykt.info.bit.edu.cn/'
  };
  if (jsessionid) h['Cookie'] = `JSESSIONID=${jsessionid}`;
  return h;
}

async function main() {
  const env = loadEnv();
  let idserial = env.bit_card_idserial;
  let openid = env.bit_card_openid;
  let jsessionid = env.bit_card_jsessionid;
  const gistId = env.bit_sc_gist_id;
  const gistToken = env.bit_sc_github_token;
  const gistFilename = env.bit_card_gist_filename || 'bit_card_cookies.json';
  const customUA = env.bit_card_probe_ua;

  if (!idserial) {
    console.error('❌ 缺少学工号 bit_card_idserial。请先在 .env 填写。');
    process.exit(1);
  }

  console.log('[Probe] 开始跳转链获取');
  const startUrl = `https://dkykt.info.bit.edu.cn/home/openDingTalkHomePage?idserial=${encodeURIComponent(idserial)}`;
  let chain;
  try {
    chain = await requestChain(startUrl, buildHeaders(customUA));
  } catch (e) {
    console.error('❌ 跳转链请求失败：', e.message || e);
    process.exit(1);
  }
  try {
    const dump = chain.map(h => ({ url: h.url, status: h.status, location: h.location || null })).reverse();
    fs.writeFileSync(path.join(__dirname, 'probe_chain.json'), JSON.stringify(dump, null, 2));
    console.log('[Probe] 📝 已写入 probe_chain.json');
  } catch {}

  if (!openid) {
    openid = extractOpenId(chain);
    if (openid) {
      console.log('[Probe] ✅ 提取 openid 成功');
      env.bit_card_openid = openid;
    } else {
      console.warn('[Probe] ❌ 未在链路中找到 openid，写入最后页面供分析');
      fs.writeFileSync(path.join(__dirname, 'probe_final.html'), (chain[chain.length - 1].body || '').slice(0, 60000));
      saveEnv(env);
      process.exit(1);
    }
  }

  if (!jsessionid) {
    jsessionid = extractJsessionFromChain(chain);
    if (jsessionid) {
      console.log('[Probe] ✅ 提取 JSESSIONID 成功');
      env.bit_card_jsessionid = jsessionid;
    } else {
      console.log('[Probe] ℹ️ 跳转链未发现 Set-Cookie JSESSIONID');
    }
  }

  if (!env.bit_card_idserial) {
    const autoId = extractIdSerial(chain);
    if (autoId) {
      idserial = autoId;
      env.bit_card_idserial = idserial;
      console.log('[Probe] ✅ 链路补充学工号');
    }
  }

  console.log('[Probe] 拉取首页解析余额');
  let balanceHtml;
  try {
    const finalReq = await requestChain(`https://dkykt.info.bit.edu.cn/home/openHomePage?openid=${encodeURIComponent(openid)}`, buildHeaders(customUA, jsessionid), 0);
    balanceHtml = finalReq[finalReq.length - 1].body;
  } catch (e) {
    console.error('❌ 首页请求失败：', e.message || e);
  }
  if (balanceHtml) {
    const bal = parseBalance(balanceHtml);
    if (bal != null) {
      console.log(`[Probe] ✅ 当前余额: ${bal} 元`);
      env.bit_card_last_balance = String(bal);
    } else {
      console.warn('[Probe] ⚠️ 未能解析余额，保存片段 last_balance_page.html');
      fs.writeFileSync(path.join(__dirname, 'last_balance_page.html'), balanceHtml.slice(0, 60000));
    }
  }

  if (gistId) {
    console.log('[Probe] 同步 Gist');
    try {
      await updateGist(gistId, gistFilename, gistToken, {
        jsessionid: jsessionid || '',
        openid: openid || '',
        idserial: idserial || '',
        last_balance: env.bit_card_last_balance || null,
        updated_at: new Date().toISOString()
      });
      console.log('[Probe] ✅ Gist 同步完成');
    } catch (e) {
      console.error('❌ Gist 同步失败：', e.message || e);
    }
  } else {
    console.log('[Probe] 跳过 Gist 同步（未配置）');
  }

  saveEnv(env);
  console.log('[Probe] ✅ 探测结束');
}

function updateGist(gistId, filename, token, contentObj) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({ files: { [filename]: { content: JSON.stringify(contentObj, null, 2) } } });
    const options = {
      hostname: 'api.github.com',
      path: `/gists/${gistId}`,
      method: 'PATCH',
      headers: {
        'User-Agent': 'Local-Card-Probe',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
        ...(token ? { 'Authorization': `token ${token}` } : {})
      }
    };
    const req = https.request(options, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) return resolve();
        reject(new Error(`Gist 更新失败: ${res.statusCode} ${res.statusMessage} ${data}`));
      });
    });
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

main().catch(e => {
  console.error('❌ 脚本执行异常：', e.message || e);
  process.exit(1);
});
