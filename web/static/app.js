/* ==========================================================================
   DouyinLiveRecorder 可视化控制台 - 前端逻辑
   无任何第三方依赖（原生 JS）
   ========================================================================== */
'use strict';

/* ------------------------------------------------------------------ 图标 */
const ICONS = {
  dashboard: '<path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>',
  link: '<path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z"/>',
  video: '<path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/>',
  bell: '<path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5S10.5 3.17 10.5 4v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/>',
  cookie: '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10c0-.4-.02-.79-.07-1.18-.9.75-2.06 1.2-3.33 1.2-1.2 0-2.3-.4-3.18-1.08-.9.68-2 1.08-3.2 1.08C9.1 12.02 7 9.92 7 7.32c0-.67.14-1.3.4-1.88C6.2 5.9 5 7.8 5 10c0 .55-.45 1-1 1s-1-.45-1-1c0-4.42 3.58-8 8-8 .28 0 .55.02.82.05C11.6 2.02 11.8 2 12 2zm3 5.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zM8.5 13a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm5 3.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z"/>',
  user: '<path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>',
  key: '<path d="M12.65 10C11.83 7.67 9.61 6 7 6c-3.31 0-6 2.69-6 6s2.69 6 6 6c2.61 0 4.83-1.67 5.65-4H17v4h4v-4h2v-4H12.65zM7 14c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z"/>',
  terminal: '<path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-8 11H8v-1.5h4V15zm4.5-5.5L14 12l2.5 2.5-1.06 1.06L12.38 12l3.06-3.06L16.5 9.5z"/>',
  folder: '<path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>',
  play: '<path d="M8 5v14l11-7z"/>',
  stop: '<path d="M6 6h12v12H6z"/>',
  refresh: '<path d="M17.65 6.35A7.96 7.96 0 0 0 12 4a8 8 0 1 0 7.73 10h-2.08A6 6 0 1 1 12 6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>',
  save: '<path d="M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z"/>',
  trash: '<path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>',
  plus: '<path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>',
  search: '<path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>',
  moon: '<path d="M12 3a9 9 0 1 0 9 9c0-.46-.04-.92-.1-1.36A5.39 5.39 0 0 1 16.5 13 5.5 5.5 0 0 1 11 7.5c0-1.62.7-3.07 1.82-4.08-.27-.03-.54-.05-.82-.05z"/>',
  sun: '<path d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2v-2H2v2zm18 0h2v-2h-2v2zM11 2v2h2V2h-2zm0 18v2h2v-2h-2zM5.99 4.58L4.58 5.99l1.41 1.41 1.41-1.41-1.41-1.41zm12.02 12.02l-1.41 1.41 1.41 1.41 1.41-1.41-1.41-1.41zM18.01 4.58l-1.41 1.41 1.41 1.41 1.41-1.41-1.41-1.41zM5.99 19.42l-1.41-1.41-1.41 1.41 1.41 1.41 1.41-1.41z"/>',
  github: '<path d="M12 2A10 10 0 0 0 8.84 21.5c.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.89 1.52 2.34 1.08 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.65 0 0 .84-.27 2.75 1.02a9.6 9.6 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02.55 1.38.2 2.4.1 2.65.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85V21c0 .27.16.59.67.5A10 10 0 0 0 12 2z"/>',
  menu: '<path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/>',
  close: '<path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>',
  external: '<path d="M19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>',
  download: '<path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>',
  upload: '<path d="M9 16h6v-6h4l-7-7-7 7h4v6zm-4 2h14v2H5v-2z"/>',
  check: '<path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>',
  ban: '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM4 12c0-4.42 3.58-8 8-8 1.85 0 3.55.63 4.9 1.69L5.69 16.9A7.9 7.9 0 0 1 4 12zm8 8c-1.85 0-3.55-.63-4.9-1.69L18.31 7.1A7.9 7.9 0 0 1 20 12c0 4.42-3.58 8-8 8z"/>',
  pause: '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>',
  up: '<path d="M4 12l1.41 1.41L11 7.83V20h2V7.83l5.58 5.59L20 12l-8-8-8 8z"/>',
  file: '<path d="M6 2c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6H6zm7 7V3.5L18.5 9H13z"/>',
  image: '<path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>',
  merge: '<path d="M17 20.41L18.41 19 15 15.59 13.59 17 17 20.41zM7.5 8H11v5.59L5.59 19 7 20.41l6-6V8h3.5L12 3.5 7.5 8z"/>',
  crop: '<path d="M17 15h2V7c0-1.1-.9-2-2-2h-8v2h8v8zM7 17V1H5v4H1v2h4v10c0 1.1.9 2 2 2h10v4h2v-4h4v-2H7z"/>',
};

function icon(name, size = 16) {
  const path = ICONS[name] || ICONS.file;
  // 显式给出 width/height：否则在没有 CSS 约束的地方（表格单元格等）SVG 会撑满容器
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="currentColor" aria-hidden="true">${path}</svg>`;
}

/* ------------------------------------------------------------------ 文案 */
const I18N = {
  zh: {
    appName: '直播录制控制台', navDashboard: '概览', navUrls: '直播间地址', navSettingsGroup: '参数设置',
    navRecording: '录制设置', navPush: '推送配置', navCookie: 'Cookie', navAccount: '账号密码',
    navAuth: '授权令牌', navRuntimeGroup: '运行', navLogs: '实时日志', navFiles: '录制文件',
    start: '启动录制', stop: '停止', recheck: '重新检测', viewAll: '查看全部',
    statMonitoring: '监测中的直播间', statRecording: '正在录制', statErrors: '瞬时错误数', statDisk: '磁盘剩余',
    processCard: '录制进程', envCard: '运行环境', recentFiles: '最近录制的文件',
    kvPid: '进程 ID', kvUptime: '运行时长', kvQuality: '当前画质', kvFormat: '输出格式', kvExit: '上次退出码',
    kvPython: 'Python 解释器', kvDeps: '依赖包', kvFfmpeg: 'ffmpeg', kvSavePath: '录制保存路径', kvRoot: '项目目录',
    filterAll: '全部', filterEnabled: '已启用', filterDisabled: '已停用', filterInvalid: '地址异常',
    enableAll: '全部启用', disableAll: '全部停用', deleteSelected: '删除选中', add: '添加',
    enable: '启用', disable: '停用',
    bulkImport: '批量导入', useDefault: '默认画质', colStatus: '状态', colQuality: '画质', colUrl: '直播间地址',
    colName: '主播名', colActions: '操作', colFileName: '名称', colSize: '大小', colTime: '修改时间',
    save: '保存设置', discard: '放弃', logLive: '实时输出', logFile: '日志文件', pause: '暂停',
    clear: '清空', autoScroll: '自动滚动', recursive: '包含子目录', openFolder: '打开文件夹',
    statusRunning: '录制中', statusStopped: '未运行', notRunning: '未运行',
    urlsHint: '提示：程序运行时修改此列表会在下一个循环周期自动生效；带有 # 前缀的行表示「已停用」，不会被录制。',
    noData: '暂无数据', loading: '加载中…', enabled: '已启用', disabled: '已停用', invalidUrl: '地址异常',
    confirmDelete: '确定删除选中的 {n} 条直播间地址吗？', confirmDeleteFiles: '确定删除选中的 {n} 个文件吗？此操作不可恢复。',
    confirmStop: '停止会强制结束录制进程（含 ffmpeg 子进程），正在写入的视频可能损坏。\n建议使用 ts 格式录制。确定要停止吗？',
    confirmDisableAll: '确定停用全部直播间地址吗？',
    saved: '已保存 {n} 项设置', saveFailed: '保存失败', startFailed: '启动失败',
    started: '录制进程已启动', stopFailed: '停止失败', stopped: '录制进程已停止',
    logConnected: '已连接', logDisconnected: '已断开', logConnecting: '连接中',
    emptyConsole: '暂无日志输出。启动录制后，这里的日志会实时刷新。',
    noEnabledUrl: '还没有启用的直播间地址，请先添加。',
    whichFolder: '选择录制保存目录', useThisFolder: '使用此目录',
    preview: '预览', download: '下载', upstream: '上级目录',
    goSaveDir: '录制目录',
    outsideRootHint: '当前目录不在「录制保存路径」内，只能浏览和下载，不能删除文件。',
    importTitle: '批量导入直播间地址', importHint: '每行一个地址，支持「画质, 地址, 主播名」格式；以 # 开头的行会被视为已停用。',
    importModeAppend: '追加到现有列表', importModeReplace: '替换现有列表', doImport: '导入',
    filterPlaceholder: '搜索参数', searchUrl: '搜索地址或主播名', searchFile: '搜索文件名',
    copied: '已复制', exitCode: '退出码',
    mergeSelected: '合并所选', to16x9: '转为16:9', mediaTasks: '媒体处理任务',
    hideJobs: '收起', showJobs: '展开', selectAllFiles: '全选',
    fileSelected: '已选 {n} 个', nothingSelected: '请先勾选要处理的文件',
    needTwoFiles: '请至少勾选 2 个文件才能合并',
    confirmMerge: '把选中的 {n} 个文件无损拼接为一个视频？\n按文件名顺序拼接（_000/_001…），输出到同一目录，不会重新编码。',
    confirmTo169: '把选中的 {n} 个文件裁掉黑边并转为 16:9？\n能无损时只改码流头、不重新编码；否则会重编码（较慢）。',
    mergeStarted: '已加入合并队列', convertStarted: '已加入 {n} 个转换任务',
    jobQueued: '排队中', jobRunning: '处理中', jobDone: '已完成', jobError: '失败', jobCancelled: '已取消',
    cancelJob: '取消', losslessBadge: '无损', reencodedBadge: '已重编码',
    jobsRunningHint: '{n} 个任务进行中',
  },
  en: {
    appName: 'Live Recorder Console', navDashboard: 'Overview', navUrls: 'Stream URLs',
    navSettingsGroup: 'Settings', navRecording: 'Recording', navPush: 'Notifications', navCookie: 'Cookies',
    navAccount: 'Accounts', navAuth: 'Authorization', navRuntimeGroup: 'Runtime', navLogs: 'Live log',
    navFiles: 'Recordings',
    start: 'Start', stop: 'Stop', recheck: 'Re-check', viewAll: 'View all',
    statMonitoring: 'Monitored rooms', statRecording: 'Recording', statErrors: 'Recent errors', statDisk: 'Disk free',
    processCard: 'Recorder process', envCard: 'Environment', recentFiles: 'Recent recordings',
    kvPid: 'PID', kvUptime: 'Uptime', kvQuality: 'Quality', kvFormat: 'Format', kvExit: 'Last exit code',
    kvPython: 'Python', kvDeps: 'Packages', kvFfmpeg: 'ffmpeg', kvSavePath: 'Save path', kvRoot: 'Project root',
    filterAll: 'All', filterEnabled: 'Enabled', filterDisabled: 'Disabled', filterInvalid: 'Invalid',
    enableAll: 'Enable all', disableAll: 'Disable all', deleteSelected: 'Delete selected', add: 'Add',
    enable: 'Enable', disable: 'Disable',
    bulkImport: 'Bulk import', useDefault: 'Default quality', colStatus: 'Status', colQuality: 'Quality',
    colUrl: 'Stream URL', colName: 'Streamer', colActions: 'Actions', colFileName: 'Name', colSize: 'Size',
    colTime: 'Modified',
    save: 'Save changes', discard: 'Discard', logLive: 'Live output', logFile: 'Log files', pause: 'Pause',
    clear: 'Clear', autoScroll: 'Auto scroll', recursive: 'Include subfolders', openFolder: 'Open folder',
    statusRunning: 'Recording', statusStopped: 'Stopped', notRunning: 'Stopped',
    urlsHint: 'Changes take effect automatically on the next poll loop while running. Lines prefixed with # are disabled.',
    noData: 'No data', loading: 'Loading…', enabled: 'Enabled', disabled: 'Disabled', invalidUrl: 'Invalid URL',
    confirmDelete: 'Delete the {n} selected stream URL(s)?', confirmDeleteFiles: 'Delete the {n} selected file(s)? This cannot be undone.',
    confirmStop: 'Stopping force-kills the recorder and its ffmpeg children; an in-progress file may be corrupted.\nUsing the ts format is recommended. Stop anyway?',
    confirmDisableAll: 'Disable all stream URLs?',
    saved: 'Saved {n} setting(s)', saveFailed: 'Save failed', startFailed: 'Failed to start',
    started: 'Recorder started', stopFailed: 'Failed to stop', stopped: 'Recorder stopped',
    logConnected: 'connected', logDisconnected: 'disconnected', logConnecting: 'connecting',
    emptyConsole: 'No output yet. Logs appear here in real time once recording starts.',
    noEnabledUrl: 'No enabled stream URL yet — add one first.',
    whichFolder: 'Choose save folder', useThisFolder: 'Use this folder',
    preview: 'Preview', download: 'Download', upstream: 'Parent folder',
    goSaveDir: 'Recordings',
    outsideRootHint: 'This folder is outside the configured save path — browsing and downloading only, deleting is disabled.',
    importTitle: 'Bulk import stream URLs', importHint: 'One URL per line; "quality, url, name" is supported. Lines starting with # are disabled.',
    importModeAppend: 'Append to list', importModeReplace: 'Replace list', doImport: 'Import',
    filterPlaceholder: 'Search options', searchUrl: 'Search URL or streamer', searchFile: 'Search filename',
    copied: 'Copied', exitCode: 'exit code',
    mergeSelected: 'Merge selected', to16x9: 'To 16:9', mediaTasks: 'Media tasks',
    hideJobs: 'Hide', showJobs: 'Show', selectAllFiles: 'Select all',
    fileSelected: '{n} selected', nothingSelected: 'Select a file first',
    needTwoFiles: 'Select at least 2 files to merge',
    confirmMerge: 'Merge the {n} selected files into one video without re-encoding?\nFiles are joined in filename order (_000/_001…), output goes next to the source.',
    confirmTo169: 'Crop the black bars and convert the {n} selected file(s) to 16:9?\nLossless when possible (bitstream header only); otherwise re-encodes (slower).',
    mergeStarted: 'Added to merge queue', convertStarted: 'Queued {n} conversion task(s)',
    jobQueued: 'Queued', jobRunning: 'Running', jobDone: 'Done', jobError: 'Failed', jobCancelled: 'Cancelled',
    cancelJob: 'Cancel', losslessBadge: 'lossless', reencodedBadge: 're-encoded',
    jobsRunningHint: '{n} task(s) running',
  },
};

/* ------------------------------------------------------------------ 状态 */
const S = {
  lang: localStorage.getItem('dlr_lang') || 'zh',
  theme: localStorage.getItem('dlr_theme') || '',
  page: 'dashboard',
  section: '录制设置',
  config: [],
  dirty: {},
  urls: [],
  urlSelected: new Set(),
  files: null,
  filePath: '',
  fileSelected: new Set(),
  mediaJobs: [],
  jobsTimer: null,
  jobsBusy: false,
  jobsHidden: false,
  jobsWasActive: false,
  state: null,
  logEntries: [],
  logIds: new Set(),
  lastLogId: 0,
  logSource: 'live',
  logPaused: false,
  logLevels: new Set(['OUT', 'INFO', 'WARNING', 'ERROR']),
  logSearch: '',
  es: null,
  esRetry: 0,
  fileFilter: '',
  urlFilter: 'all',
  urlSearch: '',
  cfgSearch: '',
  initialising: true,
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function t(key, vars) {
  const dict = I18N[S.lang] || I18N.zh;
  let text = dict[key] !== undefined ? dict[key] : (I18N.zh[key] !== undefined ? I18N.zh[key] : key);
  if (vars) {
    Object.keys(vars).forEach((k) => { text = text.replace(`{${k}}`, vars[k]); });
  }
  return text;
}

function esc(value) {
  return String(value === null || value === undefined ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function humanSize(bytes) {
  if (!bytes && bytes !== 0) return '-';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = Number(bytes);
  let i = 0;
  while (value >= 1024 && i < units.length - 1) { value /= 1024; i += 1; }
  return `${value.toFixed(value < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

function formatTime(epochSeconds) {
  if (!epochSeconds) return '-';
  const d = new Date(epochSeconds * 1000);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function formatDuration(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (d) return `${d}天 ${h}小时 ${m}分`;
  if (h) return `${h}小时 ${m}分 ${sec}秒`;
  if (m) return `${m}分 ${sec}秒`;
  return `${sec}秒`;
}

/* ------------------------------------------------------------------ 请求 */
async function api(path, options = {}) {
  const opts = Object.assign({ headers: {} }, options);
  if (opts.body !== undefined && typeof opts.body !== 'string') {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.body);
  }
  const resp = await fetch(path, opts);
  let data = null;
  const text = await resp.text();
  try { data = text ? JSON.parse(text) : {}; } catch (e) { data = { ok: false, error: text || 'invalid response' }; }
  if (!resp.ok || data.ok === false) {
    const err = new Error(data.error || `HTTP ${resp.status}`);
    err.payload = data;
    err.status = resp.status;
    throw err;
  }
  return data;
}

/* ------------------------------------------------------------------ UI 小工具 */
function toast(message, kind = '') {
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = message;
  $('#toasts').appendChild(el);
  setTimeout(() => {
    el.style.transition = 'opacity .3s, transform .3s';
    el.style.opacity = '0';
    el.style.transform = 'translateX(20px)';
    setTimeout(() => el.remove(), 320);
  }, kind === 'err' ? 6000 : 3200);
}

function openModal(title, bodyHtml, footHtml) {
  $('#modalTitle').textContent = title;
  $('#modalBody').innerHTML = bodyHtml;
  $('#modalFoot').innerHTML = footHtml || '';
  $('#modalMask').classList.remove('hidden');
}

function closeModal() {
  $('#modalMask').classList.add('hidden');
  $('#modalBody').innerHTML = '';
  $('#modalFoot').innerHTML = '';
}

function confirmDialog(message) {
  return new Promise((resolve) => {
    openModal(S.lang === 'en' ? 'Please confirm' : '请确认',
      `<p style="margin:0;white-space:pre-wrap">${esc(message)}</p>`,
      `<button class="btn ghost" id="cfmNo">${S.lang === 'en' ? 'Cancel' : '取消'}</button>
       <button class="btn danger" id="cfmYes">${S.lang === 'en' ? 'Confirm' : '确定'}</button>`);
    $('#cfmNo').onclick = () => { closeModal(); resolve(false); };
    $('#cfmYes').onclick = () => { closeModal(); resolve(true); };
  });
}

function applyIcons(root = document) {
  $$('[data-icon]', root).forEach((el) => { el.innerHTML = icon(el.dataset.icon); });
}

function applyI18n(root = document) {
  $$('[data-i18n]', root).forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.documentElement.lang = S.lang === 'en' ? 'en' : 'zh-CN';
}

/* ------------------------------------------------------------------ 导航 */
const PAGES = ['dashboard', 'urls', 'config', 'logs', 'files'];

function goto(page, section, fromHash) {
  if (!PAGES.includes(page)) page = 'dashboard';
  S.page = page;
  if (section) S.section = section;
  if (page === 'config' && !S.config.some((s) => s.name === S.section)) {
    S.section = S.config.length ? S.config[0].name : '录制设置';
  }
  if (!fromHash) syncHash();
  $$('.page').forEach((el) => el.classList.toggle('hidden', el.dataset.page !== page));
  $$('.nav-item').forEach((el) => {
    const match = el.dataset.page === page && (!el.dataset.section || el.dataset.section === S.section);
    el.classList.toggle('active', match);
  });
  const titles = {
    dashboard: t('navDashboard'), urls: t('navUrls'), logs: t('navLogs'), files: t('navFiles'),
    config: t(S.section === '录制设置' ? 'navRecording' : S.section === '推送配置' ? 'navPush'
      : S.section === 'Cookie' ? 'navCookie' : S.section === '账号密码' ? 'navAccount' : 'navAuth'),
  };
  $('#pageTitle').textContent = titles[page] || '';
  $('#sidebar').classList.remove('open');

  if (page === 'config') renderConfig();
  if (page === 'urls') renderUrls();
  if (page === 'logs') { renderConsole(); connectLogs(); } else { disconnectLogs(); }
  if (page === 'files') loadFiles(S.filePath, fromHash);
  if (page === 'dashboard') { refreshState(); loadRecentFiles(); }
}

/** 把当前页面/分组/目录写进地址栏，便于刷新保留、书签收藏、前进后退 */
function syncHash(options = {}) {
  let hash = `#/${S.page}`;
  if (S.page === 'config') hash += '/' + encodeURIComponent(S.section);
  if (S.page === 'files' && S.filePath) hash += '/' + encodeURIComponent(S.filePath);
  if (location.hash !== hash) {
    if (options.replace) history.replaceState(null, '', hash);
    else location.hash = hash;
  }
}

function routeFromHash() {
  const raw = decodeURIComponent((location.hash || '').replace(/^#\/?/, ''));
  const parts = raw.split('/');
  const page = PAGES.includes(parts[0]) ? parts[0] : 'dashboard';
  const second = parts.length > 1 ? parts[1] : '';
  return {
    page,
    // 目录里可能出现 /，所以 files 之后的整段都算路径
    section: page === 'config' && second ? second : undefined,
    path: page === 'files' && parts.length > 1 ? parts.slice(1).join('/') : undefined,
  };
}

/* ------------------------------------------------------------------ 概览 */
async function refreshState() {
  try {
    const data = await api('/api/state');
    S.state = data;
    const proc = data.process || {};
    const stats = proc.stats || {};
    $('#statMonitoring').textContent = stats.monitoring || 0;
    $('#statRecording').textContent = stats.recording_count || 0;
    $('#statErrors').textContent = stats.error_count || 0;
    const disk = (data.env && data.env.disk) || {};
    $('#statDisk').textContent = disk.ok ? `${disk.free_gb} GB` : '-';
    $('#statDiskPath').textContent = disk.path || '';

    const pill = $('#statusPill');
    pill.classList.remove('running', 'stopped', 'error');
    if (proc.running) {
      pill.classList.add('running');
      $('#statusText').textContent = t('statusRunning');
    } else if (!proc.user_stopped && proc.exit_code !== null && proc.exit_code !== undefined && proc.exit_code !== 0) {
      pill.classList.add('error');
      $('#statusText').textContent = `${t('statusStopped')} (${t('exitCode')} ${proc.exit_code})`;
    } else {
      pill.classList.add('stopped');
      $('#statusText').textContent = t('statusStopped');
    }

    $('#btnStart').disabled = !!proc.running;
    $('#btnStop').disabled = !proc.running;
    $('#btnRestart').disabled = !proc.running;
    // 未运行时把统计值变淡，表示这是「上次运行」的数值
    $('.grid.stats').classList.toggle('stale', !proc.running);

    $('#procTag').textContent = proc.running ? `PID ${proc.pid}` : t('notRunning');
    $('#procTag').className = proc.running ? 'tag ok' : 'tag';
    $('#kvPid').textContent = proc.pid || '-';
    $('#kvUptime').textContent = proc.running ? formatDuration(proc.uptime) : '-';
    $('#kvQuality').textContent = stats.quality || '-';
    $('#kvFormat').textContent = stats.video_format || '-';
    $('#kvExit').textContent = proc.exit_code === null || proc.exit_code === undefined ? '-' : proc.exit_code;

    const env = data.env || {};
    const deps = env.dependencies || {};
    const ff = env.ffmpeg || {};
    $('#kvPython').textContent = data.app.python;
    $('#kvPython').title = data.app.python;
    $('#kvDeps').innerHTML = deps.ok
      ? '<span class="tag ok">正常</span>'
      : `<span class="tag err">缺少 ${esc((deps.missing || []).join(', '))}</span>`;
    $('#kvFfmpeg').innerHTML = ff.ok
      ? `<span class="tag ok">${esc((ff.version || '').split(' ').slice(0, 3).join(' '))}</span>`
      : '<span class="tag err">未安装</span>';
    $('#kvSavePath').textContent = data.save_path;
    $('#kvSavePath').title = data.save_path;
    $('#kvRoot').textContent = data.app.project_root;
    $('#kvRoot').title = data.app.project_root;
    $('#brandVersion').textContent = data.app.version;

    const badge = $('#navUrlBadge');
    badge.textContent = data.urls.enabled ? `${data.urls.enabled}/${data.urls.total}` : '0';

    const alert = $('#alertDeps');
    if (!deps.ok) {
      alert.classList.remove('hidden');
      alert.innerHTML = `当前用于运行 main.py 的 Python 缺少依赖：<code>${esc((deps.missing || []).join(', '))}</code>。
        请在项目目录执行 <code>pip install -r requirements.txt</code>，或把依赖装到项目内的 <code>.venv</code> 后重启本控制台。`;
    } else if (!ff.ok) {
      alert.classList.remove('hidden');
      alert.innerHTML = '未检测到 <code>ffmpeg</code>，无法录制。请安装 ffmpeg（Windows 可执行 <code>winget install Gyan.FFmpeg</code>），或把 ffmpeg 解压到项目根目录的 <code>ffmpeg</code> 文件夹。';
    } else {
      alert.classList.add('hidden');
    }
  } catch (err) {
    console.error(err);
  }
}

async function loadRecentFiles() {
  const box = $('#recentFiles');
  try {
    const data = await api('/api/files?recursive=true&page_size=6');
    if (!data.files.length) {
      box.innerHTML = `<div class="empty">${t('noData')}</div>`;
      return;
    }
    box.innerHTML = data.files.map((f) => `
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:center">
        <a href="/api/files/download?path=${encodeURIComponent(f.path)}" title="${esc(f.rel)}">${esc(f.rel)}</a>
        <span class="muted mono">${humanSize(f.size)} · ${esc(f.mtime_text)}</span>
      </div>`).join('');
  } catch (err) {
    box.innerHTML = `<div class="empty">${esc(err.message)}</div>`;
  }
}

/* ------------------------------------------------------------------ 直播间地址 */
function filteredUrls() {
  const kw = S.urlSearch.trim().toLowerCase();
  return S.urls.filter((item) => {
    if (S.urlFilter === 'enabled' && !item.enabled) return false;
    if (S.urlFilter === 'disabled' && item.enabled) return false;
    if (S.urlFilter === 'invalid' && item.valid) return false;
    if (kw && !(item.url.toLowerCase().includes(kw) || (item.name || '').toLowerCase().includes(kw))) return false;
    return true;
  });
}

function renderUrls() {
  const tbody = $('#urlTbody');
  const items = filteredUrls();
  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:26px">${t('noData')}</td></tr>`;
  } else {
    tbody.innerHTML = items.map((item) => `
      <tr data-index="${item.index}" class="${item.enabled ? '' : 'row-disabled'}">
        <td><input type="checkbox" class="url-check" data-index="${item.index}" ${S.urlSelected.has(item.index) ? 'checked' : ''}></td>
        <td>${item.enabled ? `<span class="tag ok">${t('enabled')}</span>`
                           : `<span class="tag">${t('disabled')}</span>`}
            ${item.valid ? '' : `<span class="tag err">${t('invalidUrl')}</span>`}</td>
        <td>
          <select class="select url-quality" data-index="${item.index}">
            ${['', '原画', '蓝光', '超清', '高清', '标清', '流畅'].map((q) =>
              `<option value="${q}" ${item.quality === q ? 'selected' : ''}>${q || t('useDefault')}</option>`).join('')}
          </select>
        </td>
        <td><input class="input url-text" data-index="${item.index}" value="${esc(item.url)}"></td>
        <td><input class="input url-name" data-index="${item.index}" value="${esc(item.name)}" placeholder="-"></td>
        <td>
          <button class="btn tiny ghost url-toggle" data-index="${item.index}" data-enabled="${item.enabled ? '0' : '1'}">
            ${item.enabled ? t('disable') : t('enable')}
          </button>
          <button class="btn tiny danger url-del" data-index="${item.index}" title="${t('deleteSelected')}">${icon('trash')}</button>
        </td>
      </tr>`).join('');
  }
  const total = S.urls.length;
  const enabled = S.urls.filter((u) => u.enabled).length;
  $('#urlSummary').textContent = S.lang === 'en'
    ? `${items.length} shown · ${enabled}/${total} enabled`
    : `显示 ${items.length} 条 · 共 ${total} 条，已启用 ${enabled} 条`;
}

async function loadUrls() {
  const data = await api('/api/urls');
  S.urls = data.items;
  S.urlSelected.clear();
  renderUrls();
  const badge = $('#navUrlBadge');
  badge.textContent = `${data.enabled}/${data.total}`;
}

async function addUrl() {
  const url = $('#newUrl').value.trim();
  if (!url) { toast(S.lang === 'en' ? 'Please enter a URL' : '请填写直播间地址', 'warn'); return; }
  try {
    await api('/api/urls', { method: 'POST', body: { url, quality: $('#newQuality').value, name: $('#newName').value.trim() } });
    $('#newUrl').value = '';
    $('#newName').value = '';
    toast(S.lang === 'en' ? 'Added' : '已添加', 'ok');
    await loadUrls();
  } catch (err) { toast(err.message, 'err'); }
}

async function updateUrlField(index, patch) {
  try {
    await api('/api/urls', { method: 'PUT', body: Object.assign({ index }, patch) });
    await loadUrls();
  } catch (err) { toast(err.message, 'err'); await loadUrls(); }
}

/* ------------------------------------------------------------------ 参数设置 */
function currentSection() {
  return S.config.find((s) => s.name === S.section);
}

function fieldValue(section, key) {
  if (S.dirty[section] && Object.prototype.hasOwnProperty.call(S.dirty[section], key)) {
    return S.dirty[section][key];
  }
  const sec = S.config.find((s) => s.name === section);
  const item = sec && sec.items.find((i) => i.key === key);
  return item ? item.value : '';
}

function setDirty(section, key, value, original) {
  if (!S.dirty[section]) S.dirty[section] = {};
  if (String(value) === String(original)) {
    delete S.dirty[section][key];
    if (!Object.keys(S.dirty[section]).length) delete S.dirty[section];
  } else {
    S.dirty[section][key] = value;
  }
  updateSaveBar();
  const field = $(`.field[data-key="${CSS.escape(key)}"][data-section="${CSS.escape(section)}"]`);
  if (field) {
    const isDirty = !!(S.dirty[section] && Object.prototype.hasOwnProperty.call(S.dirty[section], key));
    field.classList.toggle('dirty', isDirty);
  }
}

function dirtyCount() {
  return Object.keys(S.dirty).reduce((sum, sec) => sum + Object.keys(S.dirty[sec]).length, 0);
}

function updateSaveBar() {
  const count = dirtyCount();
  const bar = $('#saveBar');
  bar.classList.toggle('hidden', count === 0);
  $('#saveBarText').textContent = S.lang === 'en'
    ? `${count} unsaved change(s)` : `有 ${count} 项修改未保存`;
}

function buildControl(section, item) {
  const meta = item.meta;
  const key = item.key;
  const value = fieldValue(section, key);
  const type = meta.type;
  const attrs = `data-key="${esc(key)}" data-section="${esc(section)}"`;

  if (type === 'bool') {
    const on = value === '是';
    return `<label class="switch"><input type="checkbox" class="ctl" ${attrs} data-original="${esc(value)}" ${on ? 'checked' : ''}><span class="slider"></span></label>`;
  }
  if (type === 'select') {
    const options = (meta.options || []).map((opt) =>
      `<option value="${esc(opt)}" ${String(value) === String(opt) ? 'selected' : ''}>${esc(opt)}</option>`).join('');
    return `<select class="select ctl" ${attrs} data-original="${esc(value)}">${options}</select>`;
  }
  if (type === 'multiselect') {
    const picked = String(value || '').split(/[,，]/).map((s) => s.trim()).filter(Boolean);
    return `<div class="chips ctl-chips" ${attrs} data-original="${esc(value)}">` +
      (meta.options || []).map((opt) =>
        `<button type="button" class="chip ${picked.includes(opt) ? 'active' : ''}" data-opt="${esc(opt)}">${esc(opt)}</button>`).join('') +
      '</div>';
  }
  if (type === 'int' || type === 'float') {
    const step = meta.step || (type === 'int' ? 1 : 'any');
    return `<input type="number" class="input ctl" ${attrs} data-original="${esc(value)}" value="${esc(value)}"
      ${meta.min !== undefined ? `min="${meta.min}"` : ''} ${meta.max !== undefined ? `max="${meta.max}"` : ''} step="${step}">`;
  }
  if (type === 'secret') {
    const rows = meta.rows || 1;
    if (rows > 1) {
      return `<textarea class="input ctl secret-masked" ${attrs} data-original="${esc(value)}" rows="${rows}"
        spellcheck="false">${esc(value)}</textarea>`;
    }
    return `<input type="password" class="input ctl" ${attrs} data-original="${esc(value)}" value="${esc(value)}" spellcheck="false" autocomplete="off">`;
  }
  if (type === 'textarea') {
    return `<textarea class="input ctl" ${attrs} data-original="${esc(value)}" rows="${meta.rows || 3}">${esc(value)}</textarea>`;
  }
  if (type === 'path') {
    const hint = meta.placeholder || (meta.help && (meta.help[S.lang] || meta.help.zh)) || '';
    return `<input type="text" class="input ctl" ${attrs} data-original="${esc(value)}" value="${esc(value)}"
      placeholder="${esc(hint)}">
      <button type="button" class="btn tiny ghost pick-dir" data-target="${esc(key)}">${icon('folder')}</button>`;
  }
  if (type === 'list') {
    return `<input type="text" class="input ctl" ${attrs} data-original="${esc(value)}" value="${esc(value)}"
      placeholder="a, b, c">`;
  }
  return `<input type="text" class="input ctl" ${attrs} data-original="${esc(value)}" value="${esc(value)}"
    placeholder="${esc(meta.placeholder || '')}">`;
}

function renderConfig() {
  const section = currentSection();
  if (!section) return;
  $('#cfgTitle').textContent = section.label[S.lang] || section.label.zh || section.name;
  $('#cfgDesc').textContent = (section.desc && (section.desc[S.lang] || section.desc.zh)) || '';

  const kw = S.cfgSearch.trim().toLowerCase();
  const items = section.items.filter((item) => {
    if (!kw) return true;
    const label = (item.meta.label[S.lang] || item.meta.label.zh || '').toLowerCase();
    return item.key.toLowerCase().includes(kw) || label.includes(kw);
  });

  const html = items.map((item) => {
    const meta = item.meta;
    const label = meta.label[S.lang] || meta.label.zh || item.key;
    const help = (meta.help && (meta.help[S.lang] || meta.help.zh)) || '';
    const wide = ['textarea', 'multiselect', 'list'].includes(meta.type) || String(item.value).length > 60
      || (meta.type === 'secret' && (meta.rows || 1) > 1);
    const isDirty = !!(S.dirty[section.name] && Object.prototype.hasOwnProperty.call(S.dirty[section.name], item.key));
    const control = buildControl(section.name, item);
    const isSwitch = meta.type === 'bool';
    return `
      <div class="field ${wide ? 'wide' : ''} ${isDirty ? 'dirty' : ''}" data-key="${esc(item.key)}" data-section="${esc(section.name)}">
        <div class="field-head">
          <div>
            <div class="field-label">${esc(label)}${meta.required ? ` <span class="req">*</span>` : ''}</div>
            ${label === item.key ? '' : `<div class="field-key">${esc(item.key)}</div>`}
          </div>
          ${isSwitch ? control : ''}
        </div>
        ${isSwitch ? '' : `<div class="field-body">${control}</div>`}
        ${help ? `<div class="field-help">${esc(help)}</div>` : ''}
      </div>`;
  }).join('');

  $('#cfgFields').innerHTML = html || `<div class="muted" style="padding:20px;text-align:center">${t('noData')}</div>`;
  bindConfigEvents(section.name);
  applyDepends(section.name);
  updateSaveBar();
}

function bindConfigEvents(sectionName) {
  $$('#cfgFields .ctl').forEach((el) => {
    const key = el.dataset.key;
    const original = el.dataset.original;
    const handler = () => {
      let value;
      if (el.type === 'checkbox') value = el.checked ? '是' : '否';
      else value = el.value;
      setDirty(sectionName, key, value, original);
      applyDepends(sectionName);
    };
    el.addEventListener('change', handler);
    if (el.tagName === 'INPUT' && (el.type === 'text' || el.type === 'number' || el.type === 'password')) {
      el.addEventListener('input', handler);
    }
  });

  $$('#cfgFields .ctl-chips').forEach((box) => {
    box.addEventListener('click', (ev) => {
      const chip = ev.target.closest('.chip');
      if (!chip) return;
      chip.classList.toggle('active');
      const picked = $$('.chip.active', box).map((c) => c.dataset.opt);
      setDirty(sectionName, box.dataset.key, picked.join(', '), box.dataset.original);
    });
  });

  $$('#cfgFields .pick-dir').forEach((btn) => {
    btn.addEventListener('click', () => pickDirectory(btn.dataset.target));
  });

  $$('#cfgFields .secret-masked').forEach((el) => {
    el.style.webkitTextSecurity = 'disc';
    el.addEventListener('focus', () => { el.style.webkitTextSecurity = ''; });
    el.addEventListener('blur', () => { el.style.webkitTextSecurity = 'disc'; });
  });
}

function applyDepends(sectionName) {
  const section = currentSection();
  if (!section) return;
  section.items.forEach((item) => {
    const dep = item.meta.depends_on;
    if (!dep) return;
    const field = $(`.field[data-key="${CSS.escape(item.key)}"][data-section="${CSS.escape(sectionName)}"]`);
    if (!field) return;
    const active = fieldValue(sectionName, dep) === '是';
    field.style.opacity = active ? '1' : '.5';
    field.title = active ? '' : (S.lang === 'en' ? `Requires "${dep}" to be on` : `需先开启「${dep}」`);
    $$('input, textarea, select, button', field).forEach((el) => { el.disabled = !active; });
  });
}

async function saveConfig() {
  if (!dirtyCount()) return;
  try {
    const result = await api('/api/config', { method: 'POST', body: { updates: S.dirty } });
    const n = (result.changed || []).length;
    S.dirty = {};
    toast(t('saved', { n }), 'ok');
    await loadConfig();
    if (S.page === 'config') renderConfig();
    refreshState();
  } catch (err) {
    let msg = err.message;
    if (err.payload && err.payload.errors) {
      msg += '：' + err.payload.errors.map((e) => `${e.key || e.section}: ${e.error}`).join('；');
    }
    toast(msg, 'err');
  }
}

async function loadConfig() {
  const data = await api('/api/config');
  S.config = data.sections;
}

async function pickDirectory(targetKey) {
  let current = fieldValue(S.section, targetKey) || '';
  const render = async (path) => {
    let data;
    try { data = await api(`/api/browse?path=${encodeURIComponent(path || '')}`); }
    catch (err) { toast(err.message, 'err'); return; }
    const listHtml = [
      ...(data.drives || []).map((d) => `<div class="dir-item" data-path="${esc(d.path)}">${icon('folder')}<span>${esc(d.name)}</span></div>`),
      ...(data.dirs || []).map((d) => `<div class="dir-item" data-path="${esc(d.path)}">${icon('folder')}<span>${esc(d.name)}</span></div>`),
    ].join('') || `<div class="dir-item" style="color:var(--muted)">${t('noData')}</div>`;
    openModal(t('whichFolder'), `
      <div class="input-group"><input class="input" id="dirCurrent" value="${esc(data.path)}"></div>
      <div class="dir-list" id="dirList">${listHtml}</div>`,
      `<button class="btn ghost" id="dirCancel">${S.lang === 'en' ? 'Cancel' : '取消'}</button>
       <button class="btn primary" id="dirUse">${t('useThisFolder')}</button>`);
    const choose = async (p) => { await render(p); };
    $('#dirList').onclick = (ev) => {
      const item = ev.target.closest('.dir-item');
      if (item && item.dataset.path) choose(item.dataset.path);
    };
    $('#dirCurrent').addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') choose(ev.target.value.trim());
    });
    $('#dirCancel').onclick = closeModal;
    $('#dirUse').onclick = () => {
      const value = $('#dirCurrent').value.trim();
      const el = $(`.ctl[data-key="${CSS.escape(targetKey)}"]`);
      if (el) {
        el.value = value;
        el.dispatchEvent(new Event('input', { bubbles: true }));
      }
      closeModal();
    };
  };
  await render(current);
}

/* ------------------------------------------------------------------ 日志 */
function connectLogs() {
  if (S.logSource !== 'live') return;
  if (S.es) return;
  const url = `/api/logs/stream?since=${S.logSource === 'live' ? 0 : S.lastLogId}`;
  const es = new EventSource(url);
  S.es = es;
  setConn('connecting');
  es.onopen = () => { setConn('on'); S.esRetry = 0; };
  es.onmessage = (ev) => {
    let payload;
    try { payload = JSON.parse(ev.data); } catch (e) { return; }
    if (payload.type === 'log') {
      pushLog(payload.entry);
    } else if (payload.type === 'status') {
      applyLiveStatus(payload.status);
    }
  };
  es.onerror = () => {
    setConn('off');
    es.close();
    S.es = null;
    S.esRetry += 1;
    setTimeout(() => { if (S.page === 'logs' && S.logSource === 'live') connectLogs(); },
      Math.min(1000 * S.esRetry, 8000));
  };
}

function disconnectLogs() {
  if (S.es) { S.es.close(); S.es = null; }
  setConn('');
}

function setConn(kind) {
  const el = $('#logConn');
  el.classList.remove('on', 'off');
  if (kind === 'on') { el.classList.add('on'); el.textContent = t('logConnected'); }
  else if (kind === 'off') { el.classList.add('off'); el.textContent = t('logDisconnected'); }
  else if (kind === 'connecting') { el.textContent = t('logConnecting'); }
  else { el.textContent = '-'; }
}

function applyLiveStatus(status) {
  if (!status) return;
  const proc = status;
  const pill = $('#statusPill');
  pill.classList.remove('running', 'stopped', 'error');
  pill.classList.add(proc.running ? 'running' : 'stopped');
  $('#statusText').textContent = proc.running ? t('statusRunning') : t('statusStopped');
  $('#btnStart').disabled = !!proc.running;
  $('#btnStop').disabled = !proc.running;
  const stats = proc.stats || {};
  $('#statMonitoring').textContent = stats.monitoring || 0;
  $('#statRecording').textContent = stats.recording_count || 0;
  $('#statErrors').textContent = stats.error_count || 0;
}

function pushLog(entry) {
  if (!entry || S.logIds.has(entry.id)) return;
  S.logIds.add(entry.id);
  S.lastLogId = Math.max(S.lastLogId, entry.id);
  S.logEntries.push(entry);
  if (S.logEntries.length > 4000) {
    const removed = S.logEntries.splice(0, 1000);
    removed.forEach((e) => S.logIds.delete(e.id));
  }
  if (S.logPaused || S.page !== 'logs') {
    updateLogSummary();
    return;
  }
  appendLogLine(entry);
}

function levelBucket(level) {
  if (level === 'WARNING') return 'WARNING';
  if (level === 'ERROR' || level === 'CRITICAL') return 'ERROR';
  if (level === 'OUT') return 'OUT';
  return 'INFO';
}

function logVisible(entry) {
  if (!S.logLevels.has(levelBucket(entry.level))) return false;
  if (S.logSearch && !entry.text.toLowerCase().includes(S.logSearch)) return false;
  return true;
}

function logLineHtml(entry) {
  const time = formatTime(entry.ts).split(' ')[1] || '';
  return `<span class="ln"><span class="t">${esc(time)}</span><span class="lvl lv-${esc(levelBucket(entry.level))}">${esc(entry.level.padEnd(7))}</span>${esc(entry.text)}</span>`;
}

function appendLogLine(entry) {
  if (!logVisible(entry)) return;
  const box = $('#console');
  const empty = $('.empty', box);
  if (empty) empty.remove();
  box.insertAdjacentHTML('beforeend', logLineHtml(entry));
  while (box.childElementCount > 3000) box.removeChild(box.firstChild);
  if ($('#logAutoScroll').checked) box.scrollTop = box.scrollHeight;
  updateLogSummary();
}

function renderConsole() {
  const box = $('#console');
  const items = S.logEntries.filter(logVisible).slice(-1200);
  if (!items.length) {
    box.innerHTML = `<span class="empty">${t('emptyConsole')}</span>`;
  } else {
    box.innerHTML = items.map(logLineHtml).join('');
    box.scrollTop = box.scrollHeight;
  }
  updateLogSummary();
}

function updateLogSummary() {
  const shown = S.logEntries.filter(logVisible).length;
  $('#logSummary').textContent = S.lang === 'en'
    ? `${shown} lines shown · ${S.logEntries.length} buffered${S.logPaused ? ' · paused' : ''}`
    : `显示 ${shown} 行 · 缓冲 ${S.logEntries.length} 行${S.logPaused ? ' · 已暂停' : ''}`;
}

async function loadLogFiles() {
  const data = await api('/api/logs/files');
  const sel = $('#logFileSelect');
  sel.innerHTML = data.items.length
    ? data.items.map((f) => `<option value="${esc(f.name)}">${esc(f.name)} (${esc(f.size_text)})</option>`).join('')
    : `<option value="">${t('noData')}</option>`;
  if (S.logSource === 'file' && data.items.length) await tailLog();
}

async function tailLog() {
  const name = $('#logFileSelect').value;
  if (!name) { $('#console').innerHTML = `<span class="empty">${t('noData')}</span>`; return; }
  try {
    const data = await api(`/api/logs/tail?name=${encodeURIComponent(name)}&lines=800`);
    const lines = data.lines.map((line, i) => {
      const level = /ERROR|CRITICAL/.test(line) ? 'ERROR' : /WARNING/.test(line) ? 'WARNING'
        : /DEBUG/.test(line) ? 'DEBUG' : 'INFO';
      return `<span class="ln"><span class="lvl lv-${level}">${level.padEnd(7)}</span>${esc(line)}</span>`;
    }).join('');
    $('#console').innerHTML = lines || `<span class="empty">${t('noData')}</span>`;
    $('#console').scrollTop = $('#console').scrollHeight;
  } catch (err) { toast(err.message, 'err'); }
}

/* ------------------------------------------------------------------ 文件 */
async function loadFiles(path, skipHash) {
  try {
    const params = new URLSearchParams();
    if (path) params.set('path', path);
    if (S.fileFilter) params.set('keyword', S.fileFilter);
    if ($('#fileRecursive').checked) params.set('recursive', 'true');
    const data = await api(`/api/files?${params.toString()}`);
    S.files = data;
    S.filePath = data.path;
    // 目录变化后丢弃已不在当前列表里的勾选，避免误处理不可见的文件
    const visible = new Set((data.files || []).map((f) => f.path));
    Array.from(S.fileSelected).forEach((p) => { if (!visible.has(p)) S.fileSelected.delete(p); });
    if (!skipHash && S.page === 'files') syncHash({ replace: true });
    renderFiles();
  } catch (err) {
    toast(err.message, 'err');
    $('#fileTbody').innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:24px">${esc(err.message)}</td></tr>`;
  }
}

function renderFiles() {
  const data = S.files;
  if (!data) return;
  const tbody = $('#fileTbody');
  const canDelete = data.deletable !== false;
  const rows = [];
  // 只有位于录制保存目录内才给删除按钮，避免"点了报错"
  const delBtn = (path) => (canDelete
    ? `<button class="btn tiny danger file-del" data-path="${esc(path)}">${icon('trash')}</button>` : '');
  if (!data.recursive) {
    data.dirs.forEach((d) => {
      rows.push(`<tr>
        <td></td>
        <td><a href="#" class="dir-link" data-path="${esc(d.path)}">${icon('folder')}<span>${esc(d.name)}</span></a></td>
        <td class="muted">-</td>
        <td class="muted mono">${esc(d.mtime_text)}</td>
        <td>${delBtn(d.path)}</td>
      </tr>`);
    });
  }
  data.files.forEach((f) => {
    const playable = ['mp4', 'webm', 'm4v', 'mov', 'ogv'].includes(f.ext);
    const checked = S.fileSelected.has(f.path) ? ' checked' : '';
    rows.push(`<tr>
      <td><input type="checkbox" class="file-check" data-path="${esc(f.path)}"${checked}></td>
      <td title="${esc(f.rel || f.name)}"><span class="file-name">${icon(f.kind === 'video' ? 'video' : f.kind === 'audio' ? 'bell' : 'file')}<span>${esc(f.name)}</span></span></td>
      <td class="mono">${humanSize(f.size)}</td>
      <td class="muted mono">${esc(f.mtime_text)}</td>
      <td>
        ${playable ? `<button class="btn tiny ghost file-play" data-path="${esc(f.path)}" data-name="${esc(f.name)}">${t('preview')}</button>` : ''}
        <a class="btn tiny ghost" href="/api/files/download?path=${encodeURIComponent(f.path)}">${t('download')}</a>
        ${delBtn(f.path)}
      </td>
    </tr>`);
  });
  tbody.innerHTML = rows.length ? rows.join('')
    : `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:26px">${t('noData')}</td></tr>`;

  // 面包屑：任意层级都能点，方便从 C 盘一路点到 D 盘
  const parts = data.path.replace(/\\/g, '/').split('/').filter(Boolean);
  const crumbs = [];
  let acc = '';
  parts.forEach((part, i) => {
    if (i === 0 && /^[A-Za-z]:$/.test(part)) {
      acc = part + '/';
    } else {
      acc = acc.endsWith('/') || !acc ? acc + part : acc + '/' + part;
    }
    crumbs.push(`<button data-path="${esc(acc)}">${esc(part)}</button>`);
  });
  $('#filePath').innerHTML = crumbs.join('<span>/</span>');

  // 盘符切换下拉
  const drives = data.drives || [];
  const sel = $('#fileDrives');
  sel.classList.toggle('hidden', drives.length < 2);
  if (drives.length >= 2) {
    const current = (data.path.match(/^[A-Za-z]:/) || [''])[0].toUpperCase();
    sel.innerHTML = drives.map((d) =>
      `<option value="${esc(d.path)}" ${d.path.toUpperCase().startsWith(current) ? 'selected' : ''}>${esc(d.name)}</option>`).join('');
  }

  // 不在录制目录内时给出提示（删除按钮已隐藏）
  const hint = $('#fileHint');
  const root = data.root || (data.roots && data.roots[0]) || '';
  if (canDelete) {
    hint.classList.add('hidden');
  } else {
    hint.classList.remove('hidden');
    hint.innerHTML = `${esc(t('outsideRootHint'))}
      <button class="btn tiny ghost" id="hintGoRoot" style="margin-left:8px">${esc(t('goSaveDir'))}</button>`;
    const goBtn = $('#hintGoRoot');
    if (goBtn) goBtn.onclick = () => loadFiles(root);
  }

  const dirCount = data.recursive ? 0 : data.dirs.length;
  $('#fileSummary').textContent = S.lang === 'en'
    ? `${dirCount ? dirCount + ' folder(s) · ' : ''}${data.files.length} file(s) · ${humanSize(data.total_size)}`
    : `${dirCount ? dirCount + ' 个文件夹 · ' : ''}${data.files.length} 个文件 · 合计 ${humanSize(data.total_size)}`;
  updateFileSelectionUI();
}

/* ------------------------------------------------------------------ 文件勾选与媒体任务 */
function updateFileSelectionUI() {
  const count = S.fileSelected.size;
  const info = $('#fileSelectedInfo');
  if (info) info.textContent = count ? (S.lang === 'en' ? `· ${count} selected` : `· 已选 ${count} 个`) : '';
  const all = $('#fileCheckAll');
  if (all) {
    const visible = (S.files && S.files.files) ? S.files.files.length : 0;
    all.checked = visible > 0 && count >= visible;
    all.indeterminate = count > 0 && !all.checked;
  }
  const mergeBtn = $('#btnMergeFiles');
  if (mergeBtn) mergeBtn.disabled = count < 2;
  const cropBtn = $('#btnTo169');
  if (cropBtn) cropBtn.disabled = count < 1;
}

function selectedFilePaths() {
  return Array.from(S.fileSelected);
}

async function startMergeSelected() {
  const paths = selectedFilePaths();
  if (paths.length < 2) { toast(t('needTwoFiles'), 'warn'); return; }
  if (!await confirmDialog(t('confirmMerge', { n: paths.length }))) return;
  try {
    const result = await api('/api/media/merge', { method: 'POST', body: { paths } });
    S.jobsHidden = false;
    toast(t('mergeStarted'), 'ok');
    if (result.job) renderJobs([result.job]);
    pollJobs(true);
  } catch (err) { toast(err.message, 'err'); }
}

async function startTo169() {
  const paths = selectedFilePaths();
  if (!paths.length) { toast(t('nothingSelected'), 'warn'); return; }
  if (!await confirmDialog(t('confirmTo169', { n: paths.length }))) return;
  try {
    const result = await api('/api/media/to16x9', { method: 'POST', body: { paths } });
    S.jobsHidden = false;
    toast(t('convertStarted', { n: result.count || paths.length }), 'ok');
    pollJobs(true);
  } catch (err) { toast(err.message, 'err'); }
}

const JOB_LABELS = {
  queued: 'jobQueued', running: 'jobRunning', done: 'jobDone', error: 'jobError', cancelled: 'jobCancelled',
};
const JOB_TAG_CLASS = { done: 'ok', error: 'err', cancelled: 'warn' };

function renderJobs(items) {
  const card = $('#mediaJobsCard');
  const box = $('#mediaJobs');
  if (!card || !box) return;
  S.mediaJobs = items || [];
  if (!S.mediaJobs.length) { card.classList.add('hidden'); return; }
  if (S.jobsHidden) { card.classList.add('hidden'); } else { card.classList.remove('hidden'); }

  const active = S.mediaJobs.filter((j) => j.running).length;
  const hint = $('#mediaJobsHint');
  if (hint) hint.textContent = active ? t('jobsRunningHint', { n: active }) : '';

  box.innerHTML = S.mediaJobs.map((job) => {
    const label = t(JOB_LABELS[job.status] || job.status);
    const tagClass = JOB_TAG_CLASS[job.status] || '';
    const percent = job.status === 'done' ? 100 : Math.max(0, Math.min(100, job.percent || 0));
    const result = job.result || {};
    let detail = '';
    if (job.error) {
      detail = `<div class="job-detail err-text">${esc(job.error)}</div>`;
    } else if (result.output) {
      const badge = result.lossless ? t('losslessBadge') : t('reencodedBadge');
      detail = `<div class="job-detail">${esc(result.name || '')} · ${humanSize(result.size || 0)} · ${badge}</div>`;
    }
    const cancel = job.running
      ? `<button class="btn tiny danger job-cancel" data-id="${esc(job.id)}">${t('cancelJob')}</button>` : '';
    return `<div class="job-row">
      <div class="job-head"><strong>${esc(job.title)}</strong><span class="tag ${tagClass}">${label}</span></div>
      <div class="job-bar"><span style="width:${percent}%"></span></div>
      <div class="job-foot"><span class="muted">${esc(job.message || '')}</span>${cancel}</div>
      ${detail}
    </div>`;
  }).join('');
}

async function pollJobs(force) {
  if (S.jobsBusy) return;              // 防止快速连点造成并发请求
  if (S.jobsTimer) { clearTimeout(S.jobsTimer); S.jobsTimer = null; }
  S.jobsBusy = true;
  try {
    const data = await api('/api/media/jobs?limit=20');
    renderJobs(data.items || []);
    const active = data.active || 0;
    if (active > 0) {
      S.jobsWasActive = true;
      S.jobsTimer = setTimeout(() => { S.jobsTimer = null; pollJobs(false); }, 1500);
    } else if (S.jobsWasActive) {
      // 从「有任务」变成「全部结束」时刷新一次文件列表，让新文件立刻出现
      S.jobsWasActive = false;
      if (S.page === 'files') loadFiles(S.filePath, true);
    }
  } catch (err) {
    S.jobsTimer = null;
  } finally {
    S.jobsBusy = false;
  }
}

/* ------------------------------------------------------------------ 事件绑定 */
function bindEvents() {
  $$('.nav-item').forEach((el) => {
    el.addEventListener('click', () => goto(el.dataset.page, el.dataset.section));
  });
  document.addEventListener('click', (ev) => {
    const goto2 = ev.target.closest('[data-goto]');
    if (goto2) goto(goto2.dataset.goto);
  });

  $('#menuToggle').onclick = () => $('#sidebar').classList.toggle('open');
  $('#modalClose').onclick = closeModal;
  $('#modalMask').addEventListener('click', (ev) => { if (ev.target.id === 'modalMask') closeModal(); });
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape') closeModal();
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 's') {
      ev.preventDefault();
      if (S.page === 'config') saveConfig();
    }
  });

  $('#themeToggle').onclick = () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('dlr_theme', next);
    $('#themeToggle').innerHTML = icon(next === 'dark' ? 'sun' : 'moon');
  };
  $('#langToggle').onclick = () => {
    S.lang = S.lang === 'zh' ? 'en' : 'zh';
    localStorage.setItem('dlr_lang', S.lang);
    $('#langToggle').textContent = S.lang === 'zh' ? 'EN' : '中文';
    applyI18n();
    goto(S.page, S.section);
    if (S.page !== 'config') renderConfig();
  };

  // 控制
  $('#btnStart').onclick = async () => {
    try {
      await api('/api/control/start', { method: 'POST', body: {} });
      toast(t('started'), 'ok');
      setTimeout(refreshState, 600);
      if (S.page === 'logs') { S.logSource = 'live'; }
    } catch (err) {
      let msg = err.message;
      if (err.payload && err.payload.missing) msg += `：${err.payload.missing.join(', ')}`;
      toast(msg, 'err');
    }
  };
  $('#btnStop').onclick = async () => {
    if (!await confirmDialog(t('confirmStop'))) return;
    try {
      await api('/api/control/stop', { method: 'POST', body: {} });
      toast(t('stopped'), 'ok');
      setTimeout(refreshState, 500);
    } catch (err) { toast(err.message, 'err'); }
  };
  $('#btnRestart').onclick = async () => {
    if (!await confirmDialog(t('confirmStop'))) return;
    try {
      await api('/api/control/restart', { method: 'POST', body: {} });
      toast(t('started'), 'ok');
      setTimeout(refreshState, 800);
    } catch (err) { toast(err.message, 'err'); }
  };
  $('#btnRecheck').onclick = async () => { await api('/api/state'); refreshState(); toast(S.lang === 'en' ? 'Refreshed' : '已重新检测', 'ok'); };
  $('#btnOpenFolder').onclick = async () => {
    try { const r = await api('/api/open', { method: 'POST', body: { path: (S.state && S.state.save_path) || '' } }); if (!r.ok) toast(r.error, 'err'); }
    catch (err) { toast(err.message, 'err'); }
  };

  // 地址页
  $('#btnAddUrl').onclick = addUrl;
  $('#newUrl').addEventListener('keydown', (ev) => { if (ev.key === 'Enter') addUrl(); });
  $('#urlSearch').addEventListener('input', (ev) => { S.urlSearch = ev.target.value; renderUrls(); });
  $('#urlFilter').addEventListener('change', (ev) => { S.urlFilter = ev.target.value; renderUrls(); });
  $('#urlCheckAll').addEventListener('change', (ev) => {
    const items = filteredUrls();
    if (ev.target.checked) items.forEach((i) => S.urlSelected.add(i.index));
    else items.forEach((i) => S.urlSelected.delete(i.index));
    renderUrls();
  });
  $('#urlTbody').addEventListener('change', (ev) => {
    const el = ev.target;
    const index = Number(el.dataset.index);
    if (el.classList.contains('url-check')) {
      if (el.checked) S.urlSelected.add(index); else S.urlSelected.delete(index);
      return;
    }
    if (el.classList.contains('url-quality')) updateUrlField(index, { quality: el.value });
    if (el.classList.contains('url-text')) updateUrlField(index, { url: el.value });
    if (el.classList.contains('url-name')) updateUrlField(index, { name: el.value });
  });
  $('#urlTbody').addEventListener('click', async (ev) => {
    const toggle = ev.target.closest('.url-toggle');
    if (toggle) {
      await updateUrlField(Number(toggle.dataset.index), { enabled: toggle.dataset.enabled === '1' });
      return;
    }
    const del = ev.target.closest('.url-del');
    if (del) {
      if (!await confirmDialog(t('confirmDelete', { n: 1 }))) return;
      try { await api('/api/urls/delete', { method: 'POST', body: { indexes: [Number(del.dataset.index)] } }); await loadUrls(); toast(S.lang === 'en' ? 'Deleted' : '已删除', 'ok'); }
      catch (err) { toast(err.message, 'err'); }
    }
  });
  $('#btnDeleteSelected').onclick = async () => {
    if (!S.urlSelected.size) { toast(S.lang === 'en' ? 'Nothing selected' : '请先勾选要删除的地址', 'warn'); return; }
    if (!await confirmDialog(t('confirmDelete', { n: S.urlSelected.size }))) return;
    try { await api('/api/urls/delete', { method: 'POST', body: { indexes: Array.from(S.urlSelected) } }); await loadUrls(); toast(S.lang === 'en' ? 'Deleted' : '已删除', 'ok'); }
    catch (err) { toast(err.message, 'err'); }
  };
  $('#btnEnableAll').onclick = () => bulkToggle(true);
  $('#btnDisableAll').onclick = async () => {
    if (!await confirmDialog(t('confirmDisableAll'))) return;
    bulkToggle(false);
  };
  async function bulkToggle(enabled) {
    const indexes = filteredUrls().map((i) => i.index);
    if (!indexes.length) return;
    try { await api('/api/urls/toggle', { method: 'POST', body: { indexes, enabled } }); await loadUrls(); toast(S.lang === 'en' ? 'Done' : '已更新', 'ok'); }
    catch (err) { toast(err.message, 'err'); }
  }
  $('#btnImport').onclick = () => {
    openModal(t('importTitle'), `
      <div class="alert info">${esc(t('importHint'))}</div>
      <textarea class="input" id="importText" rows="10" placeholder="https://live.douyin.com/123456
高清, https://live.bilibili.com/123, 主播名
#流畅, https://www.huya.com/xxx, 已停用的主播"></textarea>
      <label class="inline-check"><input type="radio" name="importMode" value="append" checked> ${t('importModeAppend')}</label>
      <label class="inline-check"><input type="radio" name="importMode" value="replace"> ${t('importModeReplace')}</label>`,
      `<button class="btn ghost" id="impCancel">${S.lang === 'en' ? 'Cancel' : '取消'}</button>
       <button class="btn primary" id="impOk">${t('doImport')}</button>`);
    $('#impCancel').onclick = closeModal;
    $('#impOk').onclick = async () => {
      const text = $('#importText').value;
      const mode = $('input[name="importMode"]:checked').value;
      try {
        const r = await api('/api/urls/import', { method: 'POST', body: { text, mode } });
        closeModal();
        toast(S.lang === 'en' ? `Imported ${r.added}, skipped ${r.skipped}` : `已导入 ${r.added} 条，跳过 ${r.skipped} 条`, 'ok');
        await loadUrls();
      } catch (err) { toast(err.message, 'err'); }
    };
  };

  // 设置页
  $('#cfgSearch').addEventListener('input', (ev) => { S.cfgSearch = ev.target.value; renderConfig(); });
  $('#btnSave').onclick = saveConfig;
  $('#btnDiscard').onclick = () => { S.dirty = {}; renderConfig(); toast(S.lang === 'en' ? 'Discarded' : '已放弃修改', 'ok'); };

  // 日志页
  $$('#logSource .seg-item').forEach((btn) => {
    btn.onclick = async () => {
      $$('#logSource .seg-item').forEach((b) => b.classList.toggle('active', b === btn));
      S.logSource = btn.dataset.source;
      $('#logFileSelect').classList.toggle('hidden', S.logSource !== 'file');
      if (S.logSource === 'live') { renderConsole(); connectLogs(); }
      else { disconnectLogs(); await loadLogFiles(); await tailLog(); }
    };
  });
  $('#logFileSelect').addEventListener('change', tailLog);
  $('#logSearch').addEventListener('input', (ev) => { S.logSearch = ev.target.value.toLowerCase(); if (S.logSource === 'live') renderConsole(); });
  $$('#logLevels .chip').forEach((chip) => {
    chip.onclick = () => {
      const level = chip.dataset.level;
      if (S.logLevels.has(level)) S.logLevels.delete(level); else S.logLevels.add(level);
      chip.classList.toggle('active', S.logLevels.has(level));
      renderConsole();
    };
  });
  $('#btnLogPause').onclick = () => {
    S.logPaused = !S.logPaused;
    $('#btnLogPause').innerHTML = `<span data-icon="${S.logPaused ? 'play' : 'pause'}"></span><span>${S.logPaused ? (S.lang === 'en' ? 'Resume' : '继续') : t('pause')}</span>`;
    applyIcons($('#btnLogPause'));
    if (!S.logPaused) renderConsole();
    else updateLogSummary();
  };
  $('#btnLogClear').onclick = async () => {
    S.logEntries = []; S.logIds.clear();
    try { await api('/api/logs/clear', { method: 'POST', body: {} }); } catch (e) { /* ignore */ }
    renderConsole();
  };

  // 文件页
  $('#btnUp').onclick = () => { if (S.files && S.files.parent) loadFiles(S.files.parent); };
  $('#btnRefreshFiles').onclick = () => loadFiles(S.filePath);
  $('#btnMergeFiles').onclick = startMergeSelected;
  $('#btnTo169').onclick = startTo169;
  $('#btnHideJobs').onclick = () => {
    S.jobsHidden = true;
    $('#mediaJobsCard').classList.add('hidden');
  };
  $('#fileCheckAll').addEventListener('change', (ev) => {
    if (!S.files || !S.files.files) return;
    if (ev.target.checked) S.files.files.forEach((f) => S.fileSelected.add(f.path));
    else S.fileSelected.clear();
    renderFiles();
  });
  $('#fileTbody').addEventListener('change', (ev) => {
    const el = ev.target;
    if (!el.classList.contains('file-check')) return;
    if (el.checked) S.fileSelected.add(el.dataset.path);
    else S.fileSelected.delete(el.dataset.path);
    updateFileSelectionUI();
  });
  $('#btnGoRoot').onclick = () => {
    const root = (S.files && (S.files.root || (S.files.roots && S.files.roots[0]))) || '';
    if (root) loadFiles(root);
  };
  $('#fileDrives').addEventListener('change', (ev) => { if (ev.target.value) loadFiles(ev.target.value); });
  $('#fileSearch').addEventListener('input', (ev) => {
    S.fileFilter = ev.target.value.trim();
    clearTimeout(window.__ft);
    window.__ft = setTimeout(() => loadFiles(S.filePath), 300);
  });
  $('#fileRecursive').addEventListener('change', () => loadFiles(S.filePath));
  $('#btnOpenFolder2').onclick = async () => {
    try { const r = await api('/api/open', { method: 'POST', body: { path: S.filePath } }); if (!r.ok) toast(r.error, 'err'); }
    catch (err) { toast(err.message, 'err'); }
  };
  $('#fileTbody').addEventListener('click', async (ev) => {
    const link = ev.target.closest('.dir-link');
    if (link) { ev.preventDefault(); loadFiles(link.dataset.path); return; }
    const del = ev.target.closest('.file-del');
    if (del) {
      if (!await confirmDialog(t('confirmDeleteFiles', { n: 1 }))) return;
      try { await api('/api/files/delete', { method: 'POST', body: { paths: [del.dataset.path] } }); toast(S.lang === 'en' ? 'Deleted' : '已删除', 'ok'); loadFiles(S.filePath); }
      catch (err) { toast(err.message, 'err'); }
      return;
    }
    const play = ev.target.closest('.file-play');
    if (play) {
      openModal(play.dataset.name,
        `<video controls autoplay src="/api/files/stream?path=${encodeURIComponent(play.dataset.path)}"></video>`,
        `<button class="btn ghost" onclick="document.getElementById('modalClose').click()">${S.lang === 'en' ? 'Close' : '关闭'}</button>`);
    }
  });
  $('#filePath').addEventListener('click', (ev) => {
    const btn = ev.target.closest('button');
    if (btn && btn.dataset.path) loadFiles(btn.dataset.path);
  });
  $('#mediaJobs').addEventListener('click', async (ev) => {
    const btn = ev.target.closest('.job-cancel');
    if (!btn) return;
    try {
      await api('/api/media/jobs/cancel', { method: 'POST', body: { id: btn.dataset.id } });
      toast(S.lang === 'en' ? 'Cancelling…' : '正在取消…', 'ok');
      pollJobs(true);
    } catch (err) { toast(err.message, 'err'); }
  });
}

/* ------------------------------------------------------------------ 初始化 */
async function init() {
  if (S.theme) document.documentElement.dataset.theme = S.theme;
  else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.dataset.theme = 'dark';
  }
  $('#themeToggle').innerHTML = icon(document.documentElement.dataset.theme === 'dark' ? 'sun' : 'moon');
  $('#langToggle').textContent = S.lang === 'zh' ? 'EN' : '中文';

  applyIcons();
  applyI18n();
  bindEvents();

  try {
    await loadConfig();
    await loadUrls();
  } catch (err) {
    toast(`初始化失败: ${err.message}`, 'err');
  }
  await refreshState();
  const route = routeFromHash();
  if (route.path) S.filePath = route.path;
  goto(route.page, route.section, true);

  window.addEventListener('hashchange', () => {
    const next = routeFromHash();
    if (next.page === S.page && (!next.section || next.section === S.section)
        && (!next.path || next.path === S.filePath)) return;
    if (next.path) S.filePath = next.path;
    goto(next.page, next.section, true);
  });

  setInterval(() => { if (S.page === 'dashboard') refreshState(); }, 5000);
  setInterval(() => { if (S.page === 'urls') loadUrls(); }, 30000);
  pollJobs(true);   // 刷新页面后继续跟踪仍在跑的后处理任务
  S.initialising = false;
}

document.addEventListener('DOMContentLoaded', init);
