/*
 * 脚本名称：北理工校园卡-获取Cookie
 * 作者：Copilot for User
 * 描述：严格按抓包字段提取 JSESSIONID/openid/idserial（仅请求 Cookie、URL 参数、请求体参数），并按需同步到 Gist。
 * 
 * 推荐规则（QuanX）：
 * [rewrite_local]
 * ^https:\/\/dkykt\.info\.bit\.edu\.cn\/(home\/(openDingtalkLoginNew|openDingTalkHomePage|getUseridBindIdserialNew|queryUserFunciton|queryUserMessage)|myaccount\/querywechatUserLastInfo|selftrade\/(openQueryCardSelfTrade|queryCardSelfTradeList)) url script-request-header https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/card_cookie.js
 * ^https:\/\/dkykt\.info\.bit\.edu\.cn\/(home\/(openDingtalkLoginNew|openDingTalkHomePage|getUseridBindIdserialNew|queryUserFunciton|queryUserMessage)|myaccount\/querywechatUserLastInfo|selftrade\/(openQueryCardSelfTrade|queryCardSelfTradeList)) url script-response-header https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/card_cookie.js
 * ^https:\/\/dkykt\.info\.bit\.edu\.cn\/(home\/(openDingtalkLoginNew|openDingTalkHomePage|getUseridBindIdserialNew|queryUserFunciton|queryUserMessage)|myaccount\/querywechatUserLastInfo|selftrade\/(openQueryCardSelfTrade|queryCardSelfTradeList)) url script-response-body https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/card_cookie.js
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
    headersKey: "bit_card_headers", // 存放各 API 请求头的 BoxJS 键
    pendingPayloadKey: "bit_card_pending_payload",
    lastPushFingerprintKey: "bit_card_last_push_fingerprint",
    lastPushTsKey: "bit_card_last_push_ts",
    syncLockTsKey: "bit_card_sync_lock_ts",
    minPushIntervalSec: 90,
    syncLockTtlSec: 20,
    rewriteCheckGistEachHit: true,
    trackedPathRegex: /^\/(home\/(openDingtalkLoginNew|openDingTalkHomePage)|myaccount\/querywechatUserLastInfo|selftrade\/queryCardSelfTradeList)(\?.*)?$/i
};

(async () => {
    try {
        // 重写阶段：只采集并写本地，不发外网请求，避免影响业务请求时延。
        // 任务阶段（无 $request/$response）：再同步到 Gist。
        if (typeof $request !== "undefined" || typeof $response !== "undefined") {
            await captureCreds();
        } else {
            await syncPendingToGist();
        }
    } catch (e) {
        console.log(`[${$.name}] 脚本执行异常: ${e}`);
        $.msg($.name, "脚本执行异常", e.toString());
    }
    $done({});
})();

async function captureCreds() {
    const reqHeaders = ($request && $request.headers) ? $request.headers : {};
    const url = ($request && $request.url) ? $request.url : "";
    const reqBody = ($request && typeof $request.body === 'string') ? $request.body : "";

    if (!isTrackedRequest(url)) {
        return;
    }

    if (CONFIG.rewriteCheckGistEachHit) {
        refreshFromGistNonBlocking();
    }

    const prevLocalJsession = $.getdata("bit_card_jsessionid") || null;
    const jsessionid = extractJsessionId(reqHeaders);
    const openid = extractOpenId({ url, reqHeaders, reqBody });
    const idserial = extractIdSerial({ url, reqBody });

    // 采集并归档本次请求的头部，用于后续 API 复用
    const collectedHeaders = collectApiHeaders($request, reqHeaders);

    if (!jsessionid && !openid && !idserial) return; // 没有新线索，直接返回

    // 本地优先，避免每次触发都访问 Gist
    const mergedHeaders = mergeHeadersMap(collectedHeaders, parseBoxHeaders($.getdata(CONFIG.headersKey)));

    const current = {
        jsessionid: jsessionid || $.getdata("bit_card_jsessionid") || null,
        openid: openid || $.getdata("bit_card_openid") || null,
        idserial: idserial || $.getdata(CONFIG.idserialKey) || null,
        headers: mergedHeaders
    };

    // 关键凭证本地立即更新，保证“最新 cookie”不依赖 Gist 同步结果。
    if (current.jsessionid) $.setdata(current.jsessionid, "bit_card_jsessionid");
    if (current.openid) $.setdata(current.openid, "bit_card_openid");
    if (current.idserial) $.setdata(current.idserial, CONFIG.idserialKey);
    if (current.headers && Object.keys(current.headers).length) {
        $.setdata(JSON.stringify(current.headers), CONFIG.headersKey);
    }

    // JSESSIONID 发生变化时，视为高优先级：即使在冷却窗口也要排队同步。
    const jsessionRotated = !!(jsessionid && prevLocalJsession && jsessionid !== prevLocalJsession);
    const firstCapturedJsession = !!(jsessionid && !prevLocalJsession);
    const prioritySync = jsessionRotated || firstCapturedJsession;

    if (!current.jsessionid || !current.openid) {
        // 信息仍不完整，先落本地，等待下一次补全
        console.log(`[${$.name}] 捕获到部分信息，已先写入本地：JSESSIONID=${truncate(jsessionid)} openid=${truncate(openid)} idserial=${truncate(idserial)}`);
        return;
    }

    // 仅按 cookie 三项判重：cookie 一致就不上传
    const fp = makeCookieFingerprint(current);
    const lastFp = $.getdata(CONFIG.lastPushFingerprintKey) || "";
    const nowSec = Math.floor(Date.now() / 1000);
    const lastTs = parseInt($.getdata(CONFIG.lastPushTsKey) || "0", 10) || 0;

    let needUpdate = true;
    if (fp === lastFp) {
        needUpdate = false;
        console.log(`[${$.name}] cookie 一致，跳过上传`);
    } else if (!prioritySync && nowSec - lastTs < CONFIG.minPushIntervalSec) {
        needUpdate = false;
        console.log(`[${$.name}] 命中更新冷却(${CONFIG.minPushIntervalSec}s)，暂不访问 Gist`);
    } else if (prioritySync) {
        console.log(`[${$.name}] 关键 cookie 发生变化，强制入队同步`);
    }

    if (needUpdate) {
        // 重写链路只排队，不访问 Gist，避免阻塞网络请求。
        queuePendingPayload(current, fp, nowSec, prioritySync);
        syncPendingToGistNonBlocking();
    }
}

function syncPendingToGistNonBlocking() {
    const nowSec = Math.floor(Date.now() / 1000);
    const lockTs = parseInt($.getdata(CONFIG.syncLockTsKey) || "0", 10) || 0;
    if (nowSec - lockTs < CONFIG.syncLockTtlSec) {
        console.log(`[${$.name}] 同步锁生效，跳过本次上传触发`);
        return;
    }

    $.setdata(String(nowSec), CONFIG.syncLockTsKey);
    syncPendingToGist().catch((e) => {
        console.log(`[${$.name}] 非阻塞同步失败: ${e}`);
    }).finally(() => {
        $.setdata("", CONFIG.syncLockTsKey);
    });
}

function refreshFromGistNonBlocking() {
    getGist().then((gistResult) => {
        if (!gistResult || !gistResult.ok || !gistResult.data) return;
        const remote = gistResult.data;

        const localJ = $.getdata("bit_card_jsessionid") || null;
        const localO = $.getdata("bit_card_openid") || null;
        const localI = $.getdata(CONFIG.idserialKey) || null;

        let changed = false;
        if (remote.jsessionid && remote.jsessionid !== localJ) {
            $.setdata(remote.jsessionid, "bit_card_jsessionid");
            changed = true;
        }
        if (remote.openid && remote.openid !== localO) {
            $.setdata(remote.openid, "bit_card_openid");
            changed = true;
        }
        if (remote.idserial && remote.idserial !== localI) {
            $.setdata(remote.idserial, CONFIG.idserialKey);
            changed = true;
        }
        if (remote.headers && Object.keys(remote.headers).length) {
            const merged = mergeHeadersMap(parseBoxHeaders($.getdata(CONFIG.headersKey)), remote.headers);
            $.setdata(JSON.stringify(merged), CONFIG.headersKey);
            changed = true;
        }

        if (changed) {
            console.log(`[${$.name}] 已从 Gist 回灌最新凭据到本地`);
        }
    }).catch((e) => {
        console.log(`[${$.name}] 非阻塞 Gist 检查失败: ${e}`);
    });
}

async function syncPendingToGist() {
    const raw = $.getdata(CONFIG.pendingPayloadKey);
    if (!raw) {
        console.log(`[${$.name}] 无待同步数据，跳过`);
        return;
    }

    let payload;
    try {
        payload = JSON.parse(raw);
    } catch {
        console.log(`[${$.name}] 待同步数据损坏，已清理`);
        $.setdata("", CONFIG.pendingPayloadKey);
        return;
    }

    if (!payload || !payload.current || !payload.current.jsessionid || !payload.current.openid) {
        console.log(`[${$.name}] 待同步数据不完整，已清理`);
        $.setdata("", CONFIG.pendingPayloadKey);
        return;
    }

    // 先检查远端 Gist 是否已是同一份 cookie；一致则不再重复上传。
    const localCookieFp = makeCookieFingerprint(payload.current);
    const gistCheck = await getGist();
    if (gistCheck && gistCheck.ok && gistCheck.data) {
        const remoteCookieFp = makeCookieFingerprint(gistCheck.data);
        if (remoteCookieFp === localCookieFp) {
            if (payload.fp) $.setdata(payload.fp, CONFIG.lastPushFingerprintKey);
            if (payload.nowSec) $.setdata(String(payload.nowSec), CONFIG.lastPushTsKey);
            $.setdata("", CONFIG.pendingPayloadKey);
            console.log(`[${$.name}] Gist cookie 已一致，跳过上传`);
            return;
        }
        console.log(`[${$.name}] Gist cookie 不一致，执行上传`);
    } else {
        console.log(`[${$.name}] Gist 对比失败，取消上传并结束本次执行`);
        return;
    }

    const result = await updateGist(
        payload.current.jsessionid,
        payload.current.openid,
        payload.current.idserial,
        payload.current.headers || {}
    );

    if (result.ok) {
        $.setdata(payload.current.jsessionid, "bit_card_jsessionid");
        $.setdata(payload.current.openid, "bit_card_openid");
        if (payload.current.idserial) $.setdata(payload.current.idserial, CONFIG.idserialKey);
        if (payload.current.headers && Object.keys(payload.current.headers).length) {
            $.setdata(JSON.stringify(payload.current.headers), CONFIG.headersKey);
        }
        if (payload.fp) $.setdata(payload.fp, CONFIG.lastPushFingerprintKey);
        if (payload.nowSec) $.setdata(String(payload.nowSec), CONFIG.lastPushTsKey);
        $.setdata("", CONFIG.pendingPayloadKey);
        console.log(`[${$.name}] 待同步数据已推送到 Gist: status=${result.statusCode || 'unknown'} jsessionid=${truncate(payload.current.jsessionid)} openid=${truncate(payload.current.openid)} idserial=${truncate(payload.current.idserial)} body=${summarizeResponseBody(result.responseBody)}`);
    } else {
        console.log(`[${$.name}] Gist 上传失败: status=${result.statusCode || 'unknown'} body=${summarizeResponseBody(result.responseBody)} reason=${result.message || 'unknown'}`);
        return;
    }
}

function queuePendingPayload(current, fp, nowSec, prioritySync = false) {
    const packet = {
        current,
        fp,
        nowSec,
        prioritySync,
        queued_at: new Date().toISOString()
    };
    $.setdata(JSON.stringify(packet), CONFIG.pendingPayloadKey);
    console.log(`[${$.name}] 已写入待同步队列: JSESSIONID=${truncate(current.jsessionid)} openid=${truncate(current.openid)}`);
}

function extractJsessionId(reqHeaders) {
    const cookie = pickHeader(reqHeaders, 'cookie');
    if (cookie) {
        const m = /JSESSIONID=([^;]+)/i.exec(cookie);
        if (m) return m[1];
    }
    return null;
}

function extractOpenId({ url, reqHeaders, reqBody }) {
    // 严格按抓包字段：先读请求 URL 参数 openid，再读请求 Cookie openid，最后读请求体 openid。
    let m = /[?&#]openid=([^&\s"'>]+)/i.exec(url || "");
    if (m) return decodeURIComponent(m[1]);

    const cookie = pickHeader(reqHeaders, 'cookie');
    if (cookie) {
        m = /(?:^|;\s*)openid=([^;]+)/i.exec(cookie);
        if (m) return m[1];
    }

    if (reqBody) {
        m = /(?:^|[&\s])openid=([^&\s]+)/i.exec(reqBody);
        if (m) return decodeURIComponent(m[1]);
    }

    return null;
}

function extractIdSerial({ url, reqBody }) {
    // 严格按抓包字段：URL 参数和请求体参数。
    let m = /[?&#]idserial=([^&\s"'>]+)/i.exec(url || "");
    if (m) return decodeURIComponent(m[1]);
    m = /[?&#]idSerial=([^&\s"'>]+)/i.exec(url || "");
    if (m) return decodeURIComponent(m[1]);
    if (reqBody) {
        m = /(?:^|[&\s])idserial=([^&\s]+)/i.exec(reqBody);
        if (m) return decodeURIComponent(m[1]);
        m = /(?:^|[&\s])idSerial=([^&\s]+)/i.exec(reqBody);
        if (m) return decodeURIComponent(m[1]);
    }
    return null;
}

function pickHeader(headers, key) {
    if (!headers) return null;
    const lower = Object.create(null);
    for (const k in headers) lower[k.toLowerCase()] = headers[k];
    return lower[key.toLowerCase()] || null;
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
        return { ok: false, statusCode: 0, responseBody: "", message: "配置缺失" };
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
                        resolve({ ok: true, statusCode: response.statusCode, responseBody: response.body || "", message: "ok" });
                    } else {
                        console.log(`[${$.name}] Gist 更新失败: ${response.statusCode} ${response.body}`);
                        resolve({ ok: false, statusCode: response.statusCode, responseBody: response.body || "", message: "http_error" });
                    }
                },
                reason => {
                    console.log(`[${$.name}] Gist 更新出错: ${reason.error}`);
                    resolve({ ok: false, statusCode: 0, responseBody: "", message: reason.error || "network_error" });
                }
            );
        } else {
            resolve({ ok: false, statusCode: 0, responseBody: "", message: "当前环境不支持网络请求" });
        }
    });
}

function summarizeResponseBody(body, maxLen = 180) {
    if (!body) return "";
    const oneLine = String(body).replace(/\s+/g, " ").trim();
    if (oneLine.length <= maxLen) return oneLine;
    return oneLine.slice(0, maxLen) + "...";
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

    // 仅保留程序实际需要的头（参考当前 Python 程序 dkykt_api.py 的请求头需求）
    const allow = new Set([
        'user-agent',
        'accept',
        'accept-language',
        'content-type',
        'x-requested-with',
        'origin',
        'referer',
        'upgrade-insecure-requests'
    ]);

    const keep = {};
    for (const k in lower) {
        if (!allow.has(k)) continue;
        keep[k] = lower[k];
    }
    return keep;
}

function isTrackedRequest(url) {
    if (!url) return false;
    try {
        const u = new URL(url);
        return CONFIG.trackedPathRegex.test(u.pathname || '/');
    } catch {
        return false;
    }
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

function makeCookieFingerprint(data) {
    return stableStringify({
        jsessionid: data && data.jsessionid ? data.jsessionid : null,
        openid: data && data.openid ? data.openid : null,
        idserial: data && data.idserial ? data.idserial : null
    });
}

function parseBoxHeaders(str) {
    if (!str) return {};
    try { return JSON.parse(str); } catch { return {}; }
}
