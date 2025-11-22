/*
 * 脚本名称：北理工第二课堂签到
 * 描述：自动检查已报名课程并进行签到/签退
 * 作者：Gemini for User
 * 
 * [task_local]
 * # 签到脚本 (默认关闭，需手动运行或开启)
 * 0 8-22/1 * * * https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/bit_signin.js, tag=第二课堂签到, enabled=false
 */

const $ = new Env("北理工第二课堂签到");

console.log("加载脚本: 北理工第二课堂签到");

// 配置项
const CONFIG = {
    tokenKey: "bit_sc_token",
    headersKey: "bit_sc_headers",
    
    // API 接口
    listUrl: "https://qcbldekt.bit.edu.cn/api/transcript/course/signIn/list?page=1&limit=10&type=1",
    infoUrl: "https://qcbldekt.bit.edu.cn/api/transcript/checkIn/info",
    signInUrl: "https://qcbldekt.bit.edu.cn/api/transcript/signIn"
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
    // 确保 Authorization 格式正确
    headers['Authorization'] = token.startsWith("Bearer") ? token : `Bearer ${token}`;
    headers['Content-Type'] = 'application/json;charset=utf-8';
    headers['Host'] = 'qcbldekt.bit.edu.cn';
    // 移除可能导致问题的 Content-Length (QX 会自动处理)
    if (headers['Content-Length']) delete headers['Content-Length'];

    console.log("🔍 正在获取已报名课程列表...");
    
    try {
        const listData = await httpGet(CONFIG.listUrl, headers);
        if (!listData || listData.code !== 200) {
            console.log(`❌ 获取列表失败: ${JSON.stringify(listData)}`);
            $.msg($.name, "获取课程列表失败", listData ? listData.msg : "未知错误");
            return;
        }

        const courses = listData.data.items || [];
        console.log(`📋 找到 ${courses.length} 个已报名课程`);

        if (courses.length === 0) {
            console.log("暂无需要签到的课程");
            return;
        }

        for (const course of courses) {
            console.log(`\nChecking Course: [${course.course_id}] ${course.course_title}`);
            console.log(`Status: ${course.status_label} (${course.status})`);
            
            // status: 0 (待签到), 1 (待签退), 2 (补卡), 3 (待完成), 4 (待审核)
            let potentialAction = false;
            if (course.status === 0 || course.status === 1) {
                potentialAction = true;
            }

            if (!potentialAction) {
                console.log("非签到/签退状态，跳过");
                continue;
            }

            // 获取详细信息
            const info = await getCourseInfo(course.course_id, headers);
            if (!info) continue;

            const now = new Date();
            let canSign = false;
            let typeStr = "";

            if (course.status === 0) {
                // 待签到
                const start = new Date(info.sign_in_start_time.replace(/-/g, '/'));
                const end = new Date(info.sign_in_end_time.replace(/-/g, '/'));
                if (now >= start && now <= end) {
                    canSign = true;
                    typeStr = "签到";
                } else {
                    console.log(`⏳ 当前不在签到时间范围内 (${info.sign_in_start_time} - ${info.sign_in_end_time})`);
                }
            } else if (course.status === 1) {
                // 待签退
                const start = new Date(info.sign_out_start_time.replace(/-/g, '/'));
                const end = new Date(info.sign_out_end_time.replace(/-/g, '/'));
                if (now >= start && now <= end) {
                    canSign = true;
                    typeStr = "签退";
                } else {
                    console.log(`⏳ 当前不在签退时间范围内 (${info.sign_out_start_time} - ${info.sign_out_end_time})`);
                }
            }

            if (canSign) {
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
                    await doSignIn(course.course_id, lat, lon, address, headers, typeStr, course.course_title);
                } else {
                    console.log("❌ 未找到签到位置信息");
                    $.msg($.name, `${typeStr}失败`, `课程: ${course.course_title}\n原因: 未找到位置信息`);
                }
            }
        }

    } catch (e) {
        console.error("❌ 运行异常:", e);
    }
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
        if (result.code === 200) {
            console.log(`✅ ${typeStr}成功！`);
            $.msg($.name, `${typeStr}成功`, `课程: ${courseTitle}\n位置: ${address}`);
        } else {
            console.log(`❌ ${typeStr}失败！`);
            $.msg($.name, `${typeStr}失败`, `课程: ${courseTitle}\n原因: ${result.msg || "未知错误"}`);
        }
    } catch (e) {
        console.error(`❌ ${typeStr}请求异常: ${e}`);
        $.msg($.name, `${typeStr}异常`, `课程: ${courseTitle}\n错误: ${e}`);
    }
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
