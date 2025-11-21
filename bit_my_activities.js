/*
 * 脚本名称：北理工第二课堂-我的活动
 * 描述：查看个人报名列表，若有待签到/签退活动且在时间内，发送通知并复制二维码链接。
 * 配置：请在 Quantumult X 配置文件中添加 task_local
 * [task_local]
 * 0 8-22 * * * bit_my_activities.js, tag=第二课堂我的活动, enabled=true
 */

const $ = new Env("北理工第二课堂-我的活动");
console.log("脚本开始运行");

const CONFIG = {
    tokenKey: "bit_sc_token",
    listUrl: "https://qcbldekt.bit.edu.cn/api/transcript/course/signIn/list?page=1&limit=20&type=1",
    qrBaseUrl: "https://qcbldekt.bit.edu.cn/qrcode/event/?course_id="
};

(async () => {
    try {
        await checkActivities();
    } catch (e) {
        console.log(e);
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

    try {
        const res = await httpGet(CONFIG.listUrl, headers);
        if (res.code === 200 && res.data && res.data.items) {
            processItems(res.data.items);
        } else {
            console.log("获取列表失败或列表为空: " + JSON.stringify(res));
        }
    } catch (error) {
        console.log("请求失败: " + error);
        $.msg($.name, "请求失败", error);
    }
}

function httpGet(url, headers) {
    return new Promise((resolve, reject) => {
        $.get({ url, headers }, (err, resp, data) => {
            if (err) {
                reject(err);
            } else {
                if (resp.status === 401 || resp.statusCode === 401) {
                    resolve({ code: 401, message: "Unauthenticated." });
                    return;
                }
                try {
                    resolve(JSON.parse(data));
                } catch (e) {
                    reject("JSON解析失败");
                }
            }
        });
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
                
                // 如果当前时间在结束时间之前
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
        // 遍历通知所有待处理事项
        for (let i = 0; i < notifyItems.length; i++) {
            const item = notifyItems[i];
            const qrUrl = `${CONFIG.qrBaseUrl}${item.id}`;
            
            // 仅复制第一个（最紧急）的二维码链接到剪贴板
            if (i === 0) {
                if (typeof $pasteboard !== 'undefined') {
                    $pasteboard.copy(qrUrl);
                } else {
                    console.log(`[Clipboard] Would copy: ${qrUrl}`);
                }
            }

            $.msg(
                $.name, 
                `⚠️ ${item.action}提醒: ${item.title}`, 
                `截止时间: ${item.deadline}\n${i===0 ? '已复制二维码链接，' : ''}点击跳转小程序`,
                {"open-url": "weixin://dl/business/?t=34E4TP288tr"}
            );
            
            console.log(`已通知: ${item.title} ${item.action}`);
        }
    } else {
        console.log("没有需要签到/签退的活动");
    }
}

// Env Polyfill
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { this.isQuanX && $notify(e, s, i, r) } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && $done(t) } }(t, e) }
