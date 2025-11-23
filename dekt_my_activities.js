/*
 * 脚本名称：北理工第二课堂-我的活动
 * 作者：Gemini for User
 * 描述：查看个人报名列表，若有待签到/签退活动且在时间内，发送通知并复制二维码链接。
 * 
 * [task_local]
 * 0 8-22 * * * https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/dekt_my_activities.js, tag=第二课堂我的活动, enabled=true
 */

const $ = new Env("北理工第二课堂-我的活动");
console.log("脚本开始运行");

const CONFIG = {
    tokenKey: "bit_sc_token",
    listUrl: "https://qcbldekt.bit.edu.cn/api/transcript/course/signIn/list?page=1&limit=20&type=1",
    infoUrl: "https://qcbldekt.bit.edu.cn/api/transcript/checkIn/info",
    qrBaseUrl: "https://qcbldekt.bit.edu.cn/qrcode/event/?course_id=",
    categories: [
        { id: 1, name: "理想信念" },
        { id: 2, name: "科学素养" },
        { id: 3, name: "社会贡献" },
        { id: 4, name: "团队协作" },
        { id: 5, name: "文化互鉴" },
        { id: 6, name: "健康生活" }
    ]
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
            await processItems(res.data.items, headers);
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

async function getCourseInfo(courseId, headers) {
    const url = `${CONFIG.infoUrl}?course_id=${courseId}`;
    try {
        const data = await httpGet(url, headers);
        if (data && data.code === 200) {
            return data.data;
        }
        return null;
    } catch (e) {
        console.log(`获取课程详情失败: ${e}`);
        return null;
    }
}

async function processItems(items, headers) {
    const now = new Date();
    let notifyItems = [];

    for (const item of items) {
        // status_label: "待签到", "待签退", "进行中" 等
        // status: 0 (待签到), 1 (待签退), 2 (补卡), 3 (已结束) 
        // 抓包示例: status:0 -> 待签到, status:1 -> 待签退
        
        const isSignIn = item.status_label.includes("待签到");
        const isSignOut = item.status_label.includes("待签退");

        if (isSignIn || isSignOut) {
            const endTimeStr = isSignIn ? item.sign_in_end_time : item.sign_out_end_time;
            
            if (endTimeStr) {
                const endTime = new Date(endTimeStr.replace(/-/g, '/')); // 兼容性替换
                
                // 如果当前时间在结束时间之前
                if (now < endTime) {
                    // 获取详细信息以得到准确的开始时间
                    const info = await getCourseInfo(item.course_id, headers);
                    const signInStart = info ? info.sign_in_start_time : item.sign_in_start_time;
                    const signInEnd = info ? info.sign_in_end_time : item.sign_in_end_time;
                    const signOutStart = info ? info.sign_out_start_time : item.sign_out_start_time;
                    const signOutEnd = info ? info.sign_out_end_time : item.sign_out_end_time;
                    
                    // 获取分类名称
                    // 优先使用 transcript_index_id，如果没有则尝试使用 transcript_name 匹配
                    let category = null;
                    const catId = (info && info.transcript_index_id) || item.transcript_index_id;
                    
                    if (catId) {
                        category = CONFIG.categories.find(c => c.id == catId);
                    } else if (info && info.transcript_name) {
                        category = CONFIG.categories.find(c => c.name === info.transcript_name);
                    }
                    
                    const categoryName = category ? category.name : (info && info.transcript_name) || "未知分类";

                    notifyItems.push({
                        title: item.course_title,
                        action: isSignIn ? "签到" : "签退",
                        deadline: endTimeStr,
                        id: item.course_id,
                        signInStart: signInStart,
                        signInEnd: signInEnd,
                        signOutStart: signOutStart,
                        signOutEnd: signOutEnd,
                        category: categoryName,
                        statusLabel: item.status_label
                    });
                }
            }
        }
    }

    if (notifyItems.length > 0) {
        // 按截止时间排序，优先处理最早截止的
        notifyItems.sort((a, b) => new Date(a.deadline.replace(/-/g, '/')) - new Date(b.deadline.replace(/-/g, '/')));

        // 打印所有待参加活动的签到时间段和签退时间段
        console.log("待参加活动列表详情:");
        notifyItems.forEach(item => {
            console.log(`【${item.category} | ${item.statusLabel}】[${item.id}] [${item.action}] ${item.title}`);
            console.log(`  签到时间: ${item.signInStart || '未设置'} - ${item.signInEnd || '未设置'}`);
            console.log(`  签退时间: ${item.signOutStart || '未设置'} - ${item.signOutEnd || '未设置'}`);
        });

        // 1. 处理第一个（最紧急）活动
        const firstItem = notifyItems[0];
        const qrUrl = `${CONFIG.qrBaseUrl}${firstItem.id}`;
        const quickChartUrl = `https://quickchart.io/qr?text=${encodeURIComponent(qrUrl)}`;
        
        let msgBody = `签到: ${firstItem.signInStart || '未设置'} - ${firstItem.signInEnd || '未设置'}`;
        msgBody += `\n签退: ${firstItem.signOutStart || '未设置'} - ${firstItem.signOutEnd || '未设置'}`;

        $.msg(
            $.name, 
            `⚠️ ${firstItem.action}提醒: [${firstItem.id}] ${firstItem.title}`, 
            msgBody,
            {"open-url": quickChartUrl}
        );
        console.log(`已通知: [${firstItem.id}] ${firstItem.title} ${firstItem.action}`);

        // 2. 其余活动简写为一条通知
        if (notifyItems.length > 1) {
            const restItems = notifyItems.slice(1);
            const summary = restItems.map(item => `[${item.id}] [${item.action}] ${item.title}`).join('\n');
            
            $.msg(
                $.name,
                `还有 ${restItems.length} 个活动待处理`,
                summary + "\n点击跳转小程序",
                {"open-url": "weixin://dl/business/?t=34E4TP288tr"}
            );
            console.log(`已通知其余 ${restItems.length} 个活动`);
        }
    } else {
        console.log("没有需要签到/签退的活动");
    }
}

// Env Polyfill
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { this.isQuanX && $notify(e, s, i, r) } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && $done(t) } }(t, e) }
