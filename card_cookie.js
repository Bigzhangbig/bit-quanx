/*
 * 脚本名称：北理工校园卡-获取Cookie
 * 作者：Copilot for User
 * 
 * [rewrite_local]
 * ^https:\/\/dkykt\.info\.bit\.edu\.cn\/selftrade\/.* url script-request-header https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/card_cookie.js
 * 
 * [mitm]
 * hostname = dkykt.info.bit.edu.cn
 * */

const $ = new Env("北理工校园卡-获取Cookie");

const CONFIG = {
    githubTokenKey: "bit_sc_github_token",
    gistIdKey: "bit_sc_gist_id",
    gistFileNameKey: "bit_card_gist_filename",
    defaultFileName: "bit_card_cookies.json"
};

(async () => {
    if (typeof $request !== "undefined") {
        try {
            await getCookie();
        } catch (e) {
            console.log(`[${$.name}] 脚本执行异常: ${e}`);
            $.msg($.name, "脚本执行异常", e.toString());
        }
    }
    $done({});
})();

async function getCookie() {
    if ($request.headers) {
        const cookie = $request.headers['Cookie'] || $request.headers['cookie'];
        const url = $request.url;
        
        let jsessionid = null;
        if (cookie) {
            const match = cookie.match(/JSESSIONID=([^;]+)/);
            if (match) jsessionid = match[1];
        }

        let openid = null;
        if (url.includes("openid=")) {
            const match = url.match(/openid=([^&]+)/);
            if (match) openid = match[1];
        }

        if (jsessionid && openid) {
            // 1. 获取 Gist 上的数据进行对比
            const gistData = await getGist();
            
            let needUpdate = true;
            if (gistData) {
                if (gistData.jsessionid === jsessionid && gistData.openid === openid) {
                    needUpdate = false;
                    console.log(`[${$.name}] 凭证与 Gist 一致，跳过更新`);
                }
            } else {
                console.log(`[${$.name}] 未能获取 Gist 数据或 Gist 为空，将执行强制更新`);
            }

            // 2. 根据对比结果决定是否更新
            if (needUpdate) {
                console.log(`[${$.name}] 检测到新凭证，准备更新 Gist...`);
                console.log(`JSESSIONID: ${jsessionid}`);
                console.log(`OpenID: ${openid}`);
                
                const success = await updateGist(jsessionid, openid);
                if (success) {
                    // 更新本地缓存 (可选)
                    $.setdata(jsessionid, "bit_card_jsessionid");
                    $.setdata(openid, "bit_card_openid");
                    $.msg($.name, "凭证更新成功", "已同步到 GitHub Gist");
                } else {
                    $.msg($.name, "凭证更新失败", "同步到 Gist 失败，请查看日志");
                }
            }
        }
    }
}

async function getGist() {
    const githubToken = $.getdata(CONFIG.githubTokenKey);
    const gistId = $.getdata(CONFIG.gistIdKey);
    const filename = $.getdata(CONFIG.gistFileNameKey) || CONFIG.defaultFileName;

    if (!githubToken || !gistId) return null;

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
                                resolve(JSON.parse(body.files[filename].content));
                            } else {
                                resolve(null);
                            }
                        } catch (e) {
                            console.log(`[${$.name}] 解析 Gist 失败: ${e}`);
                            resolve(null);
                        }
                    } else {
                        console.log(`[${$.name}] 获取 Gist 失败: ${response.statusCode}`);
                        resolve(null);
                    }
                },
                reason => {
                    console.log(`[${$.name}] 获取 Gist 出错: ${reason.error}`);
                    resolve(null);
                }
            );
        } else {
            resolve(null);
        }
    });
}

async function updateGist(jsessionid, openid) {
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
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { this.isQuanX && $notify(e, s, i, r) } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && $done(t) } }(t, e) }
