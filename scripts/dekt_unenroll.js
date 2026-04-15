/*
 * 脚本名称：北理工第二课堂-取消报名
 * 作者：Gemini for User
 * 描述：取消已报名的第二课堂课程。复用 BoxJS 的认证信息。
 *       若未指定取消报名课程ID，则使用最后一次成功报名的课程。
 * 
 * 注意事项：
 * - 仅手动运行（task.enabled=false）
 * - 若后端取消报名路径不同，请调整 CANCEL_PATH
 * 
 * BoxJS 配置项：
 * - bit_sc_unenroll_course_id / dekt_course_id / DEKT_COURSE_ID：取消报名课程ID（可选，留空则使用最后成功报名的课程）
 * - bit_sc_last_signup：最后成功报名的课程对象（自动记录，格式 {id,title,time}）
 * - bit_sc_token / dekt_token：认证Token
 * 
 * [task_local]
 * # 取消报名 (手动运行)
 * 0 0 1 1 * https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/dekt_unenroll.js, tag=第二课堂取消报名, enabled=false
 * 
 * [mitm]
 * hostname = qcbldekt.bit.edu.cn
 */

const HOST = "https://qcbldekt.bit.edu.cn";
const $ = new Env("第二课堂取消报名");
console.log("[unenroll] 脚本启动");
// 调试开关：BoxJS 中设置 `bit_sc_debug=true` 或环境 `DEKT_DEBUG=true` 可开启详细调试日志
const DEBUG = String($.getdata('bit_sc_debug') || $.getdata('DEKT_DEBUG') || 'false').toLowerCase() === 'true';
function debugLog(...args) { if (DEBUG) console.log(...args); }
const KEY_COURSE_IDS = ["bit_sc_unenroll_course_id", "dekt_unenroll_course_id", "dekt_course_id", "DEKT_COURSE_ID"];
const KEY_LAST_SIGNUP = "bit_sc_last_signup"; // 最后成功报名课程 Key (JSON 对象)
const KEY_TOKENS = ["bit_sc_token", "dekt_token", "DEKT_TOKEN"];
const KEY_BLACKLIST = "bit_sc_blacklist"; // 黑名单 Key

// 取消报名接口路径（仅使用抓包确认的 API）
const CANCEL_PATH = "/api/course/cancelApply";

main();

async function main() {
  try {
    // 优先读取用户指定的课程ID（记录使用的 BoxJS 变量名），若为空则使用最后成功报名的课程ID
    const coursePref = getFirstPrefWithKey(KEY_COURSE_IDS);
    let courseId = coursePref.value;
    const coursePrefKey = coursePref.key;
    if (coursePrefKey) console.log(`[unenroll] 使用 BoxJS 变量: ${coursePrefKey}`);
    let courseTitle = "";
    let isUsingLastSignup = false;
    
    if (!courseId) {
      // 尝试读取最后成功报名的课程对象
      const lastStr = $.getdata(KEY_LAST_SIGNUP);
      const parsed = tryParseJSON(lastStr) || {};
      if (parsed && parsed.id) {
        courseId = String(parsed.id);
        courseTitle = parsed.title || "";
        isUsingLastSignup = true;
        console.log(`[unenroll] 未指定课程ID，使用最后成功报名的课程: ID=${courseId}, 标题=${courseTitle}`);
      } else {
        return done("未找到课程ID，请在 BoxJS 中配置「取消报名课程ID」或先完成一次报名");
      }
    }

    const token = getFirstPref(KEY_TOKENS);
    let headers = normalizeHeaders(null, token);

    // user_id 仅从 token 对应的用户信息接口获取，避免手动填写错误。
    const userId = await getUserIdFromApi(headers);
    console.log(`[unenroll] courseId=${courseId}, tokenUserId=${userId || '(none)'}`);
    console.log(`[unenroll] headers.Authorization=${headers.Authorization ? 'Bearer *' : 'none'}`);
    // 严格按照抓包，取消报名必须提供 user_id。
    if (!userId) {
      const err = "无法通过 token 获取 user_id，请确认 token 有效并可访问 /api/user/info";
      const subTitle = courseTitle ? `课程: ${courseTitle} (ID: ${courseId})` : `课程ID: ${courseId}`;
      notify("第二课堂取消报名", subTitle, err);
      console.log(`[unenroll] 终止：${err}`);
      return done(err);
    }
    // 强校验：取消报名必须提供课程 ID（纯数字），禁止模糊匹配或填写课程名称
    if (courseId && !/^\d+$/.test(String(courseId).trim())) {
      const keysHint = KEY_COURSE_IDS.join(" / ");
      const err = `课程 ID 必须为数字，请不要使用课程名称或模糊匹配。请在 BoxJS 填写上述变量之一（例如：${keysHint}）并填入课程 ID`;
      notify("第二课堂取消报名", `课程ID: ${courseId}`, err);
      console.log(`[unenroll] 终止：${err}`);
      return done(err);
    }
    const result = await tryCancel(courseId, userId, headers);
    const subTitle = courseTitle ? `课程: ${courseTitle} (ID: ${courseId})` : `课程ID: ${courseId}`;
    if (result.ok) {
      // 取消报名成功后，自动将课程ID添加到黑名单
      const blacklistMsg = addToBlacklist(courseId);
      const usingLastHint = isUsingLastSignup ? "\n📌 使用最后成功报名的课程" : "";
      notify("第二课堂取消报名", subTitle, `已取消报名（${result.path}）${blacklistMsg}${usingLastHint}`);
      console.log(`[unenroll] 成功: path=${result.path} status=${result.status}`);
      return done();
    } else {
      // 若接口返回 "报名记录不存在"，尝试修复 user_id 或先报名再重试取消
      const parsed = tryParseJSON(result.body) || {};
      const detail = parsed.message || parsed.msg || (typeof result.body === 'string' ? result.body.slice(0, 200) : "");
      const hint = (result.status === 401 || result.code === 401) ? "(Token 失效，请重新获取)" : "";

      if (String(detail).includes('报名记录不存在') || String(detail).includes('未找到报名')) {
        console.log('[unenroll] 检测到报名记录不存在，尝试获取正确的 user_id 后重试取消');

        // 1) 尝试从 /api/user/info 获取 user_id
        try {
          const newUserId = await getUserIdFromApi(headers);
          if (newUserId && newUserId !== String(userId)) {
            console.log(`[unenroll] 从 /api/user/info 获取到 user_id=${newUserId}，将重试取消报名`);
            const retry = await tryCancel(courseId, newUserId, headers);
            if (isSuccess(retry)) {
              const blacklistMsg2 = addToBlacklist(courseId);
              notify('第二课堂取消报名', subTitle, `已取消报名（${CANCEL_PATH}）${blacklistMsg2}`);
              console.log(`[unenroll] 重试成功: status=${retry.status}`);
              return done();
            }
            console.log(`[unenroll] 使用新 user_id 重试仍失败: ${String(retry.body).slice(0,200)}`);
          }
        } catch (e) {
          console.log(`[unenroll] 获取 user_id 失败: ${e}`);
        }

      }

      const msg = `取消失败：HTTP ${result.status || "未知"} ${detail} ${hint} [${result.path || "未知接口"}]`;
      notify("第二课堂取消报名", subTitle, msg);
      console.log(`[unenroll] 失败: ${msg}`);
      return done(msg);
    }
  } catch (e) {
    notify("第二课堂取消报名", "", `异常：${String(e)}`);
    console.log(`[unenroll] 异常: ${String(e)}`);
    return done(String(e));
  }
}

function getFirstPref(keys) {
  for (const k of keys) {
    const v = $.getdata(k);
    console.log(`[pref] key=${k} value=${v ? '(set)' : '(empty)'}`);
    if (v) return v.trim();
  }
  // 兼容额外可能键名
  const extraKeys = ["course_id", "bit_sc_course_id", "DEKT_COURSEID"]; 
  for (const k of extraKeys) {
    const v = $.getdata(k);
    console.log(`[pref] fallback key=${k} value=${v ? '(set)' : '(empty)'}`);
    if (v) return v.trim();
  }
  return "";
}

// 返回第一个存在的偏好值以及所使用的 BoxJS 键名
function getFirstPrefWithKey(keys) {
  for (const k of keys) {
    const v = $.getdata(k);
    console.log(`[pref] key=${k} value=${v ? '(set)' : '(empty)'}`);
    if (v) return { key: k, value: String(v).trim() };
  }
  // 兼容额外可能键名
  const extraKeys = ["course_id", "bit_sc_course_id", "DEKT_COURSEID"];
  for (const k of extraKeys) {
    const v = $.getdata(k);
    console.log(`[pref] fallback key=${k} value=${v ? '(set)' : '(empty)'}`);
    if (v) return { key: k, value: String(v).trim() };
  }
  return { key: "", value: "" };
}

function tryParseJSON(s) {
  if (!s) return null;
  try { return JSON.parse(s); } catch { return null; }
}

function normalizeHeaders(h, token) {
  const headers = {};
  headers["Content-Type"] = "application/json;charset=utf-8";
  headers["Accept"] = "application/json, text/plain, */*";
  // 注入 token（若 headers 中未包含）
  if (token) {
    const normalized = /^Bearer\s+/i.test(String(token).trim()) ? String(token).trim() : `Bearer ${String(token).trim()}`;
    headers["Authorization"] = normalized;
  }
  return headers;
}

async function tryCancel(courseId, userId, headers) {
  const payload = { course_id: toInt(courseId), user_id: toInt(userId) };
  console.log(`[unenroll] POST ${CANCEL_PATH} payload=${JSON.stringify(payload)}`);
  const r = await httpPost(`${HOST}${CANCEL_PATH}`, headers, JSON.stringify(payload));
  if (isSuccess(r)) return { ok: true, path: CANCEL_PATH, ...r };
  return { ok: false, path: CANCEL_PATH, ...r };
}

function isSuccess(resp) {
  if (!resp) return false;
  if (resp.status >= 200 && resp.status < 300 && !resp.err) {
    const data = tryParseJSON(resp.body) || {};
    // 常见成功判定：code==200/0 或 success==true 或 message含“成功”
    if (data.code === 200 || data.code === 0 || data.success === true) return true;
    if (typeof data.message === "string" && data.message.includes("成功")) return true;
  }
  return false;
}

function httpPost(url, headers, body) {
  const sh = sanitizeHeaders(headers);
  debugLog(`[httpPostDebug] POST ${url} headers=${JSON.stringify(sh)} body=${String(body).slice(0,400)}`);
  return new Promise((resolve) => {
    $.post({ url, headers, body }, (err, resp, data) => {
      if (err) {
        debugLog(`[httpPostDebug] ERROR ${url} err=${err}`);
        resolve({ err });
        return;
      }
      const status = resp && (resp.statusCode ?? resp.status);
      debugLog(`[httpPostDebug] RESP ${url} status=${status} body=${String(data).slice(0,800)}`);
      resolve({ status, headers: resp?.headers, body: data });
    });
  });
}

function httpGet(url, headers) {
  const sh = sanitizeHeaders(headers);
  // 移除 Content-Length 以免对 GET 请求造成问题
  const headersForGet = Object.assign({}, headers || {});
  if (headersForGet['Content-Length']) delete headersForGet['Content-Length'];
  if (headersForGet['content-length']) delete headersForGet['content-length'];
  debugLog(`[httpGetDebug] GET ${url} headers=${JSON.stringify(sanitizeHeaders(headersForGet))}`);
  return new Promise((resolve) => {
    $.get({ url, headers: headersForGet }, (err, resp, data) => {
      if (err) { debugLog(`[httpGetDebug] ERROR ${url} err=${err}`); resolve({ err }); return; }
      const status = resp && (resp.statusCode ?? resp.status);
      debugLog(`[httpGetDebug] RESP ${url} status=${status} body=${String(data).slice(0,800)}`);
      resolve({ status, headers: resp?.headers, body: data });
    });
  });
}

async function getUserIdFromApi(headers) {
  try {
    const authOnlyHeaders = buildAuthOnlyHeaders(headers);
    if (!authOnlyHeaders.Authorization && !authOnlyHeaders.authorization) {
      debugLog('[unenroll-debug] /api/user/info 跳过：缺少 Authorization');
      return '';
    }
    const r = await httpGet(`${HOST}/api/user/info`, authOnlyHeaders);
    debugLog('[unenroll-debug] /api/user/info raw response:', typeof r === 'object' ? (r.body ? String(r.body).slice(0,800) : JSON.stringify(r)) : String(r));
    if (r && r.status >= 200 && r.status < 300 && !r.err) {
      const data = tryParseJSON(r.body) || {};
      debugLog('[unenroll-debug] /api/user/info parsed:', data);
      if (data && (data.data && data.data.id)) return String(data.data.id);
      if (data && data.id) return String(data.id);
    }
  } catch (e) {
    console.log(`[unenroll] getUserIdFromApi 异常: ${e}`);
  }
  return '';
}

function buildAuthOnlyHeaders(headers) {
  const h = Object.assign({}, headers || {});
  const auth = h.Authorization || h.authorization || '';
  if (!auth) return {};
  return { Authorization: auth };
}

function sanitizeHeaders(h) {
  try {
    const copy = Object.assign({}, h || {});
    if (copy.Authorization) copy.Authorization = 'Bearer *';
    if (copy.authorization) copy.authorization = 'Bearer *';
    if (copy.Token) copy.Token = '***';
    return copy;
  } catch (e) { return {} }
}

function notify(title, sub, body) {
  $.msg(title, sub, body);
}

function done(reason) {
  $.done({ ret: reason ? false : true, msg: reason || "OK" });
}

function toInt(v) {
  const n = parseInt(String(v), 10);
  return Number.isFinite(n) ? n : undefined;
}

// 将课程ID添加到黑名单
function addToBlacklist(courseId) {
  try {
    const blacklistStr = $.getdata(KEY_BLACKLIST) || "";
    // 解析已有的黑名单（支持逗号分隔或JSON数组格式）
    let blacklist = [];
    const trimmed = blacklistStr.trim();
    if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
      // JSON 数组格式
      try {
        const arr = JSON.parse(trimmed);
        if (Array.isArray(arr)) blacklist = arr.map(x => String(x).trim()).filter(Boolean);
      } catch {
        // JSON 解析失败，回退到逗号分隔格式
        blacklist = trimmed.split(/[,，]/).map(id => id.trim()).filter(id => id);
      }
    } else {
      // 逗号分隔格式
      blacklist = trimmed.split(/[,，]/).map(id => id.trim()).filter(id => id);
    }
    
    const courseIdStr = String(courseId).trim();
    // 检查是否已在黑名单中
    if (blacklist.includes(courseIdStr)) {
      console.log(`[unenroll] 课程 ${courseIdStr} 已在黑名单中，无需重复添加`);
      return "\n📝 已在黑名单中";
    }
    
    // 添加到黑名单
    blacklist.push(courseIdStr);
    $.setdata(blacklist.join(","), KEY_BLACKLIST);
    console.log(`[unenroll] 已将课程 ${courseIdStr} 添加到黑名单`);
    return "\n📝 已自动添加到黑名单";
  } catch (e) {
    console.log(`[unenroll] 添加黑名单失败: ${e}`);
    return "\n⚠️ 添加黑名单失败";
  }
}

// Env Polyfill（与 activities 保持一致，支持 QuanX）
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { if (this.isQuanX) { if (typeof $notify === 'function') { $notify(e, s, i, r) } else { console.log(`[notify] ${e} | ${s} | ${i}`) } } } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } post(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "POST", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && (typeof $done === 'function') && $done(t) } }(t, e) }