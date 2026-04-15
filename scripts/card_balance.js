/*
 * 脚本名称：北理工校园卡余额监控
 * 作者：Gemini for User
 * 描述：每日定时查询校园卡余额，低于设定值时发送通知。
 * 
 * [task_local]
 * 0 12 * * * https://raw.githubusercontent.com/Bigzhangbig/bit-dekt-quanx/main/card_balance.js, tag=校园卡余额监控, enabled=true
 * */

const $ = new Env("北理工校园卡余额");

console.log("加载脚本: 北理工校园卡余额监控");

const CONFIG = {
    // BoxJS Keys
    jsessionidKey: "bit_card_jsessionid",
    openidKey: "bit_card_openid",
    minBalanceKey: "bit_card_min_balance",
    debugKey: "bit_card_debug",
    // Gist Keys（用于兜底读取远端凭证）
    githubTokenKey: "bit_sc_github_token",
    gistIdKey: "bit_sc_gist_id",
    gistFileNameKey: "bit_card_gist_filename",
    defaultFileName: "bit_card_cookies.json",
    
    // URL
    balanceUrl: "https://dkykt.info.bit.edu.cn/home/openHomePage"
};

(async () => {
    await checkBalance();
})();

async function checkBalance() {
    let jsessionid = $.getdata(CONFIG.jsessionidKey);
    let openid = $.getdata(CONFIG.openidKey);
    const minBalanceStr = $.getdata(CONFIG.minBalanceKey) || "20"; // 默认20元
    const isDebug = $.getdata(CONFIG.debugKey) === "true";
    
    const minBalance = parseFloat(minBalanceStr);

    // 本地缺失时尝试从 Gist 兜底读取
    if (!jsessionid || !openid) {
        if (isDebug) console.log("[Debug] 本地缺失凭证，尝试从 Gist 获取...");
        try {
            const remote = await getGistCreds();
            if (remote && remote.ok && remote.data) {
                jsessionid = jsessionid || remote.data.jsessionid || null;
                openid = openid || remote.data.openid || null;
                if (jsessionid) $.setdata(jsessionid, CONFIG.jsessionidKey);
                if (openid) $.setdata(openid, CONFIG.openidKey);
                if (isDebug) console.log("[Debug] 已使用 Gist 凭证作为兜底");
            }
        } catch (e) {
            if (isDebug) console.log(`[Debug] 读取 Gist 失败: ${e}`);
        }
    }

    if (!jsessionid || !openid) {
        console.log("❌ 未找到 Cookie (JSESSIONID 或 OpenID)");
        if (isDebug) $.msg("校园卡监控", "配置缺失", "请先获取 Cookie（或检查 Gist 配置）");
        $done();
        return;
    }

    const headers = {
        "Cookie": `JSESSIONID=${jsessionid}; openid=${openid}`,
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.31(0x18001f2a) NetType/WIFI Language/zh_CN",
        "Referer": "https://dkykt.info.bit.edu.cn/home/openHomePage"
    };

    if (isDebug) console.log(`[Debug] 开始查询余额...`);

    try {
        const html = await httpGet(CONFIG.balanceUrl, headers);
        
        // 检查是否登录失效
        if (html.includes("openid无效") || html.includes("页面丢失")) {
            console.log("❌ Cookie 已失效");
            $.msg("校园卡监控", "Cookie失效", "请重新获取 Cookie");
            $done();
            return;
        }

        // 解析余额
        // <span id="hidebalanceid" class="weui-cell__ft" style="color: #F0AD4E;font-size: 20px">813.42元</span>
        const balanceMatch = html.match(/id="hidebalanceid"[^>]*>([\d\.]+)元?<\/span>/);
        
        if (balanceMatch && balanceMatch[1]) {
            const currentBalance = parseFloat(balanceMatch[1]);
            console.log(`✅ 当前余额: ${currentBalance}元`);
            
            if (isDebug) console.log(`[Debug] 设定阈值: ${minBalance}元`);

            if (currentBalance < minBalance) {
                // 余额不足，发送通知并跳转钉钉
                $.msg("校园卡余额不足", `当前余额: ${currentBalance}元`, `低于设定值 ${minBalance}元，请及时充值`, { "open-url": "dingtalk://" });
            } else {
                if (isDebug) $.msg("校园卡余额充足", "", `当前余额: ${currentBalance}元`);
                console.log("余额充足，不发送通知");
            }
        } else {
            console.log("❌ 解析余额失败");
            if (isDebug) console.log(`[Debug] HTML片段: ${html.substring(0, 500)}...`);
        }

    } catch (e) {
        console.log(`❌ 查询失败: ${e}`);
        if (isDebug) $.msg("校园卡监控", "查询异常", e.toString());
    }
    
    $done();
}

function httpGet(url, headers) {
    return new Promise((resolve, reject) => {
        $.get({ url, headers }, (err, resp, data) => {
            if (err) {
                reject(err);
            } else {
                resolve(data);
            }
        });
    });
}

async function getGistCreds() {
    const githubToken = $.getdata(CONFIG.githubTokenKey);
    const gistId = $.getdata(CONFIG.gistIdKey);
    const filename = $.getdata(CONFIG.gistFileNameKey) || CONFIG.defaultFileName;

    if (!gistId) return { ok: false, message: "缺少 Gist ID" };

    const req = {
        url: `https://api.github.com/gists/${gistId}`,
        method: "GET",
        headers: {
            "User-Agent": "BIT-Card-Script",
            "Accept": "application/vnd.github.v3+json",
            ...(githubToken ? { "Authorization": `token ${githubToken}` } : {})
        }
    };

    return new Promise((resolve) => {
        $.get(req, (err, resp, body) => {
            if (err) return resolve({ ok: false, message: String(err) });
            try {
                const json = JSON.parse(body);
                const file = json && json.files && json.files[filename];
                if (!file || !file.content) return resolve({ ok: true, data: null });
                const data = JSON.parse(file.content);
                resolve({ ok: true, data });
            } catch (e) {
                resolve({ ok: false, message: `解析失败: ${e}` });
            }
        });
    });
}

// --- Env Polyfill ---
function Env(t, e) {
    class s {
        constructor(t) {
            this.env = t
        }
    }
    return new class {
        constructor(t) {
            this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1
        }
        getdata(t) {
            let e = this.getval(t);
            if (/^@/.test(t)) {
                const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : "";
                if (r) try {
                    const t = JSON.parse(r);
                    e = t ? this.getval(i, t) : null
                } catch (t) {
                    e = ""
                }
            }
            return e
        }
        setdata(t, e) {
            let s = !1;
            if (/^@/.test(e)) {
                const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}";
                try {
                    const e = JSON.parse(h);
                    this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e))
                } catch (e) {
                    const o = {};
                    this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o))
                }
            } else s = this.setval(t, e);
            return s
        }
        getval(t) {
            return this.isQuanX ? $prefs.valueForKey(t) : ""
        }
        setval(t, e) {
            return this.isQuanX ? $prefs.setValueForKey(t, e) : ""
        }
        msg(e = t, s = "", i = "", r) {
            if (this.isQuanX) {
                if (typeof $notify === 'function') {
                    $notify(e, s, i, r)
                } else {
                    console.log(`[notify] ${e} | ${s} | ${i}`)
                }
            }
        }
        get(t, e = (() => {})) {
            this.isQuanX && ("string" == typeof t && (t = {
                url: t
            }), t.method = "GET", $task.fetch(t).then(t => {
                e(null, t, t.body)
            }, t => e(t.error, null, null)))
        }
        post(t, e = (() => {})) {
            this.isQuanX && ("string" == typeof t && (t = {
                url: t
            }), t.method = "POST", $task.fetch(t).then(t => {
                e(null, t, t.body)
            }, t => e(t.error, null, null)))
        }
        done(t = {}) {
            this.isQuanX && $done(t)
        }
    }(t, e)
}
