/*
 * 脚本名称：北理工第二课堂监控
 * 作者：Gemini for User
 * 描述：定时监控第二课堂的新活动，支持筛选和自动报名（捡漏）。
 * 
 * [task_local]
 * 30 8-22/2 * * * https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/dekt_monitor.js, tag=第二课堂监控, enabled=true
 * */

const $ = new Env("北理工第二课堂");

console.log("加载脚本: 北理工第二课堂监控 (v20251202)");

// 配置项
const CONFIG = {
    // BoxJS/Store Keys
    tokenKey: "bit_sc_token",
    headersKey: "bit_sc_headers",
    userIdKey: "bit_sc_user_id", // 用户ID Key
    cacheKey: "bit_sc_cache", // 用来存上一次的最新课程ID
    debugKey: "bit_sc_debug", // 调试模式开关
    pickupKey: "bit_sc_pickup_mode", // 捡漏模式开关
    notifyNoUpdateKey: "bit_sc_notify_no_update", // 无更新通知开关
    delayKey: "bit_sc_random_delay", // 随机延迟 Key
    signupListKey: "bit_sc_signup_list", // 待报名列表 Key
    filterCollegeKey: "bit_sc_filter_college",
    filterGradeKey: "bit_sc_filter_grade",
    filterTypeKey: "bit_sc_filter_type",
    filterAutoBlacklistCategoriesKey: "bit_sc_auto_blacklist_categories", // 自动报名栏目黑名单 Key
    unenrollCourseIdKey: "bit_sc_unenroll_course_id", // 取消报名课程ID Key (已弃用原 signupCourseIdKey)
    lastSignupKey: "bit_sc_last_signup", // 最后成功报名课程 Key (存为 JSON 对象 {id,title,time,user_id})
    blacklistKey: "bit_sc_blacklist", // 黑名单 Key (逗号分隔)
    blacklistKeywordsKey: "bit_sc_blacklist_keywords", // 黑名单关键词 Key (逗号分隔)
    
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
    const userId = $.getdata(CONFIG.userIdKey) || deriveUserId(token);
    const isDebug = $.getdata(CONFIG.debugKey) === "true";
    const isPickupMode = $.getdata(CONFIG.pickupKey) === "true";
    const isNotifyNoUpdate = $.getdata(CONFIG.notifyNoUpdateKey) === "true";
    const randomDelay = parseInt($.getdata(CONFIG.delayKey) || "0");
    
    // 动态获取微信小程序跳转链接，失败时直接跳转微信
    let openUrl = null;
    try {
        const dynamicUrl = await getWechatJumpLink();
        if (dynamicUrl) {
            openUrl = dynamicUrl;
        } else {
            openUrl = "weixin://"; // 获取失败，直接跳转微信
        }
    } catch (e) {
        console.error('获取动态链接失败，直接跳转微信:', e);
        openUrl = "weixin://"; // 发生错误，直接跳转微信
    }
    
    // 获取筛选配置
    const filterCollege = $.getdata(CONFIG.filterCollegeKey) || "不限";
    const filterGrade = $.getdata(CONFIG.filterGradeKey) || "不限";
    const filterType = $.getdata(CONFIG.filterTypeKey) || "不限";
    // 自动报名/捡漏栏目黑名单配置（BoxJS 多选）：空或多选结果（CSV 或 JSON 数组）
    // 读取黑名单配置（仅使用新键 bit_sc_auto_blacklist_categories）
    const filterAutoBlacklistCategoriesRaw = $.getdata(CONFIG.filterAutoBlacklistCategoriesKey) || "";

    // 解析自动报名栏目黑名单（支持 ID 或名称），
    // blacklistAutoCategoryIds/Names 为空数组表示无黑名单（允许所有栏目自动报名）
    let blacklistAutoCategoryIds = [];
    let blacklistAutoCategoryNames = [];
    try {
        if (filterAutoBlacklistCategoriesRaw && filterAutoBlacklistCategoriesRaw.trim()) {
            let items = [];
            const raw = filterAutoBlacklistCategoriesRaw.trim();
            if (raw.startsWith('[')) {
                items = JSON.parse(raw);
            } else if (Array.isArray(filterAutoBlacklistCategoriesRaw)) {
                items = filterAutoBlacklistCategoriesRaw;
            } else if (raw.includes(',')) {
                items = raw.split(/[,，]/).map(s => s.trim()).filter(s => s);
            } else {
                items = [raw];
            }

            // Normalize into ID list and name list
            for (const it of items) {
                if (it === null || it === undefined) continue;
                const s = String(it).trim();
                if (s === '') continue;
                const n = parseInt(s, 10);
                if (!Number.isNaN(n)) {
                    blacklistAutoCategoryIds.push(n);
                }
                // always keep the raw string name as well (for backward compatibility)
                blacklistAutoCategoryNames.push(s);
            }
        }
    } catch (e) {
        console.log(`[Debug] 解析自动报名栏目黑名单失败: ${e}`);
        blacklistAutoCategoryIds = [];
        blacklistAutoCategoryNames = [];
    }
    // Debug 输出解析结果，帮助排查用户输入格式
    try {
        const isDebug = $.getdata(CONFIG.debugKey) === "true";
        if (isDebug) {
            console.log(`[Debug] 自动报名栏目黑名单解析: ids=${JSON.stringify(blacklistAutoCategoryIds)}, names=${JSON.stringify(blacklistAutoCategoryNames)}`);
        }
    } catch (e) {
        console.log(`[Debug] 打印黑名单解析结果失败: ${e}`);
    }
    
    // 获取黑名单(ID)
    const blacklistStr = $.getdata(CONFIG.blacklistKey) || "";
    const blacklist = blacklistStr.split(/[,，]/).map(id => id.trim()).filter(id => id); // 支持中英文逗号

    // 获取黑名单关键词
    const blacklistKeywordsStr = $.getdata(CONFIG.blacklistKeywordsKey) || "";
    const blacklistKeywords = blacklistKeywordsStr.split(/[,，]/).map(kw => kw.trim()).filter(kw => kw); // 支持中英文逗号

    if (!token) {
        $.msg("❌ 未找到 Token", "", "请先运行 bit_cookie.js 脚本，并进入微信小程序“第二课堂”刷新任意列表以获取 Token。");
        $done();
        return;
    }

    const headers = {};
    headers['Authorization'] = normalizeAuthToken(token);
    headers['Content-Type'] = 'application/json;charset=utf-8';

    if (!headers['Authorization']) {
        $.msg("❌ Token 无效", "", "请先运行 bit_cookie.js 脚本重新获取 Token。");
        $done();
        return;
    }


function normalizeAuthToken(token) {
    if (!token) return "";
    const t = String(token).trim();
    if (!t) return "";
    return /^Bearer\s+/i.test(t) ? t : `Bearer ${t}`;
}
    // --- 新增：检查待报名列表 (仅 Debug 模式) ---
    if (isDebug) {
        await checkSignupList(token, headers, userId);
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
    // Debug 模式下收集所有解析到的课程，便于最后统一打印
    const debugCourses = [];

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
                        // 记录到全局调试列表
                        for (const c of courses) {
                            debugCourses.push({
                                id: c.id,
                                title: (c.title || c.transcript_name || "未知名称") + "",
                                category: cat.name,
                                status
                            });
                        }
                    }

                    // 遍历返回的课程
                    for (let course of courses) {
                        // 黑名单检查(ID)
                        if (blacklist.includes(course.id.toString())) {
                            if (isDebug) console.log(`[Debug][${cat.name}][ID:${course.id}] 在黑名单(ID)中，跳过: ${course.title || '未知名称'}`);
                            continue;
                        }

                        // 黑名单关键词检查
                        const courseTitle = course.title || course.transcript_name || "";
                        const matchedKeyword = blacklistKeywords.find(kw => courseTitle.includes(kw));
                        if (matchedKeyword) {
                            if (isDebug) console.log(`[Debug][${cat.name}][ID:${course.id}] 标题命中黑名单关键词[${matchedKeyword}]，跳过: ${courseTitle}`);
                            continue;
                        }

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
                        // 当前栏目是否允许自动报名/捡漏（黑名单模式：黑名单为空表示全部允许，否则黑名单中的栏目不允许）
                        const isCategoryBlacklisted = (
                            (blacklistAutoCategoryIds.length > 0 && blacklistAutoCategoryIds.includes(cat.id)) ||
                            (blacklistAutoCategoryNames.length > 0 && blacklistAutoCategoryNames.includes(cat.name))
                        );
                        const isCategoryAllowedForAuto = !isCategoryBlacklisted;
                        const isPickupTarget = isPickupMode && status === 2 && isNotSigned && surplus > 0 && isCategoryAllowedForAuto;

                        // 如果课程ID大于缓存的ID，则是新课程；或者是捡漏模式下的捡漏目标；或者是未开始的课程(确保加入列表)
                        if (isNew || isPickupTarget || (status === 1)) {
                            
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
                                // const isOrganizer = department.includes(filterCollege); // 移除主办方匹配

                                if (!isUnlimited && !isTargeted) {
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
                                
                                if (isDebug) console.log(`[Debug][${cat.name}][ID:${course.id}] 处理课程: ${title} (New: ${isNew})`);

                                // 自动设置报名ID (如果是未开始的课程)
                                if (status === 1) {
                                    // 1. 加入待报名列表
                                    let list = [];
                                    try { list = JSON.parse($.getdata(CONFIG.signupListKey) || "[]"); } catch(e){}
                                    if (!Array.isArray(list)) list = [];
                                    
                                    let listMsg = "";
                                    if (!list.some(i => i.id == course.id)) {
                                        list.push({ id: course.id, title: title, time: signTime });
                                        $.setdata(JSON.stringify(list), CONFIG.signupListKey);
                                        listMsg = "\n📝 已加入待报名列表";
                                        if (isDebug) console.log(`[Debug] 加入待报名列表: ${title}`);
                                    }

                                    // 2. 更新旧版单ID (兼容)
                                    let autoIdMsg = "";
                                    // if (course.id >= currentMaxSignupId) {
                                    //     $.setdata(course.id.toString(), CONFIG.signupCourseIdKey);
                                    //     currentMaxSignupId = course.id;
                                    //     autoIdMsg = `\n🎯 已自动设置报名ID: ${course.id}`;
                                    // }
                                    
                                    if (isNew) {
                                        notifyMsg += `#${course.id} 【${cat.name} | ${statusStr}】🆕 ${title}\n⏰ 报名时间: ${signTime}\n📍 ${place}${listMsg}${autoIdMsg}\n\n`;
                                    }
                                } else if (status === 2) {
                                    // 进行中的课程，尝试自动报名
                                    let signupResultMsg = "";
                                    // 假设字段 is_sign, 1为已报名
                                    // 修改：如果是捡漏模式，或者发现了新课程(且未报名)，都直接尝试报名
                                    // 仅当当前栏目不在黑名单中才尝试自动报名；否则仅通知
                                    if (!course.is_sign && isCategoryAllowedForAuto && (isPickupMode || isNew)) {
                                        console.log(`[Monitor][${cat.name}][ID:${course.id}] 尝试自动报名(新课程或捡漏): ${title}`);
                                        const signupRes = await autoSignup(course.id, token, headers);
                                        
                                        if (signupRes.success) {
                                            signupResultMsg = `\n✅ 自动报名成功: ${signupRes.message}`;
                                            // 存储最后一次成功报名的课程（JSON 对象，便于与待报名列表保持一致）
                                            try {
                                                const lastObj = { id: course.id, title: title, time: (new Date()).toISOString(), user_id: userId || null };
                                                $.setdata(JSON.stringify(lastObj), CONFIG.lastSignupKey);
                                                console.log(`[Monitor] 📝 已记录最后成功报名: ${JSON.stringify(lastObj)}`);
                                            } catch (e) { console.log(`[Monitor] 记录最后报名失败: ${e}`); }
                                            // 报名成功后自动加入黑名单，防止重复处理
                                            try {
                                                const blMsg = addToBlacklist(course.id);
                                                if (isDebug) console.log(`[Monitor] addToBlacklist: ${blMsg}`);
                                            } catch (e) { console.log(`[Monitor] 添加黑名单失败: ${e}`); }
                                        } else {
                                            signupResultMsg = `\n❌ 自动报名失败: ${signupRes.message}`;
                                        }

                                        // Debug模式 或 报名成功且非新课程 时发送单独通知
                                        if (isDebug || (signupRes.success && !isNew)) {
                                            const statusIcon = signupRes.success ? "✅" : "❌";
                                            // 构造正文，报名成功时补充时长
                                            let body = `#${course.id} ${title}\n${signupRes.message}`;
                                            if (signupRes.success) {
                                                const d = getDurationIfTime(course);
                                                if (d != null) body += `\n⏱ 时长: ${d}分钟`;
                                            }
                                            $.msg(`${statusIcon} 自动报名${signupRes.success ? "成功" : "失败"}`, "", body);
                                        }
                                    } else if (course.is_sign) {
                                        signupResultMsg = `\n⚠️ 已报名，跳过`;
                                    } else if (!isCategoryAllowedForAuto) {
                                        signupResultMsg = `\n⚠️ 在自动报名栏目黑名单中，跳过自动报名`;
                                    } else if (!isPickupMode && !isNew) {
                                        signupResultMsg = `\n⚠️ 未开启捡漏模式，跳过报名`;
                                    }
                                    
                                    if (isNew) {
                                        // 聚合通知：仅当报名成功时追加时长
                                        let extraDuration = "";
                                        if (signupResultMsg.startsWith("\n✅")) {
                                            const d2 = getDurationIfTime(course);
                                            if (d2 != null) extraDuration = `\n⏱ 时长: ${d2}分钟`;
                                        }
                                        notifyMsg += `#${course.id} 【${cat.name} | ${statusStr}】🆕 ${title}\n⏰ 报名时间: ${signTime}\n📍 ${place}${extraDuration}${signupResultMsg}\n\n`;
                                    }
                                } else if (isNew) {
                                    notifyMsg += `#${course.id} 【${cat.name} | ${statusStr}】🆕 ${title}\n⏰ 报名时间: ${signTime}\n📍 ${place}\n\n`;
                                }
                            } else {
                                if (isDebug && isNew) console.log(`[Debug][${cat.name}][ID:${course.id}] 发现新课程(被筛选过滤): ${course.title}`);
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
        $.msg("⚠️ Token 已失效", "", "请重新进入小程序刷新列表获取新的 Token", { "open-url": openUrl });
        $done();
        return;
    }

    // Debug 模式：在脚本结束前打印所有解析到的课程（ID + 标题前15字）
    if (isDebug) {
        try {
            console.log("[Debug] ================== 本次解析课程汇总 ==================");
            if (debugCourses.length === 0) {
                console.log("[Debug] 本次未解析到任何课程数据");
            } else {
                for (const item of debugCourses) {
                    const shortTitle = (item.title || "").toString().slice(0, 15);
                    const statusStr = CONFIG.statusMap[item.status] || item.status;
                    console.log(`[Debug][${item.category}][${statusStr}] ID=${item.id} 标题="${shortTitle}${item.title.length > 15 ? '...' : ''}"`);
                }
                console.log(`[Debug] 共解析课程数: ${debugCourses.length}`);
            }
            console.log("[Debug] ==================================================");
        } catch (e) {
            console.log(`[Debug] 打印课程汇总时出错: ${e}`);
        }
    }

    // 如果有更新，发送通知并保存新缓存
    if (hasUpdate) {
        $.msg("🆕 发现新课程", "", notifyMsg, { "open-url": openUrl });
        $.setdata(JSON.stringify(cache), CONFIG.cacheKey);
    } else {
        // Debug 模式下无新课程不发送通知，仅打印日志
        if (isNotifyNoUpdate) {
            $.msg("🔍 监控完成", "", `共获取课程: ${totalFetchedCount}\n未开始课程: ${unstartedCount}\n暂无新课程`, { "open-url": openUrl });
        }
        if (isDebug) {
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
        console.log(`[AutoSignup][ID:${courseId}] 报名结果: ${JSON.stringify(result)}`);
        
        if (result.code === 200 || (result.message && result.message.includes("成功"))) {
            return { success: true, message: result.message || "报名成功" };
        } else {
            return { success: false, message: result.message || "未知错误" };
        }
    } catch (e) {
        console.log(`[AutoSignup][ID:${courseId}] 异常: ${e}`);
        return { success: false, message: `请求异常: ${e}` };
    }
}

async function checkSignupList(token, headers, userId) {
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
                console.log(`[CheckList][ID:${item.id}] 时间格式错误: ${item.time}，跳过`);
            }
        }

        if (shouldRun) {
            console.log(`[CheckList][ID:${item.id}] 到达报名时间，开始报名... ${item.title}`);
            const res = await autoSignup(item.id, token, headers);
            
            if (res.success) {
                let body = `#${item.id} ${item.title}\n${res.message}`;
                try {
                    const d = await getDurationByIdIfTime(item.id, headers);
                    if (d != null) body += `\n⏱ 时长: ${d}分钟`;
                } catch (_) {}
                $.msg("✅ 自动报名成功", "", body);
                // 存储最后一次成功报名的课程（JSON 对象）
                try {
                    const lastObj = { id: item.id, title: item.title || "", time: (new Date()).toISOString(), user_id: userId || null };
                    $.setdata(JSON.stringify(lastObj), CONFIG.lastSignupKey);
                    console.log(`[CheckList] 📝 已记录最后成功报名: ${JSON.stringify(lastObj)}`);
                } catch (e) { console.log(`[CheckList] 记录最后报名失败: ${e}`); }
                hasChange = true; // 报名成功，移除
                continue; // 不加入 newList
            } else {
                console.log(`[CheckList][ID:${item.id}] 报名失败: ${res.message}`);
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

function httpGet(url, headers) {
    return new Promise((resolve, reject) => {
        $.get({ url, headers }, (err, resp, data) => {
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

// 提取课程时长（分钟）：仅当完成标志为 time 时返回数字
function getDurationIfTime(course) {
    try {
        const flag = course && course.completion_flag;
        const typeFlag = course && course.transcript_index_type && course.transcript_index_type.completion_flag;
        if (flag === 'time' || typeFlag === 'time') {
            let d = null;
            if (course && course.duration != null) d = parseInt(course.duration, 10);
            if ((d == null || Number.isNaN(d)) && course && course.transcript_index_type && course.transcript_index_type.duration != null) {
                d = parseInt(course.transcript_index_type.duration, 10);
            }
            if ((d == null || Number.isNaN(d)) && course && typeof course.completion_flag_text === 'string') {
                const m = course.completion_flag_text.match(/(\d{1,3})\s*分钟/);
                if (m) d = parseInt(m[1], 10);
            }
            return Number.isNaN(d) ? null : d;
        }
    } catch (e) {}
    return null;
}

// 通过 REST 详情按需获取课程时长（仅当完成标志为 time 时返回数字）
async function getDurationByIdIfTime(courseId, headers) {
    try {
        const url = `https://qcbldekt.bit.edu.cn/api/course/info/${courseId}`;
        const resp = await httpGet(url, headers);
        const data = resp && (resp.data || resp.json && resp.json.data) || null;
        if (!data) return null;
        const flag = data.completion_flag || (data.transcript_index_type && data.transcript_index_type.completion_flag);
        if (flag !== 'time') return null;
        let d = null;
        if (data.duration != null) d = parseInt(data.duration, 10);
        if ((d == null || Number.isNaN(d)) && data.transcript_index_type && data.transcript_index_type.duration != null) {
            d = parseInt(data.transcript_index_type.duration, 10);
        }
        if ((d == null || Number.isNaN(d)) && typeof data.completion_flag_text === 'string') {
            const m = data.completion_flag_text.match(/(\d{1,3})\s*分钟/);
            if (m) d = parseInt(m[1], 10);
        }
        return Number.isNaN(d) ? null : d;
    } catch (e) {
        return null;
    }
}

/**
 * 动态获取微信小程序跳转链接
 * @param {string} pagePath - 小程序的页面路径 (可选)
 * @returns {Promise<string|null>} - 返回 weixin:// 开头的链接
 */
async function getWechatJumpLink(pagePath = '/pages/index/index') {
    const apiUrl = `https://qcbldekt.bit.edu.cn/api/generatescheme?path=${encodeURIComponent(pagePath)}`;
    
    try {
        const response = await fetch(apiUrl);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.code === 200 && result.data) {
            return result.data; // 返回 weixin://dl/business/?t=...
        } else {
            console.error('获取微信小程序链接失败:', result.message);
            return null;
        }
    } catch (error) {
        console.error('请求微信小程序链接时发生错误:', error);
        return null;
    }
}

function deriveUserId(authorizationHeader) {
    try {
        if (!authorizationHeader) return "";
        // 支持 "Bearer 611156|xxxx" 或 "611156|xxxx"
        let raw = String(authorizationHeader).trim();
        if (raw.toLowerCase().startsWith("bearer ")) raw = raw.slice(7).trim();
        const first = raw.split("|")[0].trim();
        return /^\d+$/.test(first) ? first : "";
    } catch (_) { return ""; }
}

// 将课程ID添加到黑名单（本文件局部实现，使用 CONFIG.blacklistKey）
function addToBlacklist(courseId) {
    try {
        const blacklistStr = $.getdata(CONFIG.blacklistKey) || "";
        // 解析已有的黑名单（支持逗号分隔或JSON数组格式）
        let blacklist = [];
        const trimmed = String(blacklistStr).trim();
        if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
            try {
                const arr = JSON.parse(trimmed);
                if (Array.isArray(arr)) blacklist = arr.map(x => String(x).trim()).filter(Boolean);
            } catch {
                blacklist = trimmed.split(/[,，]/).map(id => id.trim()).filter(id => id);
            }
        } else {
            blacklist = trimmed.split(/[,，]/).map(id => id.trim()).filter(id => id);
        }

        const courseIdStr = String(courseId).trim();
        if (blacklist.includes(courseIdStr)) {
            console.log(`[monitor] 课程 ${courseIdStr} 已在黑名单中，无需重复添加`);
            return "\n📝 已在黑名单中";
        }

        blacklist.push(courseIdStr);
        $.setdata(blacklist.join(","), CONFIG.blacklistKey);
        console.log(`[monitor] 已将课程 ${courseIdStr} 添加到黑名单`);
        return "\n📝 已自动添加到黑名单";
    } catch (e) {
        console.log(`[monitor] 添加黑名单失败: ${e}`);
        return "\n⚠️ 添加黑名单失败";
    }
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
