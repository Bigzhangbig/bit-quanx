/*
 * 脚本名称：北理工第二课堂-获取Token
 * 作者：Gemini for User
 * 
 * [rewrite_local]
 * ^https:\/\/qcbldekt\.bit\.edu\.cn\/api\/course\/list url script-request-header https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/bit_cookie.js
 * 
 * [mitm]
 * hostname = qcbldekt.bit.edu.cn
 * */

const $ = new Env("北理工第二课堂-获取Token");

const CONFIG = {
    tokenKey: "bit_sc_token",
    headersKey: "bit_sc_headers",
    debugKey: "bit_sc_debug"
};

(async () => {
    if (typeof $request !== "undefined") {
        await getCookie();
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
            
            if (oldToken !== auth) {
                $.setdata(auth, CONFIG.tokenKey);
                
                // 保存其他头部信息 (User-Agent, Referer等) 以伪装请求
                // 显式添加 Accept-Encoding: gzip, deflate, br 以支持解密
                const headersToSave = JSON.stringify({
                    'User-Agent': $request.headers['User-Agent'] || $request.headers['user-agent'],
                    'Referer': referer,
                    'Host': 'qcbldekt.bit.edu.cn',
                    'Connection': 'keep-alive',
                    'Accept-Encoding': 'gzip, deflate, br'
                });
                $.setdata(headersToSave, CONFIG.headersKey);
                
                $.msg($.name, "获取Token成功", "Token已更新，请去运行监控脚本测试");
                console.log(`[${$.name}] Token 更新成功`);
            } else {
                if (isDebug) console.log(`[${$.name}] Token 未变化，跳过通知`);
            }
        } else {
            if (isDebug) console.log(`[${$.name}] 缺少必要Header，跳过`);
        }
    }
}

// --- Env Polyfill ---
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { this.isQuanX && $notify(e, s, i, r) } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && $done(t) } }(t, e) }
