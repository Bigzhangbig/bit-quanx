const fs = require('fs');
const dotenv = require('dotenv');

if (fs.existsSync('.env')) {
  const envConfig = dotenv.parse(fs.readFileSync('.env'));
  for (const k in envConfig) {
    process.env[k] = envConfig[k];
  }
}

const token = process.env.bit_sc_token || process.env.dekt_token;

if (!token) {
  console.error('Token not found (bit_sc_token or dekt_token)');
  process.exit(1);
}

const headers = {
  'Authorization': token.startsWith('Bearer ') ? token : 'Bearer ' + token,
  'Accept': 'application/json, text/plain, */*',
  'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.48(0x18003029) NetType/WIFI Language/zh_CN'
};

const baseUrl = 'https://qcbldekt.bit.edu.cn';

async function fetchData() {
  try {
    const listRes = await fetch(baseUrl + '/api/course/list/my?page=1&limit=20', { headers });
    const listData = await listRes.json();
    
    if (!listData.data || !listData.data.items) {
      console.error('Failed to fetch course list:', listData);
      return;
    }

    const items = listData.data.items;
    const summary = [];
    const stats = {};

    for (let i = 0; i < Math.min(items.length, 5); i++) {
        const item = items[i];
        const detailRes = await fetch(baseUrl + '/api/transcript/checkIn/info?course_id=' + item.course_id, { headers });
        const detailData = await detailRes.json();
        const detail = detailData.data || {};

        const info = {
            course_id: item.course_id,
            title: item.title,
            status: item.status,
            status_label: item.status_label,
            sign_status: item.sign_status,
            sign_status_label: item.sign_status_label,
            completion_flag_text: item.completion_flag_text,
            sign_in_start_time: item.sign_in_start_time,
            sign_in_end_time: item.sign_in_end_time,
            sign_out_start_time: item.sign_out_start_time,
            sign_out_end_time: item.sign_out_end_time,
            checkIn_status: detail.status,
            checkIn_status_label: detail.status_label,
            sign_in_time: detail.sign_in_time,
            sign_out_time: detail.sign_out_time,
            complate_time: detail.complate_time
        };
        summary.push(info);
    }

    console.log('--- Course Details (First 5) ---');
    summary.forEach(s => console.log(JSON.stringify(s, null, 2)));

    items.forEach(item => {
        const label = item.sign_status_label || item.status_label || 'Unknown';
        stats[label] = (stats[label] || 0) + 1;
    });

    console.log('
--- Statistics (Grouped by sign_status_label/status_label) ---');
    console.log(stats);

  } catch (error) {
    console.error('Error:', error);
  }
}

fetchData();
