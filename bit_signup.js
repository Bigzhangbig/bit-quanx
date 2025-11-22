/*
 * 脚本名称：北理工第二课堂-自动报名
 * 描述：从BoxJS读取待报名列表，自动等待并报名，成功后通知。
 * [task_local]
 * 0 0-23/1 * * * bit_signup.js, tag=第二课堂自动报名, enabled=true
 */

const $ = new Env("北理工第二课堂-自动报名");

console.log("加载脚本: 北理工第二课堂-自动报名");

const CONFIG = {
    // BoxJS Keys
    tokenKey: "bit_sc_token",
    headersKey: "bit_sc_headers",
    signupListKey: "bit_sc_signup_list", // 待报名列表 Key
    notifyNoUpdateKey: "bit_sc_notify_no_update", // 无更新通知开关
    
    // APIs
    applyUrl: "https://qcbldekt.bit.edu.cn/api/course/apply",
    myListUrl: "https://qcbldekt.bit.edu.cn/api/transcript/course/signIn/list?page=1&limit=20&type=1",
    infoUrl: "https://qcbldekt.bit.edu.cn/api/transcript/checkIn/info",
    
    // Constants
    templateId: "2GNFjVv2S7xYnoWeIxGsJGP1Fu2zSs28R6mZI7Fc2kU",
    maxWaitTime: 20 * 60 * 1000, // 20 minutes
    checkInterval: 30 * 1000 // 30 seconds log interval
};

(async () => {
    await main();
})();

async function main() {
    const token = $.getdata(CONFIG.tokenKey);
    const savedHeaders = $.getdata(CONFIG.headersKey);
    const isNotifyNoUpdate = $.getdata(CONFIG.notifyNoUpdateKey) === "true";
    let hasNotified = false;
    
    if (!token) {
        $.msg($.name, "❌ 未找到 Token", "请先运行 bit_cookie.js 获取 Token");
        $.done();
        return;
    }

    const headers = JSON.parse(savedHeaders || "{}");
    headers['Authorization'] = token;
    headers['Content-Type'] = 'application/json;charset=utf-8';
    delete headers['Content-Length'];
    headers['Host'] = 'qcbldekt.bit.edu.cn';

    // 1. 获取待报名列表
    let signupList = [];
    try {
        const listStr = $.getdata(CONFIG.signupListKey) || "[]";
        signupList = JSON.parse(listStr);
    } catch (e) {
        console.log("解析待报名列表失败: " + e);
        signupList = [];
    }

    if (!Array.isArray(signupList) || signupList.length === 0) {
        console.log("待报名列表为空");
        if (isNotifyNoUpdate) {
            $.msg($.name, "🔍 检查完成", "待报名列表为空");
        }
        $.done();
        return;
    }

    console.log(`当前待报名任务数: ${signupList.length}`);

    // 2. 获取已报名列表 (用于去重)
    const myCourses = await getMyCourses(headers);
    const myCourseIds = myCourses.map(c => c.course_id);

    let newList = [];
    let hasChange = false;

    for (let item of signupList) {
        const courseId = item.id;
        const title = item.title || "未知课程";
        const timeStr = item.time; // 格式如 "2025-11-21 10:00:00"

        console.log(`\n处理课程: ${title} (ID: ${courseId})`);

        // 检查是否已报名
        if (myCourseIds.includes(courseId)) {
            console.log(`✅ 已在“我的活动”列表中，跳过并移除`);
            hasChange = true;
            continue;
        }

        // 解析时间
        let targetTime = 0;
        if (timeStr) {
            targetTime = new Date(timeStr.replace(/-/g, '/')).getTime();
        }
        
        const now = Date.now();
        const diff = targetTime - now;

        if (isNaN(targetTime)) {
            console.log(`⚠️ 时间格式错误: ${timeStr}，保留在列表中`);
            newList.push(item);
            continue;
        }

        // 逻辑判断
        if (diff > CONFIG.maxWaitTime) {
            console.log(`⏳ 距离报名开始还有 ${Math.round(diff / 60000)} 分钟，超过20分钟，跳过本次执行`);
            $.msg($.name, "⏳ 等待报名", `课程：${title}\n时间：${timeStr}\n距离开始还有 ${Math.round(diff / 60000)} 分钟，稍后重试。`);
            hasNotified = true;
            newList.push(item);
        } else {
            let result;
            // 策略：在报名开始前0.5秒 ~ 开始后0.5秒期间，并发发送请求
            const burstEndTime = targetTime + 500;
            const burstStartTime = targetTime - 500;
            
            if (Date.now() < burstEndTime) {
                if (Date.now() < burstStartTime) {
                    console.log(`🕒 距离报名开始还有 ${Math.round((targetTime - Date.now()) / 1000)} 秒，等待至 T-0.5s...`);
                    await waitAndLog(burstStartTime);
                }
                console.log("🚀 启动并发报名模式 (T-0.5s ~ T+0.5s)");
                result = await burstSignup(courseId, headers, burstEndTime);
            } else {
                console.log(`⚡ 报名时间已过，立即尝试报名`);
                result = await autoSignup(courseId, headers);
            }
            
            if (result.success) {
                console.log(`✅ 报名成功: ${result.message}`);
                hasChange = true;
                
                // 报名成功后，获取课程详情查看状态
                await new Promise(r => setTimeout(r, 2000));
                const courseInfo = await getCourseInfo(courseId, headers);
                
                let statusMsg = "报名成功";
                let subMsg = "";
                
                if (courseInfo) {
                    const statusLabel = courseInfo.status_label || "";
                    if (statusLabel) statusMsg = `报名成功 | ${statusLabel}`;
                    
                    // 根据 status 显示对应的时间
                    if (courseInfo.status === 0 && courseInfo.sign_in_start_time) {
                        subMsg += `\n⏰ 签到: ${courseInfo.sign_in_start_time} - ${courseInfo.sign_in_end_time}`;
                    } else if (courseInfo.status === 1 && courseInfo.sign_out_start_time) {
                        subMsg += `\n⏰ 签退: ${courseInfo.sign_out_start_time} - ${courseInfo.sign_out_end_time}`;
                    } else {
                        // 如果没有 status 字段，或者 status 不是 0/1
                        // 检查是否有时间字段，如果有，都显示出来 (兼容旧逻辑)
                        // 但如果 statusLabel 是 "已结束"，可能就不需要显示了
                        if (!statusLabel.includes("已结束") && !statusLabel.includes("已完成")) {
                             if (courseInfo.sign_in_start_time && courseInfo.sign_in_end_time) {
                                subMsg += `\n⏰ 签到: ${courseInfo.sign_in_start_time} - ${courseInfo.sign_in_end_time}`;
                            }
                            if (courseInfo.sign_out_start_time && courseInfo.sign_out_end_time) {
                                subMsg += `\n⏰ 签退: ${courseInfo.sign_out_start_time} - ${courseInfo.sign_out_end_time}`;
                            }
                        }
                    }
                }

                $.msg($.name, `✅ ${statusMsg}`, `课程: ${title}\nID: ${courseId}${subMsg}`, { "open-url": "weixin://dl/business/?t=34E4TP288tr" });
                hasNotified = true;

            } else {
                console.log(`❌ 报名失败: ${result.message}`);
                // 失败则保留，下次重试
                newList.push(item);
                $.msg($.name, "❌ 报名失败", `课程: ${title}\nID: ${courseId}\n原因: ${result.message}`);
                hasNotified = true;
            }
        }
    }

    // 更新列表
    if (hasChange) {
        $.setdata(JSON.stringify(newList), CONFIG.signupListKey);
        console.log("已更新待报名列表");
    }
    
    if (!hasNotified && isNotifyNoUpdate) {
        $.msg($.name, "🔍 检查完成", `检查了 ${signupList.length} 个任务，无新报名动作。`);
    }
    
    $.done();
}

async function burstSignup(courseId, headers, endTime) {
    const promises = [];
    let count = 0;
    
    // 循环直到结束时间
    while (Date.now() < endTime) {
        // 发起请求但不等待结果
        promises.push(autoSignup(courseId, headers));
        count++;
        // 简单的频率控制，避免瞬间请求过多导致被封或报错，这里设为50ms
        await new Promise(r => setTimeout(r, 50));
    }
    
    console.log(`⚡ 已发送 ${count} 个并发请求，等待结果...`);
    
    // 等待所有请求完成
    const results = await Promise.all(promises);
    
    // 检查是否有成功的
    const success = results.find(r => r.success);
    if (success) {
        return success;
    }
    
    // 如果都失败，返回最后一个错误
    return results[results.length - 1] || { success: false, message: "并发报名全部失败" };
}

async function waitAndLog(targetTime) {
    while (true) {
        const now = Date.now();
        const remaining = targetTime - now;
        
        if (remaining <= 0) break;

        console.log(`[Running] 等待报名... 剩余 ${Math.round(remaining / 1000)} 秒`);
        
        const waitTime = Math.min(remaining, CONFIG.checkInterval);
        await new Promise(r => setTimeout(r, waitTime));
    }
}

async function getMyCourses(headers) {
    try {
        const res = await httpGet(CONFIG.myListUrl, headers);
        if (res && res.code === 200 && res.data && res.data.items) {
            return res.data.items;
        }
    } catch (e) {
        console.log("获取我的课程失败: " + e);
    }
    return [];
}

async function getCourseInfo(courseId, headers) {
    const url = `${CONFIG.infoUrl}?course_id=${courseId}`;
    try {
        const data = await httpGet(url, headers);
        if (data && data.code === 200) {
            return data.data;
        }
    } catch (e) {
        console.log(`获取课程详情失败: ${e}`);
    }
    return null;
}

async function autoSignup(courseId, headers) {
    const body = {
        course_id: parseInt(courseId),
        template_id: CONFIG.templateId
    };

    const options = {
        url: CONFIG.applyUrl,
        headers: headers,
        body: JSON.stringify(body),
        method: "POST"
    };

    try {
        const result = await httpPost(options);
        if (result.code === 200 || (result.message && result.message.includes("成功"))) {
            return { success: true, message: result.message || "报名成功" };
        } else {
            return { success: false, message: result.message || "未知错误" };
        }
    } catch (e) {
        return { success: false, message: `请求异常: ${e}` };
    }
}

function httpGet(url, headers) {
    return new Promise((resolve, reject) => {
        $.get({ url, headers }, (err, resp, data) => {
            if (err) reject(err);
            else {
                try { resolve(JSON.parse(data)); }
                catch (e) { resolve(data); }
            }
        });
    });
}

function httpPost(options) {
    return new Promise((resolve, reject) => {
        $.post(options, (err, resp, data) => {
            if (err) reject(err);
            else {
                try { resolve(JSON.parse(data)); }
                catch (e) { resolve(data); }
            }
        });
    });
}

// Env Polyfill
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
            this.isQuanX && $notify(e, s, i, r)
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
