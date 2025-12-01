// 第二课堂 取消报名（手动）
// - 复用 BoxJS 的“报名课程ID”与认证信息
// - 仅手动运行（task.enabled=false）
// - 若后端取消报名路径不同，请调整 CANCEL_PATHS

const HOST = "https://qcbldekt.bit.edu.cn";
const $ = new Env("第二课堂取消报名");
console.log("[unenroll] 脚本启动");
const KEY_COURSE_IDS = ["bit_sc_signup_course_id", "dekt_signup_course_id", "dekt_course_id", "DEKT_COURSE_ID"];
const KEY_HEADERS = ["bit_sc_headers", "dekt_headers", "DEKT_HEADERS"];
const KEY_TOKENS = ["bit_sc_token", "dekt_token", "DEKT_TOKEN"];

// 取消报名接口路径（根据 20251201 抓包确认）
const CANCEL_PATHS = [
  "/api/course/cancelApply",
  "/api/course/cancelEnroll",
  "/api/course/cancel",
  "/api/app/course/cancel",
  "/api/course/unEnroll"
];

main();

async function main() {
  try {
    const courseId = getFirstPref(KEY_COURSE_IDS);
    if (!courseId) return done("未找到课程ID，请在 BoxJS 中配置与报名脚本相同的“课程ID”");

    let headers = tryParseJSON(getFirstPref(KEY_HEADERS)) || {};
    const token = getFirstPref(KEY_TOKENS);
    headers = normalizeHeaders(headers, token);

    // 用户ID来源优先级：显式偏好 > 备用键 > 不解析 token 前缀（避免错误）
    const explicitUserId = getFirstPref(["bit_sc_user_id", "dekt_user_id", "DEKT_USER_ID", "DEKT_FORCE_USER_ID", "user_id"]);
    const derivedUserId = deriveUserId(token); // 可能不准确，作为低优先级候选
    let userId = explicitUserId || "";
    console.log(`[unenroll] courseId=${courseId}, explicitUserId=${explicitUserId || '(none)'}, derivedUserId=${derivedUserId || '(none)'}`);
    if (!userId && derivedUserId) {
      userId = derivedUserId; // 仅在没有显式值时使用
    }
    console.log(`[unenroll] final userId candidate=${userId || '(empty will try without user_id first)'}`);
    console.log(`[unenroll] headers.Authorization=${headers.Authorization ? 'Bearer *' : 'none'}`);
    const result = await tryCancel(courseId, userId, headers);
    if (result.ok) {
      notify("第二课堂取消报名", `课程ID: ${courseId}`, `已取消报名（${result.path}）`);
      console.log(`[unenroll] 成功: path=${result.path} status=${result.status}`);
      return done();
    } else {
      const parsed = tryParseJSON(result.body) || {};
      const detail = parsed.message || parsed.msg || (typeof result.body === 'string' ? result.body.slice(0, 200) : "");
      const hint = (result.status === 401 || result.code === 401) ? "(Token 失效，请重新获取)" : "";
      const msg = `取消失败：HTTP ${result.status || "未知"} ${detail} ${hint} [${result.path || "未知接口"}]`;
      notify("第二课堂取消报名", `课程ID: ${courseId}`, msg);
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

function tryParseJSON(s) {
  if (!s) return null;
  try { return JSON.parse(s); } catch { return null; }
}

function normalizeHeaders(h, token) {
  const headers = Object.assign({}, h || {});
  // 标准头
  headers["Accept"] = headers["Accept"] || "application/json, text/plain, */*";
  headers["Content-Type"] = "application/json;charset=UTF-8";
  headers["Origin"] = headers["Origin"] || HOST;
  headers["Referer"] = headers["Referer"] || HOST + "/";
  headers["User-Agent"] = headers["User-Agent"] || "QuantumultX/1.0";
  // 注入 token（若 headers 中未包含）
  if (token) {
    const hasAuth =
      Object.keys(headers).some(k => k.toLowerCase() === "authorization") ||
      Object.keys(headers).some(k => k.toLowerCase() === "token");
    if (!hasAuth) {
      // 常见两种携带方式，优先 Bearer
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return headers;
}

async function tryCancel(courseId, userId, headers) {
  // 1. 优先尝试仅 course_id（避免错误 user_id 导致失败）
  let last = null;
  const candidates = [];
  candidates.push({ course_id: toInt(courseId) });
  // 如果提供 userId，则添加正确格式的 JSON
  if (userId) candidates.push({ course_id: toInt(courseId), user_id: toInt(userId) });
  // 若存在不同 userId 偏好（例如误解析），尝试不带 user_id 再带 derivedUserId 逻辑已处理
  for (const path of CANCEL_PATHS) {
    for (const payload of candidates) {
      console.log(`[unenroll] TRY path=${path} payload=${JSON.stringify(payload)}`);
      const r = await httpPost(`${HOST}${path}`, headers, JSON.stringify(payload));
      if (isSuccess(r)) return { ok: true, path, ...r };
      last = { path, ...r };
    }
  }
  // 2. 表单编码回退（含/不含 user_id）
  const formHeaders = Object.assign({}, headers, { "Content-Type": "application/x-www-form-urlencoded" });
  for (const path of CANCEL_PATHS) {
    for (const payload of candidates) {
      const body = `course_id=${encodeURIComponent(payload.course_id)}${payload.user_id ? `&user_id=${encodeURIComponent(payload.user_id)}` : ''}`;
      console.log(`[unenroll] TRY-FORM path=${path} body=${body}`);
      const r = await httpPost(`${HOST}${path}`, formHeaders, body);
      if (isSuccess(r)) return { ok: true, path, ...r };
      last = { path, ...r };
    }
  }
  // 3. 旧字段名 courseId
  for (const path of CANCEL_PATHS) {
    console.log(`[unenroll] TRY-LEGACY path=${path} body={courseId:${courseId}}`);
    const r = await httpPost(`${HOST}${path}`, headers, JSON.stringify({ courseId }));
    if (isSuccess(r)) return { ok: true, path, ...r };
    last = { path, ...r };
  }
  return { ok: false, ...(last || {}) };
}

function isSuccess(resp) {
  if (!resp) return false;
  if (resp.status >= 200 && resp.status < 300 && !resp.err) {
    const data = tryParseJSON(resp.body) || {};
    // 常见成功判定：code==200/0 或 success==true 或 message含“成功”
    if (data.code === 200 || data.code === 0 || data.success === true) return true;
    if (typeof data.message === "string" && data.message.includes("成功")) return true;
    // 无结构但 2xx 也视为成功
    if (!resp.body || resp.body === "") return true;
  }
  return false;
}

function httpPost(url, headers, body) {
  return new Promise((resolve) => {
    $.post({ url, headers, body }, (err, resp, data) => {
      if (err) {
        resolve({ err });
        return;
      }
      const status = resp && (resp.statusCode ?? resp.status);
      resolve({ status, headers: resp?.headers, body: data });
    });
  });
}

function notify(title, sub, body) {
  $.msg(title, sub, body);
}

function done(reason) {
  $.done({ ret: reason ? false : true, msg: reason || "OK" });
}

function deriveUserId(token) {
  // 原逻辑：从 token 前缀解析；但抓包示例显示 token 前缀可能不是 user_id。
  // 保留此函数，仅作为低优先级候选，不再强制使用。
  if (!token) return "";
  const part = String(token).split("|")[0];
  if (/^(\d+)$/.test(part)) return part;
  return "";
}

function toInt(v) {
  const n = parseInt(String(v), 10);
  return Number.isFinite(n) ? n : undefined;
}

// Env Polyfill（与 activities 保持一致，支持 QuanX）
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { this.isQuanX && $notify(e, s, i, r) } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } post(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "POST", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && $done(t) } }(t, e) }