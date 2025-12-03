/*
 * 脚本名称：北理工第二课堂签到
 * 作者：Gemini for User
 * 描述：自动检查已报名课程并进行签到/签退。
 * 
 * [task_local]
 * # 签到脚本 (默认关闭，需手动运行或开启)
 * 0 8-22/1 * * * https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/dekt_signin.js, tag=第二课堂签到, enabled=false
 */


// ====== 配置项 ======
const $ = new Env("北理工第二课堂签到");
const CONFIG = {
    tokenKey: "bit_sc_token",
    headersKey: "bit_sc_headers",
    autoSignAllKey: "bit_sc_auto_sign_all",
    runtimeIdsKey: "bit_sc_runtime_sign_ids",
    listUrl: "https://qcbldekt.bit.edu.cn/api/transcript/course/signIn/list?page=1&limit=10&type=1",
    infoUrl: "https://qcbldekt.bit.edu.cn/api/transcript/checkIn/info",
    signInUrl: "https://qcbldekt.bit.edu.cn/api/transcript/signIn",
    courseInfoUrlRest: "https://qcbldekt.bit.edu.cn/api/course/info/",
    myCourseListUrl: "https://qcbldekt.bit.edu.cn/api/course/list/my?page=1&limit=200"
};

// ====== 主入口 ======
main().finally(() => $.done());

async function main() {
    try {
        const { token, headers, autoSignAll, targetIds } = getEnvConfig();
        if (!token) {
            $.msg($.name, "❌ 未找到 Token", "请先运行获取 Cookie 脚本或在 BoxJS 中填写");
            return;
        }

        const courses = await getCourseList(headers);
        const processedIds = new Set();

        if (Array.isArray(courses) && courses.length > 0) {
            await handleCourseList(courses, headers, autoSignAll);
            try {
                for (const c of courses) {
                    if (c && (c.course_id != null)) processedIds.add(String(c.course_id));
                }
            } catch {}
        }

        // 对于通过 BoxJS/CLI 指定的目标课程：
        // - 当 autoSignAll=false 时，无论是否在列表中都要单独处理（确保会尝试签到/签退）
        // - 当 autoSignAll=true 时，若已通过列表处理过则跳过以避免重复
        const pendingTargetIds = (targetIds || [])
            .map(id => String(id))
            .filter(id => id && (!autoSignAll || !processedIds.has(id)));

        if (pendingTargetIds.length > 0) {
            await handleTargetIds(pendingTargetIds, headers);
        }
    } catch (e) {
        console.log(`❌ 脚本运行异常: ${e}`);
    }
}

// ====== 环境与配置读取 ======
function getEnvConfig() {
    const token = $.getdata(CONFIG.tokenKey);
    const savedHeadersStr = $.getdata(CONFIG.headersKey);
    let headers = {};
    if (savedHeadersStr) {
        try { headers = JSON.parse(savedHeadersStr); } catch {}
    }
    headers['Authorization'] = token && token.startsWith("Bearer") ? token : `Bearer ${token}`;
    headers['Content-Type'] = 'application/json;charset=utf-8';
    headers['Host'] = 'qcbldekt.bit.edu.cn';
    if (headers['Content-Length']) delete headers['Content-Length'];
    const autoSignAll = String($.getdata(CONFIG.autoSignAllKey) || "false").toLowerCase() === "true";
    const runtimeIdsStr = $.getdata(CONFIG.runtimeIdsKey) || "";
    let targetIds = runtimeIdsStr.split(/[,，\s]+/).map(s => s.trim()).filter(s => s);
    if (typeof global !== 'undefined') {
        if (global.DEKT_TARGET_IDS && Array.isArray(global.DEKT_TARGET_IDS)) {
            targetIds = Array.from(new Set([...(targetIds || []), ...global.DEKT_TARGET_IDS.map(String)]));
        } else if (global.DEKT_TARGET_ID) {
            targetIds = Array.from(new Set([...(targetIds || []), String(global.DEKT_TARGET_ID)]));
        }
    }
    return { token, headers, autoSignAll, targetIds };
}

// ====== 课程列表获取 ======
async function getCourseList(headers) {
    try {
        const listData = await httpGet(CONFIG.listUrl, headers);
        if (listData && listData.code === 200) {
            return listData.data.items || [];
        }
    } catch {}
    return [];
}

// ====== 处理课程列表 ======
async function handleCourseList(courses, headers, autoSignAll) {
    for (const course of courses) {
        // 参考 my_activities：过滤已取消课程
        if (course.status_label && course.status_label.includes("已取消")) continue;
        if (typeof course.status !== 'undefined' && (course.status === 4 || course.status === '4')) continue;
        const info = await getCourseInfo(course.course_id, headers);
        if (!info) continue;
        const meta = await getCourseMeta(course.course_id, headers);
        if (meta && meta.completionType === 'time') {
            const safeTitle = course.course_title || info.course_title || String(course.course_id);
            showCourseLog(course.course_id, safeTitle, info, meta);
            if (autoSignAll) {
                await trySign(course.course_id, info, headers, '签到', safeTitle);
                await trySign(course.course_id, info, headers, '签退', safeTitle);
            }
        }
    }
}

// ====== 处理指定ID ======
async function handleTargetIds(targetIds, headers) {
    const skipDelay = Array.isArray(targetIds) && targetIds.length === 1;
    for (const tId of targetIds) {
        const info = await getCourseInfo(tId, headers);
        if (!info) continue;
        // 若接口返回中包含状态，也参考 activities 逻辑过滤取消状态
        if (info.status_label && info.status_label.includes("已取消")) continue;
        if (typeof info.status !== 'undefined' && (info.status === 4 || info.status === '4')) continue;
        const meta = await getCourseMeta(tId, headers);
        if (meta && meta.completionType === 'time') {
            const safeTitle = await resolveCourseTitle(tId, info, headers);
            showCourseLog(tId, safeTitle, info, meta);
            await trySign(tId, info, headers, '签到', safeTitle, { skipDelay });
            await trySign(tId, info, headers, '签退', safeTitle, { skipDelay });
        }
    }
}

// ====== 日志输出 ======
function showCourseLog(courseId, title, info, meta) {
    const siWin = isInWindow(info, 'signIn');
    const soWin = isInWindow(info, 'signOut');
    console.log(`===== 课程 ${courseId} | ${title} =====`);
    console.log(`时长: ${meta.duration != null ? meta.duration : '未知'}`);
    console.log(`签到窗口: ${siWin ? '是' : '否'}${info.sign_in_start_time ? ` (${info.sign_in_start_time} - ${info.sign_in_end_time})` : ''}`);
    console.log(`签退窗口: ${soWin ? '是' : '否'}${info.sign_out_start_time ? ` (${info.sign_out_start_time} - ${info.sign_out_end_time})` : ''}`);
    console.log(`----------------------------------------------`);
}

// ====== 签到/签退尝试 ======
async function trySign(courseId, info, headers, typeStr, courseTitle, options = {}) {
    const inSignIn = isInWindow(info, 'signIn');
    const inSignOut = isInWindow(info, 'signOut');
    if (inSignIn && inSignOut) {
        // 同时处于签到和签退窗口，优先签到
        $.msg($.name, `处于签到和签退窗口，默认签到`, `${courseTitle}`);
        await executeSign(courseId, info, headers, '签到', courseTitle, options);
    } else if (typeStr === '签到' && inSignIn) {
        $.msg($.name, `处于签到窗口`, `${courseTitle}`);
        await executeSign(courseId, info, headers, '签到', courseTitle, options);
    } else if (typeStr === '签退' && inSignOut) {
        $.msg($.name, `处于签退窗口`, `${courseTitle}`);
        await executeSign(courseId, info, headers, '签退', courseTitle, options);
    }
}
// ...existing code...

async function checkAndSignIn() {
    const token = $.getdata(CONFIG.tokenKey);
    const savedHeadersStr = $.getdata(CONFIG.headersKey);

    if (!token) {
        $.msg($.name, "❌ 未找到 Token", "请先运行获取 Cookie 脚本或在 BoxJS 中填写");
        return;
    }

    let headers = {};
    if (savedHeadersStr) {
        try {
            headers = JSON.parse(savedHeadersStr);
        } catch (e) {
            console.log("Headers 解析失败，使用默认 Headers");
        }
    }
    headers['Authorization'] = token.startsWith("Bearer") ? token : `Bearer ${token}`;
    headers['Content-Type'] = 'application/json;charset=utf-8';
    headers['Host'] = 'qcbldekt.bit.edu.cn';
    if (headers['Content-Length']) delete headers['Content-Length'];

    // 读取 BoxJS 配置
    const autoSignAll = String($.getdata(CONFIG.autoSignAllKey) || "false").toLowerCase() === "true";
    const runtimeIdsStr = $.getdata(CONFIG.runtimeIdsKey) || "";
    let targetIds = runtimeIdsStr.split(/[,，\s]+/).map(s => s.trim()).filter(s => s);

    // 兼容 global 指定（如果存在，则合并）
    if (typeof global !== 'undefined') {
        if (global.DEKT_TARGET_IDS && Array.isArray(global.DEKT_TARGET_IDS)) {
            targetIds = Array.from(new Set([...(targetIds || []), ...global.DEKT_TARGET_IDS.map(String)]));
        } else if (global.DEKT_TARGET_ID) {
            targetIds = Array.from(new Set([...(targetIds || []), String(global.DEKT_TARGET_ID)]));
        }
    }

    // 获取列表数据
    let courses = [];
    try {
        const listData = await httpGet(CONFIG.listUrl, headers);
        if (listData && listData.code === 200) {
            courses = listData.data.items || [];
        }
    } catch (e) {
        // 获取列表失败时，仍继续处理“指定ID签到”
    }
    // 统一处理逻辑：
    // - 仅当课程完成标识为 time 时输出时长/签到签退
    // - 日志顺序：先输出签到，再输出签退
    // - 执行顺序：先尝试签到，再尝试签退
    if (Array.isArray(courses) && courses.length > 0) {
        for (const course of courses) {
            const info = await getCourseInfo(course.course_id, headers);
            if (!info) continue;
            const meta = await getCourseMeta(course.course_id, headers);
            const title = course.course_title || info.course_title || String(course.course_id);
            const siWin = isInWindow(info, 'signIn');
            const soWin = isInWindow(info, 'signOut');
                // 只显示 time 类型课程
                if (meta && meta.completionType === 'time') {
                    console.log(`===== 课程 ${course.course_id} | ${title} =====`);
                    const duration = meta.duration;
                    console.log(`时长: ${duration != null ? duration : '未知'}`);
                    console.log(`签到窗口: ${siWin ? '是' : '否'}${info.sign_in_start_time ? ` (${info.sign_in_start_time} - ${info.sign_in_end_time})` : ''}`);
                    console.log(`签退窗口: ${soWin ? '是' : '否'}${info.sign_out_start_time ? ` (${info.sign_out_start_time} - ${info.sign_out_end_time})` : ''}`);
                    console.log(`----------------------------------------------`);
                    // 仅在开启 autoSignAll 且为 time 类型时执行
                    if (autoSignAll) {
                        if (siWin) {
                            $.msg($.name, `处于签到窗口`, `${title}`);
                            await executeSign(course.course_id, info, headers, '签到', title);
                        }
                        if (soWin) {
                            $.msg($.name, `处于签退窗口`, `${title}`);
                            await executeSign(course.course_id, info, headers, '签退', title);
                        }
                    }
                }
        }
    } else if (targetIds.length > 0) {
        // 仅对指定 ID 尝试签到
        const skipDelay = targetIds.length === 1;
        for (const tId of targetIds) {
            const info = await getCourseInfo(tId, headers);
            if (!info) continue;
            const meta = await getCourseMeta(tId, headers);
            const title = await resolveCourseTitle(tId, info, headers);
            const soWin = isInWindow(info, 'signOut');
            const siWin = isInWindow(info, 'signIn');
                // 只显示 time 类型课程
                if (meta && meta.completionType === 'time') {
                    console.log(`===== 课程 ${tId} | ${title} =====`);
                    const duration = meta.duration;
                    console.log(`时长: ${duration != null ? duration : '未知'}`);
                    console.log(`签到窗口: ${siWin ? '是' : '否'}${info.sign_in_start_time ? ` (${info.sign_in_start_time} - ${info.sign_in_end_time})` : ''}`);
                    console.log(`签退窗口: ${soWin ? '是' : '否'}${info.sign_out_start_time ? ` (${info.sign_out_start_time} - ${info.sign_out_end_time})` : ''}`);
                    console.log(`----------------------------------------------`);
                    if (siWin) {
                        $.msg($.name, `处于签到时间窗口`, `课程: ${title}`);
                        await executeSign(tId, info, headers, '签到', title, { skipDelay });
                    }
                    if (soWin) {
                        $.msg($.name, `处于签退时间窗口`, `课程: ${title}`);
                        await executeSign(tId, info, headers, '签退', title, { skipDelay });
                    }
                }
        }
    }
}

// 获取课程时长：优先 REST 详情，其次我的课程列表兜底
async function getCourseDuration(courseId, headers) {
    // 1) REST 课程详情
    try {
        const rest = await httpGet(`${CONFIG.courseInfoUrlRest}${courseId}`, headers);
        if (rest && rest.code === 200 && rest.data) {
            if (rest.data.duration != null) return rest.data.duration;
        }
    } catch (e) {
        // 忽略错误，继续兜底
    }
    // 2) 我的课程列表兜底
    try {
        const list = await httpGet(CONFIG.myCourseListUrl, headers);
        if (list && list.code === 200 && list.data && Array.isArray(list.data.items)) {
            const found = list.data.items.find(x => String(x.course_id || x.id) === String(courseId));
            if (found && found.duration != null) return found.duration;
        } else {
            // 旧接口兜底
            const oldList = await httpGet("https://qcbldekt.bit.edu.cn/api/transcript/course/list/my?page=1&limit=200", headers);
            if (oldList && oldList.code === 200 && oldList.data && Array.isArray(oldList.data.items)) {
                const found2 = oldList.data.items.find(x => String(x.course_id || x.id) === String(courseId));
                if (found2 && found2.duration != null) return found2.duration;
            }
        }
    } catch (e) {
        // 忽略错误
    }
    return null;
}

async function getCourseInfo(courseId, headers) {
    const url = `${CONFIG.infoUrl}?course_id=${courseId}`;
    try {
        const data = await httpGet(url, headers);
        if (data && data.code === 200) {
            return data.data;
        } else {
            console.log(`❌ 获取课程详情失败: ${JSON.stringify(data)}`);
            return null;
        }
    } catch (e) {
        console.error(`❌ 获取课程详情异常: ${e}`);
        return null;
    }
}
    // 获取课程元信息：duration + completionType(time/other)
    async function getCourseMeta(courseId, headers) {
        try {
            const rest = await httpGet(`${CONFIG.courseInfoUrlRest}${courseId}`, headers);
            if (rest && rest.code === 200 && rest.data) {
                const d = rest.data;
                let completionType = null;
                // 可能字段：completion_flag / completion_type / completion_flag_text
                if (d.completion_flag) completionType = String(d.completion_flag).toLowerCase();
                else if (d.completion_type) completionType = String(d.completion_type).toLowerCase();
                else if (d.completion_flag_text) {
                    // 若文本中包含“分钟”，视为 time
                    completionType = /分钟/.test(String(d.completion_flag_text)) ? 'time' : 'other';
                } else if (d.transcript_index_type && d.transcript_index_type.duration != null) {
                    // 存在明确 duration 时倾向认为 time
                    completionType = 'time';
                }
                    return {
                        duration: d.duration != null ? d.duration : null,
                        completionType: completionType || 'other'
                    };
            }
        } catch (e) {
            // 忽略错误
        }
            return { duration: null, completionType: 'other' };
    }

// 解析课程标题：优先 info，其次 REST，最后我的课程列表
async function resolveCourseTitle(courseId, info, headers) {
    if (info) {
        const t = info.course_title || info.title || info.name || info.course_name;
        if (t) return t;
    }
    try {
        const rest = await httpGet(`${CONFIG.courseInfoUrlRest}${courseId}`, headers);
        if (rest && rest.code === 200 && rest.data) {
            const d = rest.data;
            const t2 = d.course_title || d.title || d.name || d.course_name;
            if (t2) return t2;
        }
    } catch {}
    try {
        const list = await httpGet(CONFIG.myCourseListUrl, headers);
        if (list && list.code === 200 && list.data && Array.isArray(list.data.items)) {
            const found = list.data.items.find(x => String(x.course_id || x.id) === String(courseId));
            if (found) {
                const t3 = found.course_title || found.title || found.name || found.course_name;
                if (t3) return t3;
            }
        }
    } catch {}
    return String(courseId);
}


async function doSignIn(courseId, lat, lon, address, headers, typeStr, courseTitle) {
    const body = {
        course_id: courseId,
        sign_address: {
            address: address,
            latitude: lat,
            longitude: lon
        }
    };

    const options = {
        url: CONFIG.signInUrl,
        headers: headers,
        body: JSON.stringify(body)
    };

    try {
        const result = await httpPost(options);
        console.log(`📝 ${typeStr}结果: ${JSON.stringify(result)}`);
        if (result && result.code === 200) {
            console.log(`✅ ${typeStr}成功！`);
            $.msg($.name, `${typeStr}成功`, `课程: ${courseTitle}\n位置: ${address}`);
        } else {
            console.log(`❌ ${typeStr}失败！`);
            let failReason = "未知错误";
            if (result) {
                if (typeof result === 'object') {
                    failReason = result.msg || result.message || result.error || JSON.stringify(result);
                } else {
                    failReason = String(result);
                }
            }
            $.msg($.name, `${typeStr}失败`, `课程: ${courseTitle}\n原因: ${failReason}`);
        }
    } catch (e) {
        console.error(`❌ ${typeStr}请求异常: ${e}`);
        const errStr = (e && e.message) ? e.message : String(e);
        $.msg($.name, `${typeStr}异常`, `课程: ${courseTitle}\n错误: ${errStr}`);
    }
}

async function executeSign(courseId, info, headers, typeStr, courseTitle, options = {}) {
    const skipDelay = !!(options && options.skipDelay);
    console.log(`🚀 开始执行${typeStr}...`);
    // 获取位置信息
    if (info.sign_in_address && info.sign_in_address.length > 0) {
        const target = info.sign_in_address[0]; // 取第一个位置
        const range = parseFloat(target.range) || 200;
        const baseLat = parseFloat(target.latitude);
        const baseLon = parseFloat(target.longitude);
        const address = target.address;

        // 生成随机坐标
        const { lat, lon } = getRandomCoordinate(baseLat, baseLon, range);
        console.log(`📍 目标位置: ${address} (${baseLat}, ${baseLon}), 范围: ${range}m`);
        console.log(`🎲 随机位置: (${lat}, ${lon})`);

        // 执行签到
        await doSignIn(courseId, lat, lon, address, headers, typeStr, courseTitle);

        // 增加随机延时，避免并发过快（单 ID 时跳过等待）
        if (!skipDelay) {
            const delay = Math.floor(Math.random() * 15000) + 15000; // 15-30秒
            console.log(`⏳ 等待 ${(delay / 1000).toFixed(1)} 秒...`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    } else {
        console.log("❌ 未找到签到位置信息");
        $.msg($.name, `${typeStr}失败`, `课程: ${courseTitle}\n原因: 未找到位置信息`);
    }
}

// 判断是否处于某个时间窗口（signIn/signOut）
function isInWindow(info, kind) {
    const now = new Date();
    if (kind === 'signOut') {
        if (info.sign_out_start_time && info.sign_out_end_time) {
            const soStart = new Date(String(info.sign_out_start_time).replace(/-/g, '/'));
            const soEnd = new Date(String(info.sign_out_end_time).replace(/-/g, '/'));
            return now >= soStart && now <= soEnd;
        }
        return false;
    }
    if (kind === 'signIn') {
        if (info.sign_in_start_time && info.sign_in_end_time) {
            const siStart = new Date(String(info.sign_in_start_time).replace(/-/g, '/'));
            const siEnd = new Date(String(info.sign_in_end_time).replace(/-/g, '/'));
            return now >= siStart && now <= siEnd;
        }
        return false;
    }
    return false;
}

// 生成范围内随机坐标
function getRandomCoordinate(lat, lon, rangeMeters) {
    // 1度纬度 ≈ 111km = 111000m
    // 1度经度 ≈ 111km * cos(lat)
    
    // 稍微缩小一点范围，确保在圈内
    const safeRange = rangeMeters * 0.6; 
    
    const r = safeRange / 111000; // 转换为度数的大致半径
    const u = Math.random();
    const v = Math.random();
    const w = r * Math.sqrt(u);
    const t = 2 * Math.PI * v;
    const x = w * Math.cos(t);
    const y = w * Math.sin(t);

    // x 是纬度偏移，y 是经度偏移（需要修正）
    const newLat = lat + x;
    const newLon = lon + y / Math.cos(lat * Math.PI / 180);

    return { lat: newLat, lon: newLon };
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

// 新增：根据课程详情与当前时间判断可签类型（默认优先签退）
function decideSignType(info, statusHint) {
    const now = new Date();
    let canSign = false;
    let typeStr = "";

    // 判断在签退窗口
    if (info.sign_out_start_time && info.sign_out_end_time) {
        const soStart = new Date(info.sign_out_start_time.replace(/-/g, '/'));
        const soEnd = new Date(info.sign_out_end_time.replace(/-/g, '/'));
        if (now >= soStart && now <= soEnd) {
            canSign = true;
            typeStr = "签退";
        }
    }

    // 若不在签退窗口，再判断签到窗口
    if (!canSign && info.sign_in_start_time && info.sign_in_end_time) {
        const siStart = new Date(info.sign_in_start_time.replace(/-/g, '/'));
        const siEnd = new Date(info.sign_in_end_time.replace(/-/g, '/'));
        if (now >= siStart && now <= siEnd) {
            canSign = true;
            typeStr = "签到";
        }
    }

    // 如果传入了状态提示（0待签到/1待签退），并且两个窗口都可，仍旧优先签退
    if (canSign && typeStr === "签到" && statusHint === 1) {
        // 已在签退状态优先级，保持签退优先
        // 如果签退窗口同时也在，则已在上方优先返回“签退”
    }

    return { canSign, typeStr };
}
