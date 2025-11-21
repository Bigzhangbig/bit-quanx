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
    pickupKey: "bit_sc_pickup_mode", // 捡漏模式开关
    delayKey: "bit_sc_random_delay", // 随机延迟 Key
    signupListKey: "bit_sc_signup_list", // 待报名列表 Key
    filterCollegeKey: "bit_sc_filter_college",
    filterGradeKey: "bit_sc_filter_grade",
    filterTypeKey: "bit_sc_filter_type",
    signupCourseIdKey: "bit_sc_signup_course_id", // 报名课程ID Key
    
    // 栏目ID映射
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
        2: "进行中",
        3: "已结束"
    },
    // 报名接口
    applyUrl: "https://qcbldekt.bit.edu.cn/api/course/apply",
    // 固定的 Template ID
    templateId: "2GNFjVv2S7xYnoWeIxGsJGP1Fu2zSs28R6mZI7Fc2kU"
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
    const isPickupMode = $.getdata(CONFIG.pickupKey) === "true";
    const randomDelay = parseInt($.getdata(CONFIG.delayKey) || "0");
    
    // 获取筛选配置
    const filterCollege = $.getdata(CONFIG.filterCollegeKey) || "不限";
    const filterGrade = $.getdata(CONFIG.filterGradeKey) || "不限";
    const filterType = $.getdata(CONFIG.filterTypeKey) || "不限";

    if (!token) {
        $.msg("❌ 未找到 Token", "", "请先运行 bit_cookie.js 脚本，并进入微信小程序“第二课堂”刷新任意列表以获取 Token。");
        $done();
        return;
    }

    const headers = JSON.parse(savedHeaders || "{}");
    headers['Authorization'] = token;
    headers['Content-Type'] = 'application/json;charset=utf-8';
    if (!headers['Accept-Encoding']) {
        headers['Accept-Encoding'] = 'gzip, deflate, br';
    }

    // --- 新增：检查待报名列表 (仅 Debug 模式) ---
    if (isDebug) {
        await checkSignupList(token, headers);
    }

    // 优先处理指定报名ID
    const envSignupId = $.getdata(CONFIG.signupCourseIdKey);
    let currentMaxSignupId = envSignupId ? parseInt(envSignupId) : 0;
    if (isNaN(currentMaxSignupId)) currentMaxSignupId = 0;

    if (envSignupId) {
        if (isDebug) console.log(`[Debug] 检测到指定报名ID: ${envSignupId}，尝试报名...`);
        const envRes = await autoSignup(envSignupId, token, headers);
        if (envRes.success) $.msg("✅ 指定课程报名成功", "", `ID: ${envSignupId}\n${envRes.message}`);
        else if (isDebug) console.log(`[Debug] 指定课程 ${envSignupId} 报名结果: ${envRes.message}`);
    }

    if (isDebug) {
        console.log(`[Debug] 开始运行监控脚本`);
        console.log(`[Debug] 筛选条件: 学院[${filterCollege}], 年级[${filterGrade}], 类型[${filterType}]`);
    }

    // 读取上一次的缓存数据
    let cache = JSON.parse($.getdata(CONFIG.cacheKey) || "{}");
    if (isDebug) {
        console.log(`[Debug] 本地缓存(上次最新ID): ${JSON.stringify(cache)}`);
    }

    let notifyMsg = "";
    let hasUpdate = false;
    let isTokenExpired = false;
    
    // 统计数据
    let totalFetchedCount = 0;
    let unstartedCount = 0;

    // 遍历所有栏目
    for (let cat of CONFIG.categories) {
        let maxIdInThisLoop = cache[cat.id] || 0;
        
        // 遍历状态：未开始(1), 进行中(2)
        for (let status of [1, 2]) {
            const url = `https://qcbldekt.bit.edu.cn/api/course/list?page=1&limit=5&sign_status=${status}&transcript_index_id=${cat.id}&transcript_index_type_id=0`;
            
            try {
                if (randomDelay > 0) {
                    const delayMs = Math.floor(Math.random() * randomDelay * 1000);
                    if (isDebug) console.log(`[Debug] 随机延迟: ${delayMs}ms`);
                    await new Promise(r => setTimeout(r, delayMs));
                }

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
                    totalFetchedCount += courses.length;
                    
                    if (isDebug) {
                        // 打印新获取到的数据摘要
                        const itemsSummary = courses.map(c => ({id: c.id, title: c.title}));
                        console.log(`[Debug] ${cat.name}(${status}) 解析到 ${courses.length} 条数据: ${JSON.stringify(itemsSummary)}`);
                    }

                    // 遍历返回的课程
                    for (let course of courses) {
                        if (status === 1) unstartedCount++;

                        // 计算剩余名额
                        let surplus = 0;
                        if (course.surplus !== undefined) {
                            surplus = course.surplus;
                        } else {
                            surplus = (course.max || 0) - (course.course_apply_count || 0);
                        }

                        const isNew = course.id > (cache[cat.id] || 0);
                        // Debug模式下：进行中、未报名、有名额
                        // 注意：如果 is_sign 不存在，默认为未报名，依靠后端去重
                        const isNotSigned = course.is_sign === undefined ? true : !course.is_sign;
                        const isPickupTarget = isPickupMode && status === 2 && isNotSigned && surplus > 0;

                        // 如果课程ID大于缓存的ID，则是新课程；或者是捡漏模式下的捡漏目标
                        if (isNew || isPickupTarget) {
                            
                            // --- 筛选逻辑 ---
                            let isMatch = true;

                            // 1. 学院筛选
                            if (filterCollege !== "不限") {
                                const collegeList = course.college || [];
                                const department = course.department || "";
                                
                                // 匹配规则：
                                // 1. 课程未限制学院 (collegeList为空) -> 匹配
                                // 2. 课程限制列表中包含选中学院 -> 匹配
                                // 3. 课程主办方(department)包含选中学院 -> 匹配
                                const isUnlimited = collegeList.length === 0;
                                const isTargeted = collegeList.some(c => c.includes(filterCollege));
                                const isOrganizer = department.includes(filterCollege);

                                if (!isUnlimited && !isTargeted && !isOrganizer) {
                                    isMatch = false;
                                }
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
                                if (isNew) hasUpdate = true;
                                
                                const title = course.title || course.transcript_name || "未知名称";
                                const signTime = course.sign_start_time || "未知";
                                const place = course.time_place ? course.time_place.replace(/[\r\n]+/g, " ") : "未知地点";
                                const statusStr = CONFIG.statusMap[status];
                                
                                if (isDebug) console.log(`[Debug] 处理课程: ${title} (ID: ${course.id}, New: ${isNew})`);

                                // 自动设置报名ID (如果是未开始的课程)
                                if (status === 1 && isNew) {
                                    // 1. 加入待报名列表
                                    let list = [];
                                    try { list = JSON.parse($.getdata(CONFIG.signupListKey) || "[]"); } catch(e){}
                                    if (!Array.isArray(list)) list = [];
                                    
                                    let listMsg = "";
                                    if (!list.some(i => i.id == course.id)) {
                                        list.push({ id: course.id, title: title, time: signTime });
                                        $.setdata(JSON.stringify(list), CONFIG.signupListKey);
                                        listMsg = "\n📝 已加入待报名列表";
                                    }

                                    // 2. 更新旧版单ID (兼容)
                                    let autoIdMsg = "";
                                    if (course.id >= currentMaxSignupId) {
                                        $.setdata(course.id.toString(), CONFIG.signupCourseIdKey);
                                        currentMaxSignupId = course.id;
                                        autoIdMsg = `\n🎯 已自动设置报名ID: ${course.id}`;
                                    }
                                    
                                    notifyMsg += `【${cat.name} | ${statusStr}】🆕 ${title}\n⏰ 报名时间: ${signTime}\n📍 ${place}${listMsg}${autoIdMsg}\n\n`;
                                } else if (status === 2) {
                                    // 进行中的课程，尝试自动报名
                                    let signupResultMsg = "";
                                    // 假设字段 is_sign, 1为已报名
                                    if (!course.is_sign && isPickupMode) {
                                        console.log(`[Monitor] 尝试自动报名: ${title}`);
                                        const signupRes = await autoSignup(course.id, token, headers);
                                        
                                        if (signupRes.success) {
                                            signupResultMsg = `\n✅ 自动报名成功: ${signupRes.message}`;
                                        } else {
                                            signupResultMsg = `\n❌ 自动报名失败: ${signupRes.message}`;
                                        }

                                        // Debug模式 或 报名成功且非新课程 时发送单独通知
                                        if (isDebug || (signupRes.success && !isNew)) {
                                            const statusIcon = signupRes.success ? "✅" : "❌";
                                            // 标题简单，不要两行
                                            $.msg(`${statusIcon} 捡漏${signupRes.success ? "成功" : "失败"}`, "", `${title}\n${signupRes.message}`);
                                        }
                                    } else if (course.is_sign) {
                                        signupResultMsg = `\n⚠️ 已报名，跳过`;
                                    } else if (!isPickupMode) {
                                        signupResultMsg = `\n⚠️ 未开启捡漏模式，跳过报名`;
                                    }
                                    
                                    if (isNew) {
                                        notifyMsg += `【${cat.name} | ${statusStr}】🆕 ${title}\n⏰ 报名时间: ${signTime}\n📍 ${place}${signupResultMsg}\n\n`;
                                    }
                                } else if (isNew) {
                                    notifyMsg += `【${cat.name} | ${statusStr}】🆕 ${title}\n⏰ 报名时间: ${signTime}\n📍 ${place}\n\n`;
                                }
                            } else {
                                if (isDebug && isNew) console.log(`[Debug] 发现新课程(被筛选过滤): ${course.title} (ID: ${course.id})`);
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

    // 默认跳转链接
    let openUrl = "weixin://dl/business/?t=34E4TP288tr";

    if (isTokenExpired) {
        $.msg("⚠️ Token 已失效", "", "请重新进入小程序刷新列表获取新的 Token", { "open-url": openUrl });
        $done();
        return;
    }

    // 如果有更新，发送通知并保存新缓存
    if (hasUpdate) {
        $.msg("🆕 发现新课程", "", notifyMsg, { "open-url": openUrl });
        $.setdata(JSON.stringify(cache), CONFIG.cacheKey);
    } else {
        if (isDebug) {
            $.msg("🔍 监控完成", "", `共获取课程: ${totalFetchedCount}\n未开始课程: ${unstartedCount}\n暂无新课程`, { "open-url": openUrl });
            console.log(`[Debug] 暂无新课程更新`);
        } else {
            console.log("暂无新课程更新");
        }
    }
    
    $done();
}

// 自动报名函数
async function autoSignup(courseId, token, headers) {
    // 复制 headers 并移除 Content-Length
    const reqHeaders = JSON.parse(JSON.stringify(headers));
    delete reqHeaders['Content-Length'];
    reqHeaders['Host'] = 'qcbldekt.bit.edu.cn';

    const body = {
        course_id: parseInt(courseId),
        template_id: CONFIG.templateId
    };

    const options = {
        url: CONFIG.applyUrl,
        headers: reqHeaders,
        body: JSON.stringify(body),
        method: "POST"
    };

    try {
        const result = await httpPost(options);
        console.log(`[AutoSignup] 课程 ${courseId} 报名结果: ${JSON.stringify(result)}`);
        
        if (result.code === 200 || (result.message && result.message.includes("成功"))) {
            return { success: true, message: result.message || "报名成功" };
        } else {
            return { success: false, message: result.message || "未知错误" };
        }
    } catch (e) {
        console.log(`[AutoSignup] 异常: ${e}`);
        return { success: false, message: `请求异常: ${e}` };
    }
}

async function checkSignupList(token, headers) {
    let listStr = $.getdata(CONFIG.signupListKey) || "[]";
    let list = [];
    try {
        list = JSON.parse(listStr);
    } catch (e) {
        console.log(`[CheckList] 解析列表失败: ${e}`);
        return;
    }

    if (!Array.isArray(list)) list = [];
    if (list.length === 0) return;

    console.log(`[CheckList] 检查待报名列表: ${list.length} 个任务`);
    let hasChange = false;
    let newList = [];

    for (let item of list) {
        let shouldRun = false;
        // 时间判断: 0 或 过去时间
        if (item.time == "0" || item.time === 0) {
            shouldRun = true;
        } else {
            // 兼容 iOS 时间格式 2025-11-21 10:00:00 -> 2025/11/21 10:00:00
            let timeStr = (item.time || "").replace(/-/g, '/');
            let targetTime = new Date(timeStr).getTime();
            let now = new Date().getTime();
            
            // 如果解析失败(NaN)，或者时间已到
            if (!isNaN(targetTime) && now >= targetTime) {
                shouldRun = true;
            } else if (isNaN(targetTime)) {
                console.log(`[CheckList] 时间格式错误: ${item.time}，跳过`);
            }
        }

        if (shouldRun) {
            console.log(`[CheckList] 课程 ${item.title}(${item.id}) 到达报名时间，开始报名...`);
            const res = await autoSignup(item.id, token, headers);
            
            if (res.success) {
                $.msg("✅ 自动报名成功", "", `课程: ${item.title}\nID: ${item.id}\n${res.message}`);
                hasChange = true; // 报名成功，移除
                continue; // 不加入 newList
            } else {
                console.log(`[CheckList] 报名失败: ${res.message}`);
                // 失败保留，继续重试
                newList.push(item);
            }
        } else {
            newList.push(item);
        }
    }

    if (hasChange) {
        $.setdata(JSON.stringify(newList), CONFIG.signupListKey);
    }
}

function httpPost(options) {
    return new Promise((resolve, reject) => {
        $.post(options, (err, resp, data) => {
            if (err) {
                reject(err);
            } else {
                try {
                    const res = JSON.parse(data);
                    resolve(res);
                } catch (e) {
                    resolve(data);
                }
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
