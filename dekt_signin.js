/*
 * 脚本名称：北理工第二课堂签到
 * 作者：Gemini for User
 * 描述：自动检查已报名课程并进行签到/签退。
 * 
 * [task_local]
 * # 签到脚本 (默认关闭，需手动运行或开启)
 * 0 8-22/1 * * * https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/dekt_signin.js, tag=第二课堂签到, enabled=false
 */

const $ = new Env("北理工第二课堂签到");

console.log("加载脚本: 北理工第二课堂签到");

// 配置项
const CONFIG = {
    tokenKey: "bit_sc_token",
    headersKey: "bit_sc_headers",
    // 新增 BoxJS 开关与运行时ID配置键
    autoSignAllKey: "bit_sc_auto_sign_all",
    runtimeIdsKey: "bit_sc_runtime_sign_ids",
    
    // API 接口
    listUrl: "https://qcbldekt.bit.edu.cn/api/transcript/course/signIn/list?page=1&limit=10&type=1",
    infoUrl: "https://qcbldekt.bit.edu.cn/api/transcript/checkIn/info",
    signInUrl: "https://qcbldekt.bit.edu.cn/api/transcript/signIn",
    // 新增：课程详情（含时长）REST接口
    courseInfoUrlRest: "https://qcbldekt.bit.edu.cn/api/course/info/",
    // 新增：我的课程列表（兜底时长来源）
    myCourseListUrl: "https://qcbldekt.bit.edu.cn/api/course/list/my?page=1&limit=200"
};

(async () => {
    try {
        await checkAndSignIn();
    } catch (e) {
        console.log(`❌ 脚本运行异常: ${e}`);
    } finally {
        $.done();
    }
})();

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
            const duration = meta ? meta.duration : null;
            const siWin = isInWindow(info, 'signIn');
            const soWin = isInWindow(info, 'signOut');
            // 日志始终输出（先签到再签退），非 time 也输出并标注跳过
            console.log(`===== 课程 ${course.course_id} | ${title} =====`);
            console.log(`时长: ${duration != null ? duration : '未知'}${meta && meta.completionType !== 'time' ? '（非time类型，跳过执行）' : ''}`);
            console.log(`签到窗口: ${siWin ? '是' : '否'}${info.sign_in_start_time ? ` (${info.sign_in_start_time} - ${info.sign_in_end_time})` : ''}`);
            console.log(`签退窗口: ${soWin ? '是' : '否'}${info.sign_out_start_time ? ` (${info.sign_out_start_time} - ${info.sign_out_end_time})` : ''}`);
            console.log(`----------------------------------------------`);
            // 仅在开启 autoSignAll 且为 time 类型时执行
            if (autoSignAll && meta && meta.completionType === 'time') {
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
    } else if (targetIds.length > 0) {
        // 仅对指定 ID 尝试签到
        for (const tId of targetIds) {
            const info = await getCourseInfo(tId, headers);
            if (!info) continue;
            const meta = await getCourseMeta(tId, headers);
            const title = info.course_title || String(tId);
            const duration = meta ? meta.duration : null;
            const soWin = isInWindow(info, 'signOut');
            const siWin = isInWindow(info, 'signIn');
            // 日志分割线 + 先签到后签退
            console.log(`===== 课程 ${tId} | ${title} =====`);
            console.log(`时长: ${duration != null ? duration : '未知'}${meta && meta.completionType !== 'time' ? '（非time类型，跳过执行）' : ''}`);
            console.log(`签到窗口: ${siWin ? '是' : '否'}${info.sign_in_start_time ? ` (${info.sign_in_start_time} - ${info.sign_in_end_time})` : ''}`);
            console.log(`签退窗口: ${soWin ? '是' : '否'}${info.sign_out_start_time ? ` (${info.sign_out_start_time} - ${info.sign_out_end_time})` : ''}`);
            console.log(`----------------------------------------------`);
            if (meta && meta.completionType === 'time') {
                if (siWin) {
                    $.msg($.name, `处于签到时间窗口`, `课程: ${title}`);
                    await executeSign(tId, info, headers, '签到', title);
                }
                if (soWin) {
                    $.msg($.name, `处于签退时间窗口`, `课程: ${title}`);
                    await executeSign(tId, info, headers, '签退', title);
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
                    duration: d.duration != null ? d.duration : await getCourseDuration(courseId, headers),
                    completionType: completionType || 'other'
                };
            }
        } catch (e) {
            // 忽略错误
        }
        // 兜底：从我的课程列表判断（若有 duration 则认为 time）
        try {
            const list = await httpGet(CONFIG.myCourseListUrl, headers);
            if (list && list.code === 200 && list.data && Array.isArray(list.data.items)) {
                const found = list.data.items.find(x => String(x.course_id || x.id) === String(courseId));
                if (found) {
                    return {
                        duration: found.duration != null ? found.duration : null,
                        completionType: found.duration != null ? 'time' : 'other'
                    };
                }
            }
        } catch (e) {}
        return { duration: null, completionType: 'other' };
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

async function executeSign(courseId, info, headers, typeStr, courseTitle) {
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

        // 增加随机延时，避免并发过快
        const delay = Math.floor(Math.random() * 15000) + 15000; // 15-30秒
        console.log(`⏳ 等待 ${(delay / 1000).toFixed(1)} 秒...`);
        await new Promise(resolve => setTimeout(resolve, delay));
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
