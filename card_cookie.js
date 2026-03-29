/*
 * 脚本名称：北理工校园卡-获取Cookie
 * 作者：Copilot for User
 * 描述：从请求/响应多信源提取 JSESSIONID 与 openid（URL/Cookie/Referer/Location/响应体），并与 Gist 对比后按需更新。
 * 
 * 推荐规则（QuanX）：
 * [rewrite_local]
 * ^https:\/\/dkykt\.info\.bit\.edu\.cn\/.* url script-request-header https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/card_cookie.js
 * ^https:\/\/dkykt\.info\.bit\.edu\.cn\/.* url script-response-header https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/card_cookie.js
 * ^https:\/\/dkykt\.info\.bit\.edu\.cn\/.* url script-response-body https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/card_cookie.js
 * 
 * [mitm]
 * hostname = dkykt.info.bit.edu.cn
 * */

const $ = new Env("北理工校园卡-获取Cookie");

const CONFIG = {
    githubTokenKey: "bit_sc_github_token",
    gistIdKey: "bit_sc_gist_id",
    gistFileNameKey: "bit_card_gist_filename",
    defaultFileName: "bit_card_cookies.json",
    idserialKey: "bit_card_idserial", // 学工号
    headersKey: "bit_card_headers" // 存放各 API 请求头的 BoxJS 键
};

(async () => {
    if (typeof $request !== "undefined" || typeof $response !== "undefined") {
        try {
            await captureCreds();
        } catch (e) {
            console.log(`[${$.name}] 脚本执行异常: ${e}`);
            $.msg($.name, "脚本执行异常", e.toString());
        }
    }
    $done({});
})();

async function captureCreds() {
    const reqHeaders = ($request && $request.headers) ? $request.headers : {};
    const resHeaders = ($response && $response.headers) ? $response.headers : {};
    const url = ($request && $request.url) ? $request.url : "";
    const body = ($response && typeof $response.body === 'string') ? $response.body : "";

    const jsessionid = extractJsessionId(reqHeaders, resHeaders);
    const openid = extractOpenId({ url, reqHeaders, resHeaders, body });
    const idserial = extractIdSerial({ url, body });

    // 采集并归档本次请求的头部，用于后续 API 复用
    const collectedHeaders = collectApiHeaders($request, reqHeaders);

    if (!jsessionid && !openid && !idserial) return; // 没有新线索，直接返回

    // 读取远端 Gist 以便对比/补全
    const gistResult = await getGist();
    const gistData = gistResult && gistResult.ok ? (gistResult.data || null) : null;
    if (gistResult && gistResult.failed) {
        $.msg($.name, "获取 Gist 失败", gistResult.message || "无法获取远端数据，请检查配置或网络");
    }

    const mergedHeaders = mergeHeadersMap(collectedHeaders, (gistData && gistData.headers) || parseBoxHeaders($.getdata(CONFIG.headersKey)));

    const current = {
        jsessionid: jsessionid || (gistData && gistData.jsessionid) || $.getdata("bit_card_jsessionid") || null,
        openid: openid || (gistData && gistData.openid) || $.getdata("bit_card_openid") || null,
        idserial: idserial || (gistData && gistData.idserial) || $.getdata(CONFIG.idserialKey) || null,
        headers: mergedHeaders
    };

    if (!current.jsessionid || !current.openid) {
        // 信息仍不完整，先落本地，等待下一次补全
        if (jsessionid) $.setdata(jsessionid, "bit_card_jsessionid");
        if (openid) $.setdata(openid, "bit_card_openid");
        if (idserial) $.setdata(idserial, CONFIG.idserialKey);
        if (mergedHeaders && Object.keys(mergedHeaders).length) $.setdata(JSON.stringify(mergedHeaders), CONFIG.headersKey);
        console.log(`[${$.name}] 捕获到部分信息，已先写入本地：JSESSIONID=${truncate(jsessionid)} openid=${truncate(openid)} idserial=${truncate(idserial)}`);
        return;
    }

    // 比较是否需要更新远端
    let needUpdate = true;
    if (gistData && gistData.jsessionid === current.jsessionid && gistData.openid === current.openid && gistData.idserial === current.idserial && headersEqual((gistData && gistData.headers) || {}, current.headers || {})) {
        needUpdate = false;
        console.log(`[${$.name}] 凭证与 Gist 一致，跳过更新`);
    } else if (!gistData) {
        console.log(`[${$.name}] 未能获取 Gist 数据或 Gist 为空，将执行强制更新`);
    }

    if (needUpdate) {
        console.log(`[${$.name}] 检测到新/补全的凭证，准备更新 Gist...`);
        console.log(`JSESSIONID: ${current.jsessionid}`);
        console.log(`OpenID: ${current.openid}`);

        const success = await updateGist(current.jsessionid, current.openid, current.idserial, current.headers || {});
        if (success) {
            $.setdata(current.jsessionid, "bit_card_jsessionid");
            $.setdata(current.openid, "bit_card_openid");
            if (current.idserial) $.setdata(current.idserial, CONFIG.idserialKey);
            if (current.headers && Object.keys(current.headers).length) $.setdata(JSON.stringify(current.headers), CONFIG.headersKey);
        } else {
            $.msg($.name, "凭证更新失败", "同步到 Gist 失败，请查看日志");
        }
    }
}

function extractJsessionId(reqHeaders, resHeaders) {
    const cookie = pickHeader(reqHeaders, 'cookie');
    if (cookie) {
        const m = /JSESSIONID=([^;]+)/i.exec(cookie);
        if (m) return m[1];
    }
    const setCookie = normalizeSetCookie(resHeaders);
    if (setCookie) {
        const m = /JSESSIONID=([^;]+)/i.exec(setCookie);
        if (m) return m[1];
    }
    return null;
}

function extractOpenId({ url, reqHeaders, resHeaders, body }) {
    // 1) URL 上的 openid=xxx
    const urlMatch = /[?&#]openid=([^&\s"'>]+)/i.exec(url || "");
    if (urlMatch) return decodeURIComponent(urlMatch[1]);

    // 2) 请求 Cookie 中的 openid
    const cookie = pickHeader(reqHeaders, 'cookie');
    if (cookie) {
        const m = /(?:^|;\s*)openid=([^;]+)/i.exec(cookie);
        if (m) return m[1];
    }

    // 3) Referer 上的 openid
    const referer = pickHeader(reqHeaders, 'referer');
    if (referer) {
        const m = /[?&#]openid=([^&\s"'>]+)/i.exec(referer);
        if (m) return decodeURIComponent(m[1]);
    }

    // 4) 响应 Location 重定向上的 openid
    const location = pickHeader(resHeaders, 'location');
    if (location) {
        const m = /[?&#]openid=([^&\s"'>]+)/i.exec(location);
        if (m) return decodeURIComponent(m[1]);
    }

    // 5) 响应 Set-Cookie 中的 openid
    const setCookie = normalizeSetCookie(resHeaders);
    if (setCookie) {
        const m = /(?:^|;\s*)openid=([^;]+)/i.exec(setCookie);
        if (m) return m[1];
    }

    // 6) 响应体中常见形态："openid":"..." 或 内嵌 URL 参数
    if (body) {
        let m = /"openid"\s*:\s*"([^"]+)"/i.exec(body);
        if (m) return m[1];
        m = /[?&#]openid=([^&\s"'>]+)/i.exec(body);
        if (m) return decodeURIComponent(m[1]);
        // 微信 openid 常以 'o' 开头 28 位，可做兜底（尽量保守）
        m = /\b(o[\w-]{27})\b/.exec(body);
        if (m) return m[1];
    }

    return null;
}

function extractIdSerial({ url, body }) {
    // 1) URL 参数 idserial= 或 idSerial=
    let m = /[?&#]idserial=([^&\s"'>]+)/i.exec(url || "");
    if (m) return decodeURIComponent(m[1]);
    m = /[?&#]idSerial=([^&\s"'>]+)/i.exec(url || "");
    if (m) return decodeURIComponent(m[1]);
    // 2) HTML hidden input 或脚本变量
    if (body) {
        m = /<input[^>]+id=["']idserial["'][^>]*value=["']([^"'>]+)["']/i.exec(body);
        if (m) return m[1];
        m = /name=["']idserial["'][^>]*value=["']([^"'>]+)["']/i.exec(body);
        if (m) return m[1];
        m = /var\s+idserial\s*=\s*['"]([^'";]+)['"]/i.exec(body);
        if (m) return m[1];
        // 3) 常见数字学工号：8-12位数字，和“学工”或“idserial”邻近
        m = /(?:学工号|idserial)[^\d]{0,20}(\d{8,12})/i.exec(body);
        if (m) return m[1];
        // 4) 兜底：找到多个数字后再确认长度，在余额页内经常出现 <p>1234567890</p>
        m = />(\d{8,12})<\/p>/i.exec(body);
        if (m) return m[1];
    }
    return null;
}

function pickHeader(headers, key) {
    if (!headers) return null;
    const lower = Object.create(null);
    for (const k in headers) lower[k.toLowerCase()] = headers[k];
    return lower[key.toLowerCase()] || null;
}

function normalizeSetCookie(headers) {
    const raw = pickHeader(headers, 'set-cookie');
    if (!raw) return null;
    if (Array.isArray(raw)) return raw.join('; ');
    return String(raw);
}

function truncate(v) {
    if (!v) return '';
    if (v.length <= 8) return v;
    return v.slice(0, 4) + '...' + v.slice(-4);
}

async function getGist() {
    const githubToken = $.getdata(CONFIG.githubTokenKey);
    const gistId = $.getdata(CONFIG.gistIdKey);
    const filename = $.getdata(CONFIG.gistFileNameKey) || CONFIG.defaultFileName;

    if (!githubToken || !gistId) return { ok: false, failed: true, message: "配置缺失：未设置 GitHub Token 或 Gist ID" };

    const request = {
        url: `https://api.github.com/gists/${gistId}`,
        method: "GET",
        headers: {
            "Authorization": `token ${githubToken}`,
            "User-Agent": "BIT-Card-Script",
            "Accept": "application/vnd.github.v3+json"
        }
    };

    return new Promise((resolve) => {
        if ($.isQuanX) {
            $task.fetch(request).then(
                response => {
                    if (response.statusCode === 200) {
                        try {
                            const body = JSON.parse(response.body);
                            if (body.files && body.files[filename]) {
                                resolve({ ok: true, data: JSON.parse(body.files[filename].content) });
                            } else {
                                // 文件不存在被视为“空”，不是失败
                                resolve({ ok: true, data: null });
                            }
                        } catch (e) {
                            console.log(`[${$.name}] 解析 Gist 失败: ${e}`);
                            resolve({ ok: false, failed: true, message: `解析 Gist 失败: ${e}` });
                        }
                    } else {
                        console.log(`[${$.name}] 获取 Gist 失败: ${response.statusCode}`);
                        resolve({ ok: false, failed: true, message: `获取 Gist 失败: ${response.statusCode}` });
                    }
                },
                reason => {
                    console.log(`[${$.name}] 获取 Gist 出错: ${reason.error}`);
                    resolve({ ok: false, failed: true, message: `获取 Gist 出错: ${reason.error}` });
                }
            );
        } else {
            resolve({ ok: false, failed: true, message: "当前环境不支持网络请求" });
        }
    });
}

async function updateGist(jsessionid, openid, idserial, headersMap) {
    const githubToken = $.getdata(CONFIG.githubTokenKey);
    const gistId = $.getdata(CONFIG.gistIdKey);
    const filename = $.getdata(CONFIG.gistFileNameKey) || CONFIG.defaultFileName;

    if (!githubToken || !gistId) {
        $.msg($.name, "配置缺失", "请在 BoxJS 中配置 GitHub Token 和 Gist ID");
        return false;
    }

    const content = JSON.stringify({
        jsessionid: jsessionid,
        openid: openid,
        idserial: idserial || null,
        headers: headersMap || {},
        updated_at: new Date().toISOString()
    }, null, 2);

    const request = {
        url: `https://api.github.com/gists/${gistId}`,
        method: "PATCH",
        headers: {
            "Authorization": `token ${githubToken}`,
            "User-Agent": "BIT-Card-Script",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            files: {
                [filename]: { content: content }
            }
        })
    };

    return new Promise((resolve) => {
        if ($.isQuanX) {
            $task.fetch(request).then(
                response => {
                    if (response.statusCode >= 200 && response.statusCode < 300) {
                        resolve(true);
                    } else {
                        console.log(`[${$.name}] Gist 更新失败: ${response.statusCode} ${response.body}`);
                        resolve(false);
                    }
                },
                reason => {
                    console.log(`[${$.name}] Gist 更新出错: ${reason.error}`);
                    resolve(false);
                }
            );
        } else {
            resolve(false);
        }
    });
}

// --- Env Polyfill ---
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { if (this.isQuanX) { if (typeof $notify === 'function') { $notify(e, s, i, r) } else { console.log(`[notify] ${e} | ${s} | ${i}`) } } } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && (typeof $done === 'function') && $done(t) } }(t, e) }

// --- Headers helpers ---
function collectApiHeaders($req, headers) {
    if (!$req || !headers) return {};
    const url = $req.url || "";
    const method = ($req.method || 'GET').toUpperCase();
    try {
        const u = new URL(url);
        const path = u.pathname || '/';
        const key = `${method} ${path}`;
        const sanitized = sanitizeHeaders(headers);
        const out = {};
        out[key] = sanitized;
        return out;
    } catch {
        return {};
    }
}

function sanitizeHeaders(h) {
    const lower = {};
    for (const k in h) lower[k.toLowerCase()] = h[k];
    const omit = new Set(['content-length', 'host', 'connection', 'accept-encoding']);
    const keep = {};
    for (const k in lower) {
        if (omit.has(k)) continue;
        keep[k] = lower[k];
    }
    return keep;
}

function mergeHeadersMap(newMap, baseMap) {
    const result = Object.assign({}, baseMap || {});
    if (newMap) {
        for (const k of Object.keys(newMap)) {
            result[k] = Object.assign({}, result[k] || {}, newMap[k]);
        }
    }
    return result;
}

function headersEqual(a, b) {
    return stableStringify(a) === stableStringify(b);
}

function stableStringify(obj) {
    if (!obj) return '';
    const allKeys = [];
    JSON.stringify(obj, (key, value) => { allKeys.push(key); return value; });
    allKeys.sort();
    return JSON.stringify(obj, allKeys);
}

function parseBoxHeaders(str) {
    if (!str) return {};
    try { return JSON.parse(str); } catch { return {}; }
}
