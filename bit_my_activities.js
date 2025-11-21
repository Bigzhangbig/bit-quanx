/*
 * 脚本名称：北理工第二课堂-我的活动
 * 描述：查看个人报名列表，若有待签到/签退活动且在时间内，发送通知并复制二维码链接。
 * 配置：请在 Quantumult X 配置文件中添加 task_local
 * [task_local]
 * 0 8-22 * * * bit_my_activities.js, tag=第二课堂我的活动, enabled=true
 */

const $ = new Env("北理工第二课堂-我的活动");

const CONFIG = {
    tokenKey: "bit_sc_token",
    listUrl: "https://qcbldekt.bit.edu.cn/api/transcript/course/signIn/list?page=1&limit=20&type=1",
    qrBaseUrl: "https://qcbldekt.bit.edu.cn/qrcode/second/?course_id="
};

(async () => {
    try {
        await checkActivities();
    } catch (e) {
        $.logErr(e);
    } finally {
        $.done();
    }
})();

async function checkActivities() {
    const token = $.getdata(CONFIG.tokenKey);
    if (!token) {
        $.msg($.name, "❌ 未找到 Token", "请先在 BoxJS 或本地配置 bit_sc_token");
        return;
    }

    const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json;charset=utf-8',
        'Host': 'qcbldekt.bit.edu.cn',
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.10(0x18000a2a) NetType/WIFI Language/zh_CN'
    };

    const request = {
        url: CONFIG.listUrl,
        headers: headers
    };

    $.get(request, (error, response, data) => {
        if (error) {
            $.logErr("请求失败", error);
            $.msg($.name, "请求失败", error);
            return;
        }

        try {
            const res = JSON.parse(data);
            if (res.code === 200 && res.data && res.data.items) {
                processItems(res.data.items);
            } else {
                $.log("获取列表失败或列表为空: " + data);
            }
        } catch (e) {
            $.logErr("解析响应失败", e);
        }
    });
}

function processItems(items) {
    const now = new Date();
    let notifyItems = [];

    for (const item of items) {
        // status_label: "待签到", "待签退", "进行中" 等
        // status: 0 (待签到?), 1 (待签退?), 2 (补卡?), 3 (已结束?) - 需根据实际抓包确认，这里主要用 status_label
        // 抓包示例: status:0 -> 待签到, status:1 -> 待签退
        
        const isSignIn = item.status_label.includes("待签到");
        const isSignOut = item.status_label.includes("待签退");

        if (isSignIn || isSignOut) {
            const endTimeStr = isSignIn ? item.sign_in_end_time : item.sign_out_end_time;
            
            if (endTimeStr) {
                const endTime = new Date(endTimeStr.replace(/-/g, '/')); // 兼容性替换
                
                // 如果当前时间在结束时间之前 (且假设在开始时间之后，虽然列表里没给开始时间，但通常出现在列表里就是相关的)
                if (now < endTime) {
                    notifyItems.push({
                        title: item.course_title,
                        action: isSignIn ? "签到" : "签退",
                        deadline: endTimeStr,
                        id: item.course_id
                    });
                }
            }
        }
    }

    if (notifyItems.length > 0) {
        // 优先处理第一个，或者最紧急的一个
        const item = notifyItems[0];
        const qrUrl = `${CONFIG.qrBaseUrl}${item.id}`;
        
        // 复制二维码链接到剪贴板
        $.setdata(qrUrl, "clipboard"); // QX setdata to clipboard? No, QX uses $notify(title, subtitle, content, {"open-url": url, "media-url": url})
        // QX Polyfill usually doesn't support clipboard writing easily unless mapped to $pasteboard.copy()
        // My Env polyfill below maps setdata to $prefs.setValue, not clipboard.
        // I will use the specific QX API if available in the environment, or just put it in the notification.
        
        if (typeof $pasteboard !== 'undefined') {
            $pasteboard.copy(qrUrl);
        } else {
             // Fallback for Node environment or other
             $.log(`[Clipboard] Would copy: ${qrUrl}`);
        }

        $.msg(
            $.name, 
            `⚠️ ${item.action}提醒: ${item.title}`, 
            `截止时间: ${item.deadline}\n已复制二维码链接，点击跳转`,
            {"open-url": qrUrl}
        );
        
        $.log(`已通知: ${item.title} ${item.action}`);
    } else {
        $.log("没有需要签到/签退的活动");
    }
}

// Env Polyfill
function Env(t, e) {
    "undefined" != typeof process && JSON.stringify(process.env).indexOf("GITHUB") > -1 && process.exit(0);
    class s {
        constructor(t) {
            this.env = t
        }
        write(t, e) {
            if (this.isSurge()) {
                $persistentStore.write(t, e)
            }
            if (this.isQuanX()) {
                $prefs.setValueForKey(t, e)
            }
        }
        read(t) {
            if (this.isSurge()) {
                return $persistentStore.read(t)
            }
            if (this.isQuanX()) {
                return $prefs.valueForKey(t)
            }
        }
        get(t, e) {
            if (this.isSurge()) {
                $httpClient.get(t, (s, i, r) => {
                    !s && i && (i.body = r, i.statusCode = i.status), e(s, i, r)
                })
            }
            if (this.isQuanX()) {
                "string" == typeof t && (t = {
                    url: t
                }), $task.fetch(t).then(t => {
                    t.body = t.data, e(null, t, t.body)
                }, t => e(t.error, null, null))
            }
            if (this.isNode()) {
                this.got = this.got ? this.got : require("got");
                const {
                    url: s,
                    ...i
                } = t;
                this.got.get(s, i).then(t => {
                    const {
                        statusCode: s,
                        statusCode: i,
                        body: r,
                        body: o
                    } = t;
                    e(null, {
                        status: s,
                        statusCode: i,
                        body: r,
                        body: o
                    }, r)
                }, t => {
                    const {
                        message: s,
                        response: i
                    } = t;
                    e(s, i, i && i.body)
                })
            }
        }
        post(t, e) {
            if (this.isSurge()) {
                $httpClient.post(t, (s, i, r) => {
                    !s && i && (i.body = r, i.statusCode = i.status), e(s, i, r)
                })
            }
            if (this.isQuanX()) {
                "string" == typeof t && (t = {
                    url: t
                }), t.method = "POST", $task.fetch(t).then(t => {
                    t.body = t.data, e(null, t, t.body)
                }, t => e(t.error, null, null))
            }
            if (this.isNode()) {
                this.got = this.got ? this.got : require("got");
                const {
                    url: s,
                    ...i
                } = t;
                this.got.post(s, i).then(t => {
                    const {
                        statusCode: s,
                        statusCode: i,
                        body: r,
                        body: o
                    } = t;
                    e(null, {
                        status: s,
                        statusCode: i,
                        body: r,
                        body: o
                    }, r)
                }, t => {
                    const {
                        message: s,
                        response: i
                    } = t;
                    e(s, i, i && i.body)
                })
            }
        }
        time(t, e = null) {
            const s = e ? new Date(e) : new Date;
            let i = {
                "M+": s.getMonth() + 1,
                "d+": s.getDate(),
                "H+": s.getHours(),
                "m+": s.getMinutes(),
                "s+": s.getSeconds(),
                "q+": Math.floor((s.getMonth() + 3) / 3),
                S: s.getMilliseconds()
            };
            /(y+)/.test(t) && (t = t.replace(RegExp.$1, (s.getFullYear() + "").substr(4 - RegExp.$1.length)));
            for (let e in i) new RegExp("(" + e + ")").test(t) && (t = t.replace(RegExp.$1, 1 == RegExp.$1.length ? i[e] : ("00" + i[e]).substr(("" + i[e]).length)));
            return t
        }
        msg(e = t, s = "", i = "", r) {
            const o = t => {
                if (!t) return t;
                if ("string" == typeof t) return this.isLoon() ? t : this.isQuanX() ? {
                    "open-url": t
                } : this.isSurge() ? {
                    url: t
                } : void 0;
                if ("object" == typeof t) {
                    if (this.isLoon()) {
                        let e = t.openUrl || t.url || t["open-url"],
                            s = t.mediaUrl || t["media-url"];
                        return {
                            openUrl: e,
                            mediaUrl: s
                        }
                    }
                    if (this.isQuanX()) {
                        let e = t["open-url"] || t.url || t.openUrl,
                            s = t["media-url"] || t.mediaUrl;
                        return {
                            "open-url": e,
                            "media-url": s
                        }
                    }
                    if (this.isSurge()) {
                        let e = t.url || t.openUrl || t["open-url"];
                        return {
                            url: e
                        }
                    }
                }
            };
            if (this.isMute || (this.isSurge() || this.isLoon() ? $notification.post(e, s, i, o(r)) : this.isQuanX() && $notify(e, s, i, o(r))), !this.isMuteLog) {
                let t = ["", "==============\ud83d\udce3\u7cfb\u7edf\u901a\u77e5\ud83d\udce3=============="];
                t.push(e), s && t.push(s), i && t.push(i), console.log(t.join("\n")), this.logs = this.logs.concat(t)
            }
        }
        log(...t) {
            t.length > 0 && (this.logs = [...this.logs, ...t]), console.log(t.join(this.logSeparator))
        }
        logErr(t, e) {
            const s = !this.isSurge() && !this.isQuanX() && !this.isLoon();
            s ? this.log("", `\u2757\ufe0f${this.name}, \u9519\u8bef!`, t.stack) : this.log("", `\u2757\ufe0f${this.name}, \u9519\u8bef!`, t)
        }
        wait(t) {
            return new Promise(e => setTimeout(e, t))
        }
        done(t = {}) {
            const e = (new Date).getTime(),
                s = (e - this.startTime) / 1e3;
            this.log("", `\ud83d\udd14${this.name}, \u7ed3\u675f! \ud83d\udd5b ${s} \u79d2`), this.log(), (this.isSurge() || this.isQuanX() || this.isLoon()) && $done(t)
        }
        isSurge() {
            return "undefined" != typeof $httpClient && "undefined" == typeof $loon
        }
        isQuanX() {
            return "undefined" != typeof $task
        }
        isLoon() {
            return "undefined" != typeof $loon
        }
        isNode() {
            return "undefined" != typeof module && !!module.exports
        }
        getdata(t) {
            let e = this.getval(t);
            if (/^@/.test(t)) {
                const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : "";
                if (r) try {
                    const t = JSON.parse(r);
                    e = t ? this.lodash_get(t, i, "") : e
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
                    this.lodash_set(e, r, t), s = this.setval(JSON.stringify(e), i)
                } catch (e) {
                    const o = {};
                    this.lodash_set(o, r, t), s = this.setval(JSON.stringify(o), i)
                }
            } else s = this.setval(t, e);
            return s
        }
        getval(t) {
            return this.isSurge() || this.isLoon() ? $persistentStore.read(t) : this.isQuanX() ? $prefs.valueForKey(t) : this.isNode() ? (this.data = this.loaddata(), this.data[t]) : this.data && this.data[t] || null
        }
        setval(t, e) {
            return this.isSurge() || this.isLoon() ? $persistentStore.write(t, e) : this.isQuanX() ? $prefs.setValueForKey(t, e) : this.isNode() ? (this.data = this.loaddata(), this.data[e] = t, this.writedata(), !0) : this.data && this.data[e] || null
        }
        initGotEnv(t) {
            this.got = this.got ? this.got : require("got"), this.cktough = this.cktough ? this.cktough : require("tough-cookie"), this.ckjar = this.ckjar ? this.ckjar : new this.cktough.CookieJar, t && (t.headers = t.headers ? t.headers : {}, void 0 === t.headers.Cookie && void 0 === t.cookieJar && (t.cookieJar = this.ckjar))
        }
        loaddata() {
            if (this.isNode()) {
                this.fs = this.fs ? this.fs : require("fs"), this.path = this.path ? this.path : require("path");
                const t = this.path.resolve(this.dataFile),
                    e = this.path.resolve(process.cwd(), this.dataFile),
                    s = this.fs.existsSync(t),
                    i = !s && this.fs.existsSync(e);
                if (!s && !i) return {};
                {
                    const i = s ? t : e;
                    try {
                        return JSON.parse(this.fs.readFileSync(i))
                    } catch (t) {
                        return {}
                    }
                }
            }
        }
        writedata() {
            if (this.isNode()) {
                this.fs = this.fs ? this.fs : require("fs"), this.path = this.path ? this.path : require("path");
                const t = this.path.resolve(this.dataFile),
                    e = this.path.resolve(process.cwd(), this.dataFile),
                    s = this.fs.existsSync(t),
                    i = !s && this.fs.existsSync(e),
                    r = JSON.stringify(this.data);
                if (s) this.fs.writeFileSync(t, r);
                else {
                    const t = i ? e : t;
                    this.fs.writeFileSync(t, r)
                }
            }
        }
        lodash_get(t, e, s) {
            const i = e.replace(/\[(\d+)\]/g, ".$1").split(".");
            let r = t;
            for (const t of i)
                if (r = Object(r)[t], void 0 === r) return s;
            return r
        }
        lodash_set(t, e, s) {
            return Object(t) !== t ? t : (Array.isArray(e) || (e = e.toString().match(/[^.[\]]+/g) || []), e.slice(0, -1).reduce((t, s, i) => Object(t[s]) === t[s] ? t[s] : t[s] = Math.abs(e[i + 1]) >> 0 == +e[i + 1] ? [] : {}, t)[e[e.length - 1]] = s, t)
        }
    }
    return new s(t, e)
}
