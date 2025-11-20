/*
 * 脚本名称：北理工第二课堂监控
 * 作者：Gemini for User
 * * [task_local]
 * 30 8-22/2 * * * https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/bit_monitor.js, tag=第二课堂监控, enabled=true
 * */

const $ = new Env("北理工第二课堂");

// 配置项
const CONFIG = {
    // BoxJS/Store Keys
    tokenKey: "bit_sc_token",
    headersKey: "bit_sc_headers",
    cacheKey: "bit_sc_cache", // 用来存上一次的最新课程ID
    debugKey: "bit_sc_debug", // 调试模式开关
    filterCollegeKey: "bit_sc_filter_college",
    filterGradeKey: "bit_sc_filter_grade",
    filterTypeKey: "bit_sc_filter_type",
    signupCourseIdKey: "bit_sc_signup_course_id", // 报名课程ID Key
    
    // 栏目ID映射 (根据你的截图推断)
    categories: [
        { id: 1, name: "理想信念" },
        { id: 2, name: "科学素养" },
        { id: 3, name: "社会贡献" },
        { id: 4, name: "团队协作" },
        { id: 5, name: "文化互鉴" },
        { id: 6, name: "健康生活" }
    ],
    statusMap: {
        1: "未开始",
        2: "进行中"
    }
};

// 脚本入口
(async () => {
    await checkCourses();
})();

// 监控逻辑 (运行在 Task 模式)
async function checkCourses() {
    const token = $.getdata(CONFIG.tokenKey);
    const savedHeaders = $.getdata(CONFIG.headersKey);
    const isDebug = $.getdata(CONFIG.debugKey) === "true";
    
    // 获取筛选配置
    const filterCollege = $.getdata(CONFIG.filterCollegeKey) || "不限";
    const filterGrade = $.getdata(CONFIG.filterGradeKey) || "不限";
    const filterType = $.getdata(CONFIG.filterTypeKey) || "不限";

    if (isDebug) {
        console.log(`[Debug] 开始运行监控脚本`);
        console.log(`[Debug] 筛选条件: 学院[${filterCollege}], 年级[${filterGrade}], 类型[${filterType}]`);
    }

    if (!token) {
        $.msg($.name, "❌ 未找到 Token", "请先运行 bit_cookie.js 脚本，并进入微信小程序“第二课堂”刷新任意列表以获取 Token。");
        $done();
        return;
    }

    const headers = JSON.parse(savedHeaders || "{}");
    headers['Authorization'] = token;
    headers['Content-Type'] = 'application/json;charset=utf-8';
    if (!headers['Accept-Encoding']) {
        headers['Accept-Encoding'] = 'gzip, deflate, br';
    }

    // 读取上一次的缓存数据
    let cache = JSON.parse($.getdata(CONFIG.cacheKey) || "{}");
    if (isDebug) {
        console.log(`[Debug] 本地缓存(上次最新ID): ${JSON.stringify(cache)}`);
    }

    let notifyMsg = "";
    let hasUpdate = false;
    let isTokenExpired = false;

    // 遍历所有栏目
    for (let cat of CONFIG.categories) {
        let maxIdInThisLoop = cache[cat.id] || 0;
        
        // 遍历状态：未开始(1), 进行中(2)
        for (let status of [1, 2]) {
            const url = `https://qcbldekt.bit.edu.cn/api/course/list?page=1&limit=5&sign_status=${status}&transcript_index_id=${cat.id}&transcript_index_type_id=0`;
            
            try {
                if (isDebug) console.log(`[Debug] 请求: ${cat.name} (状态${status})`);
                const data = await httpGet(url, headers);
                
                if (isDebug) {
                    // 打印完整的响应数据以便调试
                    console.log(`[Debug] ${cat.name}(${status}) 原始响应: ${JSON.stringify(data)}`);
                }
                
                // 检查 Token 是否失效
                if (data && (data.code === 401 || data.message === "Unauthenticated.")) {
                    isTokenExpired = true;
                    if (isDebug) console.log(`[Debug] Token 失效: ${JSON.stringify(data)}`);
                    break;
                }

                if (data && data.code === 200 && data.data && data.data.items && data.data.items.length > 0) {
                    const courses = data.data.items;
                    if (isDebug) {
                        // 打印新获取到的数据摘要
                        const itemsSummary = courses.map(c => ({id: c.id, title: c.title}));
                        console.log(`[Debug] ${cat.name}(${status}) 解析到 ${courses.length} 条数据: ${JSON.stringify(itemsSummary)}`);
                    }

                    // 遍历返回的课程
                    for (let course of courses) {
                        // 如果课程ID大于缓存的ID，则是新课程
                        if (course.id > (cache[cat.id] || 0)) {
                            
                            // --- 筛选逻辑 ---
                            let isMatch = true;

                            // 1. 学院筛选
                            if (filterCollege !== "不限") {
                                const collegeList = course.college || [];
                                const department = course.department || "";
                                // 检查 college 数组是否包含 OR department 字符串是否包含
                                const matchCollege = collegeList.some(c => c.includes(filterCollege)) || department.includes(filterCollege);
                                if (!matchCollege) isMatch = false;
                            }

                            // 2. 年级筛选 (例如 "2025级" -> 2025)
                            if (isMatch && filterGrade !== "不限") {
                                const targetGrade = parseInt(filterGrade.replace("级", ""));
                                const gradeList = course.grade || [];
                                // 如果 gradeList 为空，通常表示不限年级，视为匹配；如果不为空，则需包含目标年级
                                if (gradeList.length > 0 && !gradeList.includes(targetGrade)) {
                                    isMatch = false;
                                }
                            }

                            // 3. 类型筛选 (例如 "本科生")
                            if (isMatch && filterType !== "不限") {
                                const typeList = course.student_type || [];
                                // 如果 typeList 为空，通常表示不限类型，视为匹配
                                if (typeList.length > 0 && !typeList.includes(filterType)) {
                                    isMatch = false;
                                }
                            }

                            if (isMatch) {
                                hasUpdate = true;
                                const title = course.title || course.transcript_name || "未知名称";
                                const signTime = course.sign_start_time || "未知";
                                const place = course.time_place ? course.time_place.replace(/[\r\n]+/g, " ") : "未知地点";
                                const statusStr = CONFIG.statusMap[status];
                                
                                if (isDebug) console.log(`[Debug] 发现新课程(匹配成功): ${title} (ID: ${course.id})`);

                                // 自动设置报名ID (如果是未开始的课程)
                                if (status === 1) {
                                    $.setdata(course.id.toString(), CONFIG.signupCourseIdKey);
                                    notifyMsg += `【${cat.name} | ${statusStr}】🆕 ${title}\n⏰ 报名时间: ${signTime}\n📍 ${place}\n🎯 已自动设置报名ID: ${course.id}\n\n`;
                                } else {
                                    notifyMsg += `【${cat.name} | ${statusStr}】🆕 ${title}\n⏰ 报名时间: ${signTime}\n📍 ${place}\n\n`;
                                }
                            } else {
                                if (isDebug) console.log(`[Debug] 发现新课程(被筛选过滤): ${course.title} (ID: ${course.id})`);
                            }
                            
                            // 更新当前循环发现的最大ID
                            if (course.id > maxIdInThisLoop) {
                                maxIdInThisLoop = course.id;
                            }
                        }
                    }
                }
            } catch (e) {
                console.log(`❌ 获取 ${cat.name} (状态${status}) 失败: ${e}`);
                if (e.toString().includes("401")) {
                    isTokenExpired = true;
                    break;
                }
            }
            // 稍微延迟
            await new Promise(r => setTimeout(r, 500));
        }
        
        if (isTokenExpired) break;
        
        // 更新该栏目的缓存ID
        cache[cat.id] = maxIdInThisLoop;
    }

    if (isTokenExpired) {
        $.msg($.name, "⚠️ Token 已失效", "请重新进入小程序刷新列表获取新的 Token");
        $done();
        return;
    }

    // 如果有更新，发送通知并保存新缓存
    if (hasUpdate) {
        // 尝试获取跳转链接 (虽然目前测试似乎返回固定链接，但保留逻辑以防万一)
        // 默认跳转链接
        let openUrl = "weixin://dl/business/?t=34E4TP288tr";
        
        $.msg($.name, "发现新课程活动！", notifyMsg, { "open-url": openUrl });
        $.setdata(JSON.stringify(cache), CONFIG.cacheKey);
    } else {
        if (isDebug) console.log(`[Debug] 暂无新课程更新`);
        console.log("暂无新课程更新");
    }
    
    $done();
}

// 封装请求
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

// --- 构建环境 Polyfill (兼容 QX, Loon, Surge) ---
// 此处省略标准 Env 函数库，实际使用时请保留这一行：
// https://github.com/chavyleung/scripts/blob/master/Env.js
// 为了脚本简洁，建议直接引用上面的 Env.js 或者让脚本管理器自动处理
// 这里简单实现 QX 必须的部分：

function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { this.isQuanX && $notify(e, s, i, r) } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && $done(t) } }(t, e) }
