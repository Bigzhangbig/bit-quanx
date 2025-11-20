/*
 * 脚本名称：北理工第二课堂监控
 * 作者：Gemini for User
 * * [rewrite_local]
 * ^https:\/\/qcbldekt\.bit\.edu\.cn\/api\/course\/list url script-request-header https://raw.githubusercontent.com/yourname/script/master/bit_monitor.js
 * * [task_local]
 * 30 8-22/2 * * * https://raw.githubusercontent.com/yourname/script/master/bit_monitor.js, tag=第二课堂监控, img-url=https://raw.githubusercontent.com/Orz-3/mini/master/Color/BIT.png, enabled=true
 * */

const $ = new Env("北理工第二课堂");

// 配置项
const CONFIG = {
    // BoxJS/Store Keys
    tokenKey: "bit_sc_token",
    headersKey: "bit_sc_headers",
    cacheKey: "bit_sc_cache", // 用来存上一次的最新课程ID
    
    // 栏目ID映射 (根据你的截图推断)
    categories: [
        { id: 1, name: "理想信念" },
        { id: 2, name: "科学素养" },
        { id: 3, name: "社会贡献" },
        { id: 4, name: "团队协作" },
        { id: 5, name: "文化互鉴" },
        { id: 6, name: "健康生活" }
    ]
};

// 脚本入口
(async () => {
    if (typeof $request !== "undefined") {
        await getCookie();
    } else {
        await checkCourses();
    }
})().finally(() => $.done());

// 1. 获取并存储 Token (运行在 Rewrite 模式)
async function getCookie() {
    if ($request.headers) {
        const auth = $request.headers['Authorization'] || $request.headers['authorization'];
        // 保存 Authorization
        if (auth) {
            $.setdata(auth, CONFIG.tokenKey);
            
            // 保存其他头部信息 (User-Agent, Referer等) 以伪装请求
            const headersToSave = JSON.stringify({
                'User-Agent': $request.headers['User-Agent'] || $request.headers['user-agent'],
                'Referer': $request.headers['Referer'] || $request.headers['referer'],
                'Host': 'qcbldekt.bit.edu.cn',
                'Connection': 'keep-alive',
                'Accept-Encoding': 'gzip,compress,br,deflate'
            });
            $.setdata(headersToSave, CONFIG.headersKey);
            
            $.msg($.name, "获取Token成功", "请去运行任务脚本测试");
        }
    }
}

// 2. 监控逻辑 (运行在 Task 模式)
async function checkCourses() {
    const token = $.getdata(CONFIG.tokenKey);
    const savedHeaders = $.getdata(CONFIG.headersKey);
    
    if (!token) {
        $.msg($.name, "❌ 未找到 Token", "请先进入微信小程序“第二课堂”刷新任意列表以获取 Token。");
        return;
    }

    const headers = JSON.parse(savedHeaders || "{}");
    headers['Authorization'] = token;
    headers['Content-Type'] = 'application/json;charset=utf-8';

    // 读取上一次的缓存数据
    let cache = JSON.parse($.getdata(CONFIG.cacheKey) || "{}");
    let notifyMsg = "";
    let hasUpdate = false;

    // 遍历所有栏目
    for (let cat of CONFIG.categories) {
        // 构造URL：获取最新的一页数据
        // sign_status=2 表示“进行中”，如果想监控所有状态，可调整参数
        // transcript_index_type_id=0 固定
        const url = `https://qcbldekt.bit.edu.cn/api/course/list?page=1&limit=5&sign_status=2&transcript_index_id=${cat.id}&transcript_index_type_id=0`;
        
        try {
            const data = await httpGet(url, headers);
            
            if (data && data.code === 200 && data.data && data.data.length > 0) {
                // 获取该栏目最新的课程
                const latestCourse = data.data[0];
                const lastId = cache[cat.id]; // 上次记录的ID

                // 比较 ID，如果不一致，说明有更新
                if (latestCourse.id !== lastId) {
                    hasUpdate = true;
                    const time = latestCourse.sign_in_start_time || "未知时间";
                    const place = latestCourse.time_place ? latestCourse.time_place.replace(/\n/g, " ") : "未知地点";
                    
                    notifyMsg += `【${cat.name}】🆕 ${latestCourse.transcript_name}\n⏰ ${time}\n📍 ${place}\n\n`;
                    
                    // 更新缓存
                    cache[cat.id] = latestCourse.id;
                }
            }
        } catch (e) {
            console.log(`❌ 获取 ${cat.name} 失败: ${e}`);
        }
        
        // 稍微延迟一下，避免并发过高封IP
        await new Promise(r => setTimeout(r, 1000));
    }

    // 如果有更新，发送通知并保存新缓存
    if (hasUpdate) {
        $.msg($.name, "发现新课程活动！", notifyMsg);
        $.setdata(JSON.stringify(cache), CONFIG.cacheKey);
    } else {
        console.log("暂无新课程更新");
    }
}

// 封装请求
function httpGet(url, headers) {
    return new Promise((resolve, reject) => {
        $.get({ url, headers }, (err, resp, data) => {
            if (err) reject(err);
            else {
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

function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { this.isQuanX && $notify(e, s, i, r) } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done() { } }(t, e) }
