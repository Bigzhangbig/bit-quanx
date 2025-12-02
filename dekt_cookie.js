/*
 * 脚本名称：北理工第二课堂-获取Token
 * 作者：Gemini for User
 * 描述：监听第二课堂小程序的网络请求，自动提取并保存 Token 和 Headers。
 * 
 * [rewrite_local]
 * ^https:\/\/qcbldekt\.bit\.edu\.cn\/api\/course\/list url script-request-header https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/dekt_cookie.js
 * 
 * [mitm]
 * hostname = qcbldekt.bit.edu.cn
 * */

const $ = new Env("北理工第二课堂-获取Token");

const CONFIG = {
    tokenKey: "bit_sc_token",
    headersKey: "bit_sc_headers",
    userIdKey: "bit_sc_user_id",
    debugKey: "bit_sc_debug",
    githubTokenKey: "bit_sc_github_token",
    gistIdKey: "bit_sc_gist_id",
    gistFileNameKey: "bit_sc_gist_filename"
};

(async () => {
    if (typeof $request !== "undefined") {
        try {
            await getCookie();
        } catch (e) {
            console.log(`[${$.name}] 脚本执行异常: ${e}`);
        }
    }
    $done({});
})();

async function getCookie() {
    const isDebug = $.getdata(CONFIG.debugKey) === "true";
    
    // 调试日志，可以在 QX 日志中查看是否触发
    if (isDebug) console.log(`[${$.name}] 检测到请求: ${$request.url}`);
    
    if ($request.headers) {
        const auth = $request.headers['Authorization'] || $request.headers['authorization'];
        const referer = $request.headers['Referer'] || $request.headers['referer'];

        // 打印头部信息以便调试
        if (isDebug) console.log(`[Debug] Auth: ${auth ? '存在' : '缺失'}, Referer: ${referer ? '存在' : '缺失'}`);

        // 必须同时存在 Authorization 和 Referer 才认为是有效请求
        if (auth && referer) {
            const oldToken = $.getdata(CONFIG.tokenKey);
            const parsedUserId = deriveUserId(auth);
            
            if (oldToken !== auth) {
                // 检查 Gist 上的 Token
                const gistResult = await getGist();
                const gistToken = gistResult && gistResult.ok && gistResult.data ? gistResult.data.token : null;
                if (gistResult && gistResult.failed) {
                    $.msg($.name, "获取 Gist 失败", gistResult.message || "无法获取远端数据，请检查配置或网络");
                }

                const headersToSave = JSON.stringify({
                    'User-Agent': $request.headers['User-Agent'] || $request.headers['user-agent'],
                    'Referer': referer,
                    'Host': 'qcbldekt.bit.edu.cn',
                    'Connection': 'keep-alive',
                    'Accept-Encoding': 'gzip, deflate, br'
                });

                if (gistToken === auth) {
                    // Token 与 Gist 一致，仅更新本地
                    $.setdata(auth, CONFIG.tokenKey);
                    $.setdata(headersToSave, CONFIG.headersKey);
                    if (parsedUserId) $.setdata(parsedUserId, CONFIG.userIdKey);
                    console.log(`[${$.name}] Token与Gist一致，更新本地缓存，不发送通知`);
                } else {
                    // Token 不一致，更新本地和 Gist
                    $.setdata(auth, CONFIG.tokenKey);
                    $.setdata(headersToSave, CONFIG.headersKey);
                    if (parsedUserId) $.setdata(parsedUserId, CONFIG.userIdKey);
                    
                    // 同步到 Gist
                    const gistOk = await updateGist(auth, headersToSave, parsedUserId);
                    if (!gistOk) {
                        $.msg($.name, "Gist 同步失败", "Token 未能同步到 GitHub Gist，请查看日志");
                    }
                    console.log(`[${$.name}] Token 已更新`);
                }
            } else {
                if (isDebug) console.log(`[${$.name}] Token 未变化，跳过通知`);
            }
        } else {
            if (isDebug) console.log(`[${$.name}] 缺少必要Header，跳过`);
        }
    }
}

async function getGist() {
    const githubToken = $.getdata(CONFIG.githubTokenKey);
    const gistId = $.getdata(CONFIG.gistIdKey);
    const filename = $.getdata(CONFIG.gistFileNameKey) || "bit_cookies.json";

    if (!githubToken || !gistId) {
        return { ok: false, failed: true, message: "配置缺失：未设置 GitHub Token 或 Gist ID" };
    }

    const url = `https://api.github.com/gists/${gistId}`;
    const method = "GET";
    const headers = {
        "Authorization": `token ${githubToken}`,
        "User-Agent": "BIT-DEKT-Script",
        "Accept": "application/vnd.github.v3+json"
    };

    const myRequest = {
        url: url,
        method: method,
        headers: headers
    };

    return new Promise((resolve) => {
        if ($.isQuanX) {
            $task.fetch(myRequest).then(
                response => {
                    if (response.statusCode === 200) {
                        try {
                            const body = JSON.parse(response.body);
                            if (body.files && body.files[filename]) {
                                const content = JSON.parse(body.files[filename].content);
                                resolve({ ok: true, data: content });
                            } else {
                                resolve({ ok: true, data: null });
                            }
                        } catch (e) {
                            console.log(`[${$.name}] 解析Gist失败: ${e}`);
                            resolve({ ok: false, failed: true, message: `解析 Gist 失败: ${e}` });
                        }
                    } else {
                        resolve({ ok: false, failed: true, message: `获取 Gist 失败: ${response.statusCode}` });
                    }
                },
                reason => {
                    console.log(`[${$.name}] 获取Gist失败: ${reason.error}`);
                    resolve({ ok: false, failed: true, message: `获取 Gist 出错: ${reason.error}` });
                }
            );
        } else {
            resolve({ ok: false, failed: true, message: "当前环境不支持网络请求" });
        }
    });
}

async function updateGist(token, headers, userId) {
    const githubToken = $.getdata(CONFIG.githubTokenKey);
    const gistId = $.getdata(CONFIG.gistIdKey);
    const filename = $.getdata(CONFIG.gistFileNameKey) || "bit_cookies.json";

    if (!githubToken || !gistId) {
        console.log(`[${$.name}] 未配置 GitHub Token 或 Gist ID，跳过 Gist 同步`);
        $.msg($.name, "配置缺失", "请在 BoxJS 中配置 GitHub Token 和 Gist ID");
        return false;
    }

    // 读取BoxJS相关配置项
    const boxjsConfig = {
        blacklist: $.getdata("bit_sc_blacklist"),
        signup_list: $.getdata("bit_sc_signup_list"),
        pickup_mode: $.getdata("bit_sc_pickup_mode"),
        filter_college: $.getdata("bit_sc_filter_college"),
        filter_grade: $.getdata("bit_sc_filter_grade"),
        filter_type: $.getdata("bit_sc_filter_type"),
        auto_sign_all: $.getdata("bit_sc_auto_sign_all"),
        runtime_sign_ids: $.getdata("bit_sc_runtime_sign_ids")
    };

    const content = JSON.stringify({
        token: token,
        user_id: userId || null,
        headers: JSON.parse(headers),
        updated_at: new Date().toISOString(),
        boxjs: boxjsConfig
    }, null, 2);

    const url = `https://api.github.com/gists/${gistId}`;
    const method = "PATCH";
    const headers_req = {
        "Authorization": `token ${githubToken}`,
        "User-Agent": "BIT-DEKT-Script",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    };
    const body = JSON.stringify({
        files: {
            [filename]: {
                content: content
            }
        }
    });

    const myRequest = {
        url: url,
        method: method,
        headers: headers_req,
        body: body
    };

    return new Promise((resolve) => {
        if ($.isQuanX) {
            $task.fetch(myRequest).then(
                response => {
                    console.log(`[${$.name}] Gist同步响应: ${response.statusCode}`);
                    if (response.statusCode >= 200 && response.statusCode < 300) {
                        console.log(`[${$.name}] Gist 同步成功`);
                        resolve(true);
                    } else {
                        console.log(`[${$.name}] Gist 同步失败: ${response.body}`);
                        resolve(false);
                    }
                },
                reason => {
                    console.log(`[${$.name}] Gist同步出错: ${reason.error}`);
                    resolve(false);
                }
            );
        } else {
            console.log(`[${$.name}] 非QuanX环境，暂不支持Gist同步`);
            resolve(false);
        }
    });
}

function deriveUserId(authorizationHeader) {
    try {
        if (!authorizationHeader) return "";
        // 支持 "Bearer 611156|xxxx" 或 "611156|xxxx"
        let raw = String(authorizationHeader).trim();
        if (raw.toLowerCase().startsWith("bearer ")) raw = raw.slice(7).trim();
        const first = raw.split("|")[0].trim();
        return /^\d+$/.test(first) ? first : "";
    } catch (_) { return ""; }
}

// --- Env Polyfill ---
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { this.isQuanX && $notify(e, s, i, r) } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && $done(t) } }(t, e) }
