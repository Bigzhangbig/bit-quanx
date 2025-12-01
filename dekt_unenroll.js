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

    const userId = deriveUserId(token) || getFirstPref(["bit_sc_user_id", "dekt_user_id", "DEKT_USER_ID"]);
    console.log(`[unenroll] courseId=${courseId}, userId=${userId || ""}`);
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
  // 优先使用抓包中的 JSON 字段：{"course_id":451,"user_id":9028711}
  let last = null;
  for (const path of CANCEL_PATHS) {
    const payload = userId ? { course_id: toInt(courseId), user_id: toInt(userId) } : { course_id: toInt(courseId) };
    const r = await httpPost(`${HOST}${path}`, headers, JSON.stringify(payload));
    const ok = isSuccess(r);
    if (ok) return { ok: true, path, ...r };
    last = { path, ...r };
  }
  // 回退：兼容旧接口字段名与表单编码
  const formHeaders = Object.assign({}, headers, { "Content-Type": "application/x-www-form-urlencoded" });
  for (const path of CANCEL_PATHS) {
    const r = await httpPost(
      `${HOST}${path}`,
      formHeaders,
      `course_id=${encodeURIComponent(courseId)}&user_id=${encodeURIComponent(userId || "")}`
    );
    const ok = isSuccess(r);
    if (ok) return { ok: true, path, ...r };
    last = { path, ...r };
  }
  // 再回退到旧字段名 courseId
  for (const path of CANCEL_PATHS) {
    const r = await httpPost(`${HOST}${path}`, headers, JSON.stringify({ courseId }));
    const ok = isSuccess(r);
    if (ok) return { ok: true, path, ...r };
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
  // 从 Bearer token 形如 "9028711|xxxxx" 中提取 user_id（抓包示例）
  if (!token) return "";
  const part = String(token).split("|")[0];
  return /^(\d+)$/.test(part) ? part : "";
}

function toInt(v) {
  const n = parseInt(String(v), 10);
  return Number.isFinite(n) ? n : undefined;
}

// Env Polyfill（与 activities 保持一致，支持 QuanX）
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { this.isQuanX && $notify(e, s, i, r) } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } post(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "POST", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && $done(t) } }(t, e) }