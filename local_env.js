/*
 * 脚本名称：本地环境模拟模块
 * 作者：Gemini for User
 * 描述：为本地 Node.js 环境提供 Quantumult X Env 类的模拟实现。
 *       用于本地调试脚本（local_*.js）加载使用。
 * 
 * 用法：
 *   const Env = require('./local_env');
 *   const $ = new Env('脚本名称');
 * 
 * 功能：
 * - getdata(key)：从 .env 文件读取配置
 * - setdata(val, key)：将配置写入 .env 文件
 * - msg(title, subtitle, body)：在控制台输出通知
 * - get(options, callback)：发起 HTTPS GET 请求
 * - post(options, callback)：发起 HTTPS POST 请求
 * - done(val)：标记脚本执行完成
 * 
 * 注意：
 * - 配置文件路径为项目根目录下的 .env
 * - 自动处理 gzip/deflate/br 压缩响应
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const zlib = require('zlib');

class Env {
    constructor(name) {
        this.name = name;
        this.dataFile = path.join(__dirname, '.env');
        this.data = this.loadData();
    }

    loadData() {
        if (fs.existsSync(this.dataFile)) {
            try {
                const content = fs.readFileSync(this.dataFile, 'utf8');
                const result = {};
                content.split('\n').forEach(line => {
                    line = line.trim();
                    if (line && !line.startsWith('#')) {
                        const parts = line.split('=');
                        const key = parts[0].trim();
                        const val = parts.slice(1).join('=').trim();
                        // Remove quotes if present
                        if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
                            result[key] = val.slice(1, -1);
                        } else {
                            result[key] = val;
                        }
                    }
                });
                return result;
            } catch (e) {
                console.error("Error reading .env:", e);
                return {};
            }
        }
        return {};
    }

    saveData() {
        const content = Object.entries(this.data)
            .map(([key, val]) => `${key}=${val}`)
            .join('\n');
        fs.writeFileSync(this.dataFile, content);
    }

    getdata(key) {
        return this.data[key];
    }

    setdata(val, key) {
        this.data[key] = val;
        this.saveData();
    }

    msg(title, subtitle, body) {
        console.log(`\n=== ${title} ===\n${subtitle || ''}\n${body || ''}\n==================\n`);
    }

    log(msg) {
        console.log(`[${this.name}] ${msg}`);
    }

    get(options, callback) {
        this.request('GET', options, callback);
    }

    post(options, callback) {
        this.request('POST', options, callback);
    }

    request(method, options, callback) {
        let urlStr = typeof options === 'string' ? options : options.url;
        let opts = typeof options === 'string' ? {} : options;
        
        if (!urlStr) {
            return callback('No URL specified', null, null);
        }

        try {
            const url = new URL(urlStr);
            const reqOpts = {
                method: method,
                hostname: url.hostname,
                port: url.port || 443,
                path: url.pathname + url.search,
                headers: opts.headers || {}
            };

            // Handle body
            let body = opts.body;
            if (body && typeof body === 'object') {
                // If body is object and not buffer, assume JSON or form? 
                // Usually QX scripts pass stringified body.
                // If it's an object, let's try to stringify it if content-type is json
                if (reqOpts.headers['Content-Type'] && reqOpts.headers['Content-Type'].includes('application/json')) {
                     body = JSON.stringify(body);
                }
            }

            if (body) {
                reqOpts.headers['Content-Length'] = Buffer.byteLength(body);
            }

            const req = https.request(reqOpts, (res) => {
                const encoding = res.headers['content-encoding'];
                let stream = res;
                
                // Handle compression
                if (encoding === 'gzip') {
                    stream = res.pipe(zlib.createGunzip());
                } else if (encoding === 'deflate') {
                    stream = res.pipe(zlib.createInflate());
                } else if (encoding === 'br') {
                    stream = res.pipe(zlib.createBrotliDecompress());
                }

                let data = '';
                // Set encoding to utf8 to get string instead of buffer
                stream.setEncoding('utf8');
                
                stream.on('data', (chunk) => data += chunk);
                stream.on('end', () => {
                    callback(null, res, data);
                });
            });

            req.on('error', (e) => {
                callback(e, null, null);
            });

            if (body) {
                req.write(body);
            }
            req.end();
        } catch (e) {
            callback(e, null, null);
        }
    }

    done(val) {
        console.log(`\n[${this.name}] Execution finished.`);
    }
}

module.exports = Env;
