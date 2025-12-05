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
 * - bit_sc_last_signup_id / bit_sc_last_signup_title：最后成功报名的课程ID和标题（自动记录）
 * - bit_sc_user_id / dekt_user_id / DEKT_USER_ID：用户ID
 * - bit_sc_token / dekt_token：认证Token
 * - bit_sc_headers / dekt_headers：请求Headers（可选）
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
const KEY_COURSE_IDS = ["bit_sc_unenroll_course_id", "dekt_unenroll_course_id", "dekt_course_id", "DEKT_COURSE_ID"];
const KEY_LAST_SIGNUP_ID = "bit_sc_last_signup_id"; // 最后成功报名课程ID Key
const KEY_LAST_SIGNUP_TITLE = "bit_sc_last_signup_title"; // 最后成功报名课程标题 Key
const KEY_HEADERS = ["bit_sc_headers", "dekt_headers", "DEKT_HEADERS"];
const KEY_TOKENS = ["bit_sc_token", "dekt_token", "DEKT_TOKEN"];
const KEY_BLACKLIST = "bit_sc_blacklist"; // 黑名单 Key

// 取消报名接口路径（仅使用抓包确认的 API）
const CANCEL_PATH = "/api/course/cancelApply";

main();

async function main() {
  try {
    // 优先读取用户指定的课程ID，若为空则使用最后成功报名的课程ID
    let courseId = getFirstPref(KEY_COURSE_IDS);
    let courseTitle = "";
    let isUsingLastSignup = false;
    
    if (!courseId) {
      // 尝试读取最后成功报名的课程ID
      const lastSignupId = $.getdata(KEY_LAST_SIGNUP_ID);
      const lastSignupTitle = $.getdata(KEY_LAST_SIGNUP_TITLE);
      if (lastSignupId) {
        courseId = lastSignupId;
        courseTitle = lastSignupTitle || "";
        isUsingLastSignup = true;
        console.log(`[unenroll] 未指定课程ID，使用最后成功报名的课程: ID=${courseId}, 标题=${courseTitle}`);
      } else {
        return done("未找到课程ID，请在 BoxJS 中配置「取消报名课程ID」或先完成一次报名");
      }
    }

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
    // 严格按照抓包，要求提供 user_id
    if (!userId) {
      const err = "缺少 user_id，请在 BoxJS 设置 dekt_user_id/bit_sc_user_id（或 DEKT_FORCE_USER_ID）";
      const subTitle = courseTitle ? `课程: ${courseTitle} (ID: ${courseId})` : `课程ID: ${courseId}`;
      notify("第二课堂取消报名", subTitle, err);
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
      const parsed = tryParseJSON(result.body) || {};
      const detail = parsed.message || parsed.msg || (typeof result.body === 'string' ? result.body.slice(0, 200) : "");
      const hint = (result.status === 401 || result.code === 401) ? "(Token 失效，请重新获取)" : "";
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

function tryParseJSON(s) {
  if (!s) return null;
  try { return JSON.parse(s); } catch { return null; }
}

function normalizeHeaders(h, token) {
  const headers = Object.assign({}, h || {});
  // 标准头
  headers["Accept"] = headers["Accept"] || "application/json, text/plain, */*";
  headers["Content-Type"] = "application/json;charset=utf-8";
  headers["Origin"] = headers["Origin"] || HOST;
  headers["Referer"] = headers["Referer"] || "https://servicewechat.com/wx89b19258915c9585/25/page-frame.html";
  headers["User-Agent"] = headers["User-Agent"] || "Mozilla/5.0 (iPad; CPU OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.65(0x18004130) NetType/WIFI Language/zh_CN";
  headers["Host"] = headers["Host"] || "qcbldekt.bit.edu.cn";
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
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { this.isQuanX && $notify(e, s, i, r) } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } post(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "POST", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && $done(t) } }(t, e) }