/*
 * 脚本名称：北理工第二课堂-清理黑名单
 * 作者：Gemini for User
 * 描述：自动移除黑名单中已结束/已取消的课程ID
 * [task_local]
 * 0 3 * * * https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/dekt_clean_blacklist.js, tag=清理黑名单, enabled=true
 */

const $ = new Env("北理工第二课堂-清理黑名单");

const CONFIG = {
    blacklistKey: "bit_sc_blacklist",
    tokenKey: "bit_sc_token",
    headersKey: "bit_sc_headers"
};

(async () => {
    try {
        const token = $.getdata(CONFIG.tokenKey);
        const headers = JSON.parse($.getdata(CONFIG.headersKey) || "{}");
        if (!token || !headers) {
            $.msg($.name, "未获取到Token或Headers", "请先运行cookie脚本获取Token");
            $done();
            return;
        }

        // 读取黑名单
        const blacklistStr = $.getdata(CONFIG.blacklistKey) || "";
        let blacklist = blacklistStr.split(/[,，]/).map(id => id.trim()).filter(id => id);

        if (blacklist.length === 0) {
            $.msg($.name, "黑名单为空", "无需清理");
            $done();
            return;
        }

        // 获取课程列表
        const courseList = await getCourseList(token, headers);
        if (!courseList) {
            $.msg($.name, "获取课程列表失败", "请检查网络或Token");
            $done();
            return;
        }

        // 过滤黑名单
        const validIds = blacklist.filter(id => {
            const course = courseList.find(c => String(c.id) === id);
            // 仅保留未结束且未取消的课程
            return course && course.status !== 3 && course.status !== 4;
        });

        // 写回 BoxJS
        $.setdata(validIds.join(","), CONFIG.blacklistKey);

        $.msg($.name, "黑名单已清理", `剩余ID: ${validIds.join(",") || "无"}`);
    } catch (e) {
        $.msg($.name, "脚本异常", String(e));
    }
    $done();
})();

async function getCourseList(token, headers) {
    const url = "https://qcbldekt.bit.edu.cn/api/course/list";
    const myRequest = {
        url: url,
        method: "GET",
        headers: {
            ...headers,
            "Authorization": token
        }
    };
    return new Promise((resolve) => {
        if ($.isQuanX) {
            $task.fetch(myRequest).then(
                response => {
                    try {
                        const body = JSON.parse(response.body);
                        resolve(body.data || []);
                    } catch (e) {
                        resolve(null);
                    }
                },
                () => resolve(null)
            );
        } else {
            resolve(null);
        }
    });
}

// --- Env Polyfill ---
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { this.isQuanX && $notify(e, s, i, r) } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && $done(t) } }(t, e) }
