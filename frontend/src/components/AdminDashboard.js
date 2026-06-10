import React, { useState, useEffect, useCallback } from 'react';
import { UserButton } from '@clerk/clerk-react';
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis,
  Tooltip, ResponsiveContainer, Legend, AreaChart, Area, CartesianGrid
} from 'recharts';
import {
  LayoutDashboard, Inbox, Wrench, RefreshCw,
  ChevronLeft, ChevronRight, Check, Clock, EyeOff, Eye,
  AlertCircle, AlertTriangle, ThumbsUp, ThumbsDown, Activity,
  ChevronDown, X, Save, Shield, CheckCheck, Layers, Trash, Copy, Download,
  MessageSquare, AlertOctagon, BookX, BrainCircuit, Bot, Ghost, History, MessageCircleQuestion, Skull, HelpCircle,
  BookOpen, Pencil, Plus, Search, Menu, Cpu, Lock, Zap, Sliders, ToggleLeft, ToggleRight, ShieldAlert
} from 'lucide-react';
import { getAdminStats, getAdminFeedbacks, updateFeedbackStatus, bulkResolveFeedbacks, deleteFeedback, getDictionaryItems, createDictionaryItem, updateDictionaryItem, deleteDictionaryItem, getSystemSettings, updateSystemSettings, getUnsafeLogs, getUnsafeStats, deleteUnsafeLog, clearUnsafeLogs, getUnsafeUsers, toggleBanUser, refreshSuggestionCache } from '../services/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './AdminDashboard.css';

const TAG_LABELS = {
  wrong_medical_info: 'Sai kiến thức y khoa',
  ignored_allergy: 'Bỏ qua Dị ứng/Tiền sử',
  off_topic: 'Lan man / Lạc đề',
  irrelevant_source: 'Nguồn không liên quan',
  too_technical: 'Quá nhiều từ chuyên môn',
  cold_tone: 'Giọng điệu vô cảm',
  hallucination: 'Bịa đặt thông tin',
  outdated_info: 'Thông tin lỗi thời',
  too_vague: 'Trả lời chung chung',
  dangerous_advice: 'Tư vấn nguy hiểm',
  other: 'Khác',
};

const getTagConfig = (tagKey) => {
  const icons = {
    wrong_medical_info: <Activity size={20} className="tag-icon" />,
    ignored_allergy: <AlertTriangle size={20} className="tag-icon" />,
    off_topic: <MessageCircleQuestion size={20} className="tag-icon" />,
    irrelevant_source: <BookX size={20} className="tag-icon" />,
    too_technical: <BrainCircuit size={20} className="tag-icon" />,
    cold_tone: <Bot size={20} className="tag-icon" />,
    hallucination: <Ghost size={20} className="tag-icon" />,
    outdated_info: <History size={20} className="tag-icon" />,
    too_vague: <HelpCircle size={20} className="tag-icon" />,
    dangerous_advice: <Skull size={20} className="tag-icon" />,
    other: <MessageSquare size={20} className="tag-icon" />,
  };
  return {
    label: TAG_LABELS[tagKey] || tagKey,
    icon: icons[tagKey] || <MessageSquare size={20} className="tag-icon" />
  };
};

const PIE_COLORS = [
  '#526df8', '#3ecf8e', '#ff6b6b', '#ffa94d',
  '#a78bfa', '#38bdf8', '#f472b6', '#fb923c',
  '#34d399', '#e879f9',
];

const STATUS_CONFIG = {
  pending: { label: 'Chờ xử lý', icon: <Clock size={13} />, className: 'status-pending' },
  resolved: { label: 'Đã xử lý', icon: <Check size={13} />, className: 'status-resolved' },
  ignored: { label: 'Bỏ qua', icon: <EyeOff size={13} />, className: 'status-ignored' },
};

function MetricCard({ icon, label, value, sub, accent, trend }) {
  const isUp = trend && trend.startsWith('+');
  return (
    <div className={`metric-card ${accent ? `accent-${accent}` : ''}`}>
      <div className="metric-icon">{icon}</div>
      <div className="metric-body">
        <div className="metric-value-row">
          <div className="metric-value">{value ?? '—'}</div>
          {trend && (
            <div className={`metric-trend ${isUp ? 'up' : 'down'}`}>
              {trend}
            </div>
          )}
        </div>
        <div className="metric-label">{label}</div>
        {sub && <div className="metric-sub">{sub}</div>}
      </div>
    </div>
  );
}

const CustomAreaTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="custom-tooltip">
        <p className="tooltip-label">{`⏱ Khung ${label}`}</p>
        <p className="tooltip-value">{`Truy vấn: ${payload[0].value}`}</p>
      </div>
    );
  }
  return null;
};

function TabSafetyMonitor() {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [riskUsers, setRiskUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filterCategory, setFilterCategory] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [showRiskUsersModal, setShowRiskUsersModal] = useState(false);
  const [logToDelete, setLogToDelete] = useState(null);
  const [userToBan, setUserToBan] = useState(null);
  const [selectedSafetyLog, setSelectedSafetyLog] = useState(null);
  const [isActionProcessing, setIsActionProcessing] = useState(false);

  const CATEGORIES = ['SELF_HARM', 'ILLEGAL_DRUGS', 'HATE_SPEECH', 'ILLEGAL_PRACTICE', 'OTHER'];
  const CATEGORY_COLORS = {
    'SELF_HARM': '#ef4444',
    'ILLEGAL_DRUGS': '#f97316',
    'HATE_SPEECH': '#eab308',
    'ILLEGAL_PRACTICE': '#a855f7',
    'OTHER': '#64748b'
  };
  const CATEGORY_LABELS = {
    'SELF_HARM': 'Tự hại',
    'ILLEGAL_DRUGS': 'Chất cấm',
    'HATE_SPEECH': 'Thù ghét',
    'ILLEGAL_PRACTICE': 'Bất hợp pháp',
    'OTHER': 'Khác'
  };

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const logsData = await getUnsafeLogs(page, 4, filterCategory || null, searchQuery || null);
      setLogs(logsData.logs || []);
      setTotalPages(Math.ceil((logsData.total || 0) / 4));
    } catch (e) {
      console.error('Lỗi lấy logs:', e);
    } finally {
      setLoading(false);
    }
  }, [page, filterCategory, searchQuery]);

  const fetchStats = useCallback(async () => {
    try {
      const [statsData, usersData] = await Promise.all([getUnsafeStats(), getUnsafeUsers()]);
      setStats(statsData);
      setRiskUsers(usersData.users || []);
    } catch (e) {
      console.error('Lỗi lấy stats:', e);
    }
  }, []);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);
  useEffect(() => { fetchStats(); }, [fetchStats]);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    setSearchQuery(searchInput);
  };

  const confirmDeleteLog = async () => {
    if (!logToDelete || isActionProcessing) return;
    setIsActionProcessing(true);
    try {
      await deleteUnsafeLog(logToDelete.id || logToDelete._id);
      setLogToDelete(null);
      fetchLogs();
      fetchStats();
    } catch (e) {
      console.error('Xóa log thất bại:', e);
    } finally {
      setIsActionProcessing(false);
    }
  };

  const handleClearAll = async () => {
    if (isActionProcessing) return;
    setIsActionProcessing(true);
    try {
      await clearUnsafeLogs();
      setShowClearConfirm(false);
      setLogs([]);
      fetchStats();
    } catch (e) {
      console.error('Xóa tất cả thất bại:', e);
    } finally {
      setIsActionProcessing(false);
    }
  };

  const confirmBanToggle = async () => {
    if (!userToBan || isActionProcessing) return;
    setIsActionProcessing(true);
    try {
      await toggleBanUser(userToBan.user_id);
      setUserToBan(null);
      fetchStats();
    } catch (e) {
      console.error('Cấm user thất bại:', e);
    } finally {
      setIsActionProcessing(false);
    }
  };

  const handleExportCSV = () => {
    if (logs.length === 0) return;
    const headers = ['Thời gian', 'Câu hỏi', 'Nhóm', 'Lý do', 'User ID'];
    const rows = logs.map(l => [
      l.timestamp ? new Date(l.timestamp).toLocaleString('vi-VN') : '',
      `"${(l.query || '').replace(/"/g, '""')}"`,
      l.category || '',
      `"${(l.reason || '').replace(/"/g, '""')}"`,
      l.user_id || ''
    ]);
    const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `unsafe_logs_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const pieData = stats?.by_category ? Object.keys(stats.by_category).map((key) => ({
    name: CATEGORY_LABELS[key] || key,
    value: stats.by_category[key],
    originalKey: key
  })) : [];

  const trendData = stats?.recent_trend || [];

  if (loading && logs.length === 0 && !stats) {
    return <div className="tuning-loading"><RefreshCw size={24} className="spin" /><span>Đang tải...</span></div>;
  }

  return (
    <div className="tab-safety">
      <div className="tuning-grid safety-grid">

        {/* === CỘT TRÁI: Biểu đồ & Top Risk Users === */}
        <div className="tuning-column" style={{ display: 'flex', flexDirection: 'column', gap: 24, height: '100%' }}>

          {/* Biểu đồ */}
          <div className="tuning-card tuning-card--info" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div className="tuning-card-header">
              <ShieldAlert size={18} />
              <h3>Thống kê Rủi ro</h3>
            </div>
            {stats && (
              <div className="safety-stats-container" style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div className="safety-total" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                  <span>Tổng số truy vấn bị chặn:</span>
                  <span style={{ fontSize: 28, fontWeight: 700, color: '#ef4444' }}>{stats.total_unsafe}</span>
                </div>
                {/* Pie Chart */}
                <div style={{ height: 220, marginTop: 8 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={75} paddingAngle={5} dataKey="value">
                        {pieData.map((entry, i) => (
                          <Cell key={`cell-${i}`} fill={CATEGORY_COLORS[entry.originalKey] || '#999'} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value, name) => [value, name]} labelStyle={{ display: 'none' }} />
                      <Legend verticalAlign="bottom" height={36} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                {/* Line Chart - Xu hướng 7 ngày */}
                {trendData.length > 0 && (
                  <>
                    <h4 style={{ margin: '16px 0 8px', fontSize: 13, color: 'var(--med-text-sub)' }}>Xu hướng 7 ngày qua</h4>
                    <div style={{ height: 150 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={trendData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--med-border)" />
                          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => {
                            if (!d) return '';
                            const p = d.split('-');
                            return p.length === 3 ? `${p[2]}/${p[1]}` : d;
                          }} />
                          <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                          <Tooltip labelFormatter={(label) => {
                            if (!label) return '';
                            const p = label.split('-');
                            return 'Ngày ' + (p.length === 3 ? `${p[2]}/${p[1]}` : label);
                          }} />
                          <Area type="monotone" dataKey="count" stroke="#ef4444" fill="#ef444420" strokeWidth={2} name="Vi phạm" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </>
                )}

                {/* Nút mở Modal danh sách User */}
                <button
                  className="btn-danger"
                  style={{ width: '100%', marginTop: 16, display: 'flex', justifyContent: 'center', background: 'var(--med-bg)', color: '#ef4444', border: '1px solid #ef4444' }}
                  onClick={() => setShowRiskUsersModal(true)}
                >
                  <AlertTriangle size={16} /> Xem danh sách Tài khoản vi phạm ({riskUsers.length})
                </button>
              </div>
            )}
          </div>
        </div>

        {/* === CỘT PHẢI: Bảng Logs === */}
        <div className="tuning-column" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div className="tuning-card tuning-card--rag" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div className="tuning-card-header flex-between" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <History size={18} />
                <h3 style={{ margin: 0 }}>Nhật ký truy vấn</h3>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button className="icon-btn" onClick={handleExportCSV} data-tooltip="Xuất CSV"><Download size={14} /></button>
                <button className="icon-btn" onClick={() => { fetchLogs(); fetchStats(); }} data-tooltip="Làm mới"><RefreshCw size={14} /></button>
                <button className="icon-btn" onClick={() => setShowClearConfirm(true)} data-tooltip="Xóa tất cả" style={{ color: '#ef4444' }}><Trash size={14} /></button>
              </div>
            </div>

            {/* Toolbar: Filter + Search */}
            <div className="safety-toolbar">
              <select
                value={filterCategory}
                onChange={(e) => { setFilterCategory(e.target.value); setPage(1); }}
                className="safety-filter-select"
              >
                <option value="">Tất cả nhóm</option>
                {CATEGORIES.map(c => <option key={c} value={c}>{CATEGORY_LABELS[c] || c}</option>)}
              </select>
              <form onSubmit={handleSearch} style={{ display: 'flex', gap: 6, flex: 1 }}>
                <input
                  type="text"
                  placeholder="Tìm kiếm nội dung..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="safety-search-input"
                />
                <button type="submit" className="icon-btn"><Search size={14} /></button>
                {searchQuery && <button type="button" className="icon-btn" onClick={() => { setSearchInput(''); setSearchQuery(''); setPage(1); }}><X size={14} /></button>}
              </form>
            </div>

            {/* Logs List */}
            <div className="safety-logs-list">
              {logs.length === 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, padding: 32, textAlign: 'center', color: 'var(--med-text-sub)' }}>
                  <Shield size={32} style={{ marginBottom: 8, opacity: 0.4 }} />
                  <p>Không có dữ liệu nào{filterCategory ? ` cho nhóm ${CATEGORY_LABELS[filterCategory]}` : ''}{searchQuery ? ` khớp "${searchQuery}"` : ''}.</p>
                </div>
              ) : logs.map((log, i) => (
                <div key={log.id || log._id || i} className="safety-log-item">
                  <div className="log-content" style={{ flex: 1, minWidth: 0, paddingRight: 16 }}>
                    <div className="log-time" style={{ fontSize: 12, color: 'var(--med-text-sub)', marginBottom: 6 }}>
                      {log.timestamp ? new Date(log.timestamp).toLocaleString('vi-VN') : 'Unknown'}
                    </div>
                    <div className="log-query" data-tooltip={log.query}>"{log.query}"</div>
                    <div className="log-reason" data-tooltip={log.reason}><strong>Lý do:</strong> {log.reason}</div>
                  </div>
                  <div className="log-actions" style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
                    <span className="tag-chip" style={{
                      padding: '4px 10px', borderRadius: 4, fontWeight: 600, fontSize: 12,
                      backgroundColor: (CATEGORY_COLORS[log.category] || '#999') + '20',
                      color: CATEGORY_COLORS[log.category] || '#999',
                      border: `1px solid ${(CATEGORY_COLORS[log.category] || '#999')}40`
                    }}>{CATEGORY_LABELS[log.category] || log.category}</span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button className="icon-btn" onClick={() => setSelectedSafetyLog(log)} data-tooltip="Xem chi tiết" style={{ color: 'var(--med-blue, #6366f1)', padding: 4 }}>
                        <Eye size={16} />
                      </button>
                      <button className="icon-btn" onClick={() => setLogToDelete(log)} data-tooltip="Xóa" style={{ color: '#ef4444', padding: 4 }}><Trash size={16} /></button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Phân trang */}
            <div className="dict-pagination" style={{ marginTop: 20, visibility: totalPages > 1 ? 'visible' : 'hidden' }}>
              <button disabled={page === 1} onClick={() => setPage(page - 1)}><ChevronLeft size={16} /></button>
              <span style={{ fontSize: 14 }}>Trang {page} / {totalPages || 1}</span>
              <button disabled={page === totalPages} onClick={() => setPage(page + 1)}><ChevronRight size={16} /></button>
            </div>
          </div>
        </div>
      </div>

      {/* Modal xác nhận xóa tất cả */}
      {showClearConfirm && (
        <div className="modal-overlay" onClick={() => !isActionProcessing && setShowClearConfirm(false)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <AlertTriangle size={32} style={{ color: '#ef4444', marginBottom: 12 }} />
            <h3>Xác nhận xóa tất cả?</h3>
            <p style={{ color: 'var(--med-text-sub)', margin: '8px 0 20px' }}>Hành động này sẽ xóa vĩnh viễn toàn bộ dữ liệu unsafe logs và không thể hoàn tác.</p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button className="btn-cancel" onClick={() => setShowClearConfirm(false)} disabled={isActionProcessing}>Hủy</button>
              <button className="btn-danger" onClick={handleClearAll} disabled={isActionProcessing}>
                <Trash size={14} /> {isActionProcessing ? 'Đang xóa...' : 'Xóa tất cả'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal hiển thị danh sách User rủi ro */}
      {showRiskUsersModal && (
        <div className="modal-overlay" onClick={() => !isActionProcessing && setShowRiskUsersModal(false)}>
          <div className="confirm-modal" style={{ maxWidth: 650, padding: '24px 24px 16px', textAlign: 'left' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}><AlertTriangle size={20} color="#ef4444" /> Tài khoản Rủi ro</h3>
              <button className="icon-btn" onClick={() => setShowRiskUsersModal(false)} disabled={isActionProcessing}><X size={20} /></button>
            </div>

            {riskUsers.length === 0 ? (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--med-text-sub)', fontSize: 14 }}>
                <Shield size={40} style={{ marginBottom: 12, opacity: 0.3 }} />
                <p>Chưa có tài khoản nào vi phạm hệ thống.</p>
              </div>
            ) : (
              <div style={{ maxHeight: 450, overflowY: 'auto' }}>
                <table className="safety-users-table">
                  <thead>
                    <tr>
                      <th>Email</th>
                      <th style={{ textAlign: 'center' }}>Vi phạm</th>
                      <th style={{ textAlign: 'center' }}>Nhóm</th>
                      <th style={{ textAlign: 'center' }}>Hành động</th>
                    </tr>
                  </thead>
                  <tbody>
                    {riskUsers.map((u, i) => (
                      <tr key={i} className={u.is_banned ? 'banned-row' : ''}>
                        <td>
                          <div style={{ fontSize: 13, fontWeight: 500, wordBreak: 'break-all' }}>{u.email || 'N/A'}</div>
                          <div style={{ fontSize: 11, color: 'var(--med-text-sub)' }}>Lần cuối: {u.last_violation ? new Date(u.last_violation).toLocaleDateString('vi-VN') : '?'}</div>
                        </td>
                        <td style={{ textAlign: 'center', fontWeight: 700, fontSize: 18, color: u.count >= 5 ? '#ef4444' : u.count >= 3 ? '#f97316' : 'inherit' }}>{u.count}</td>
                        <td style={{ textAlign: 'center' }}>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, justifyContent: 'center' }}>
                            {(u.categories || []).map((c, ci) => (
                              <span key={ci} style={{
                                padding: '1px 6px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                                backgroundColor: (CATEGORY_COLORS[c] || '#999') + '20',
                                color: CATEGORY_COLORS[c] || '#999'
                              }}>{CATEGORY_LABELS[c] || c}</span>
                            ))}
                          </div>
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <button
                            className={`btn-ban ${u.is_banned ? 'banned' : ''}`}
                            onClick={() => !isActionProcessing && setUserToBan(u)}
                            data-tooltip={u.is_banned ? 'Mở cấm' : 'Cấm tài khoản'}
                            disabled={isActionProcessing}
                          >
                            {u.is_banned ? <><Lock size={12} /> Đã cấm</> : <><ShieldAlert size={12} /> Cấm</>}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal xác nhận xóa log đơn lẻ */}
      {logToDelete && (
        <div className="modal-overlay" style={{ zIndex: 10010 }} onClick={() => !isActionProcessing && setLogToDelete(null)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <AlertTriangle size={32} style={{ color: '#ef4444', marginBottom: 12 }} />
            <h3>Xác nhận xóa nhật ký?</h3>
            <p style={{ color: 'var(--med-text-sub)', margin: '8px 0 20px', lineHeight: '1.5' }}>
              Bạn có chắc chắn muốn xóa nhật ký truy vấn này?<br />
              <strong style={{ color: 'var(--med-text-main)' }}>"{logToDelete.query}"</strong>
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button className="btn-cancel" onClick={() => setLogToDelete(null)} disabled={isActionProcessing}>Hủy</button>
              <button className="btn-danger" onClick={confirmDeleteLog} disabled={isActionProcessing}>
                <Trash size={14} /> {isActionProcessing ? 'Đang xóa...' : 'Xóa'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal xác nhận cấm/mở cấm tài khoản */}
      {userToBan && (
        <div className="modal-overlay" style={{ zIndex: 10020 }} onClick={() => !isActionProcessing && setUserToBan(null)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <ShieldAlert size={32} style={{ color: userToBan.is_banned ? '#10b981' : '#ef4444', marginBottom: 12 }} />
            <h3>{userToBan.is_banned ? 'Xác nhận mở cấm tài khoản?' : 'Xác nhận cấm tài khoản?'}</h3>
            <p style={{ color: 'var(--med-text-sub)', margin: '8px 0 20px', lineHeight: '1.5' }}>
              Bạn có chắc chắn muốn {userToBan.is_banned ? 'mở cấm' : 'cấm'} tài khoản:<br />
              <strong style={{ color: 'var(--med-text-main)' }}>{userToBan.email || 'N/A'}</strong>?
              {!userToBan.is_banned && (
                <span style={{ display: 'block', marginTop: 8, fontSize: 12, color: '#f59e0b' }}>
                  Lưu ý: Tài khoản này sẽ không thể tiếp tục gửi câu hỏi đến hệ thống.
                </span>
              )}
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button className="btn-cancel" onClick={() => setUserToBan(null)} disabled={isActionProcessing}>Hủy</button>
              <button
                className={userToBan.is_banned ? 'btn-save' : 'btn-danger'}
                onClick={confirmBanToggle}
                disabled={isActionProcessing}
              >
                {userToBan.is_banned ? (
                  isActionProcessing ? 'Đang xử lý...' : <><Lock size={12} /> Mở cấm</>
                ) : (
                  isActionProcessing ? 'Đang xử lý...' : <><ShieldAlert size={12} /> Xác nhận cấm</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal hiển thị chi tiết logs */}
      {selectedSafetyLog && (
        <div className="modal-overlay" style={{ zIndex: 10005 }} onClick={() => setSelectedSafetyLog(null)}>
          <div className="confirm-modal" style={{ maxWidth: 550, padding: '28px', textAlign: 'left', borderRadius: 16 }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, borderBottom: '1px solid var(--med-border)', paddingBottom: 12 }}>
              <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--med-blue, #6366f1)', fontSize: 18 }}>
                <ShieldAlert size={20} /> Chi tiết Truy vấn Rủi ro
              </h3>
              <button className="icon-btn" onClick={() => setSelectedSafetyLog(null)}><X size={20} /></button>
            </div>

            <div style={{ maxHeight: '60vh', overflowY: 'auto', paddingRight: 4, display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--med-text-sub)', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase' }}>Thời gian ghi nhận</label>
                <div style={{ fontSize: 14, color: 'var(--med-text-main)', background: 'var(--med-bg)', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--med-border)' }}>
                  {selectedSafetyLog.timestamp ? new Date(selectedSafetyLog.timestamp).toLocaleString('vi-VN') : 'Không rõ'}
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--med-text-sub)', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase' }}>Phân loại rủi ro</label>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <span style={{
                    padding: '6px 12px', borderRadius: 6, fontWeight: 600, fontSize: 13,
                    backgroundColor: (CATEGORY_COLORS[selectedSafetyLog.category] || '#999') + '20',
                    color: CATEGORY_COLORS[selectedSafetyLog.category] || '#999',
                    border: `1px solid ${(CATEGORY_COLORS[selectedSafetyLog.category] || '#999')}40`
                  }}>{CATEGORY_LABELS[selectedSafetyLog.category] || selectedSafetyLog.category}</span>
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--med-text-sub)', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase' }}>Nội dung câu hỏi (Query)</label>
                <div style={{ fontSize: 14, color: 'var(--med-text-main)', background: 'var(--med-bg)', padding: '12px 14px', borderRadius: 8, border: '1px solid var(--med-border)', lineHeight: '1.6', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 150, overflowY: 'auto' }}>
                  "{selectedSafetyLog.query || 'Không có nội dung'}"
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--med-text-sub)', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase' }}>Phân tích lý do (Reason)</label>
                <div style={{ fontSize: 14, color: 'var(--med-text-main)', background: 'var(--med-bg)', padding: '12px 14px', borderRadius: 8, border: '1px solid var(--med-border)', lineHeight: '1.6', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 200, overflowY: 'auto' }}>
                  {selectedSafetyLog.reason || 'Không có phân tích lý do.'}
                </div>
              </div>

              {(selectedSafetyLog.user_id || selectedSafetyLog.session_id) && (
                <div style={{ display: 'flex', gap: 16 }}>
                  {selectedSafetyLog.user_id && (
                    <div style={{ flex: 1 }}>
                      <label style={{ display: 'block', fontSize: 11, color: 'var(--med-text-sub)', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase' }}>User ID</label>
                      <div style={{ fontSize: 12, color: 'var(--med-text-sub)', background: 'var(--med-bg)', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--med-border)', overflowX: 'auto', whiteSpace: 'nowrap' }}>
                        {selectedSafetyLog.user_id}
                      </div>
                    </div>
                  )}
                  {selectedSafetyLog.session_id && (
                    <div style={{ flex: 1 }}>
                      <label style={{ display: 'block', fontSize: 11, color: 'var(--med-text-sub)', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase' }}>Session ID</label>
                      <div style={{ fontSize: 12, color: 'var(--med-text-sub)', background: 'var(--med-bg)', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--med-border)', overflowX: 'auto', whiteSpace: 'nowrap' }}>
                        {selectedSafetyLog.session_id}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--med-border)' }}>
              <button className="btn-cancel" style={{ padding: '10px 20px', borderRadius: 8 }} onClick={() => setSelectedSafetyLog(null)}>Đóng</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TabOverview({ stats, onRefresh, loading }) {
  if (loading) return <div className="admin-loading"><RefreshCw size={20} className="spin" /> Đang tải số liệu...</div>;
  if (!stats) return <div className="admin-empty">Không có dữ liệu. <button onClick={onRefresh} className="link-btn">Tải lại</button></div>;

  const tagChartData = (stats.tag_distribution || []).map((d) => ({
    name: TAG_LABELS[d.tag] || d.tag,
    value: d.count,
  }));

  const trendData = (stats.trend_7days || []).map((d) => {
    const p = d.date.split('-');
    const formatted = p.length === 3 ? `${p[2]}/${p[1]}` : d.date;
    return {
      date: formatted,
      Like: d.like,
      Dislike: d.dislike,
    };
  });

  const hourlyData = (stats.hourly_usage || []).map((d) => ({
    hour: `${String(d.hour).padStart(2, '0')}h`,
    'Lượt hỏi': d.count,
  }));

  // Custom Donut label
  const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
    if (percent < 0.05) return null;
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);
    return (
      <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={600}>
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  return (
    <div className="tab-overview">
      {/* Header Row with Refresh Button */}
      <div className="tab-header-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: 'var(--med-text-main)' }}>Tổng quan hệ thống</h2>
        <button
          className="icon-btn"
          onClick={onRefresh}
          disabled={loading}
          data-tooltip="Làm mới số liệu"
        >
          <RefreshCw size={16} className={loading ? "spin" : ""} />
        </button>
      </div>

      {/* Row 1: KPI Cards */}
      <div className="metric-grid">
        <MetricCard icon={<Activity size={20} />} label="Tổng phản hồi" value={stats.total} trend="+12%" />
        <MetricCard icon={<ThumbsUp size={20} />} label="CSAT (% Hài lòng)" value={`${stats.csat ?? 0}%`} accent="green" trend="+5%" />
        <MetricCard icon={<ThumbsUp size={20} />} label="Tổng Like" value={stats.total_like} accent="green" trend="+8%" />
        <MetricCard icon={<ThumbsDown size={20} />} label="Tổng Dislike" value={stats.total_dislike} accent="red" trend="-2%" />
        <MetricCard
          icon={<AlertCircle size={20} />}
          label="Lỗi chưa xử lý"
          value={stats.total_pending}
          sub="Dislike · Pending"
          accent="critical"
        />
      </div>

      {/* Row 2: Core Charts */}
      <div className="charts-row">
        <div className="chart-card">
          <h3 className="chart-title">Phân bổ lỗi (Dislike Tags)</h3>
          {tagChartData.length === 0 ? (
            <div className="chart-empty">Chưa có dữ liệu lỗi</div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', height: 260 }}>
              <div style={{ flex: 1, position: 'relative', height: '100%', minWidth: 0 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={tagChartData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%" cy="50%"
                      innerRadius={65}
                      outerRadius={100}
                      labelLine={false}
                      label={renderCustomLabel}
                    >
                      {tagChartData.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(val, name) => [val, name]} labelStyle={{ display: 'none' }} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{
                  position: 'absolute', top: '50%', left: '50%',
                  transform: 'translate(-50%, -50%)',
                  textAlign: 'center', pointerEvents: 'none'
                }}>
                  <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--med-text-main)', lineHeight: 1 }}>
                    {tagChartData.reduce((acc, curr) => acc + curr.value, 0)}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--med-text-sub)', marginTop: 4 }}>
                    Tổng lỗi
                  </div>
                </div>
              </div>
              <div style={{ width: '190px', flexShrink: 0, paddingLeft: 10 }}>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: '12.5px', lineHeight: '28px' }}>
                  {tagChartData.map((entry, index) => (
                    <li key={`legend-${index}`} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: PIE_COLORS[index % PIE_COLORS.length], display: 'inline-block', flexShrink: 0 }}></span>
                      <span style={{ color: 'var(--med-text-sub)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} data-tooltip={entry.name}>{entry.name}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>

        <div className="chart-card">
          <h3 className="chart-title">Xu hướng 7 ngày gần nhất</h3>
          {trendData.length === 0 ? (
            <div className="chart-empty">Chưa có dữ liệu</div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={trendData} barSize={20} barGap={4} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--med-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} dy={10} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: 'rgba(0,0,0,0.04)' }} labelFormatter={(label) => 'Ngày ' + label} />
                <Legend iconSize={10} iconType="circle" wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                <Bar dataKey="Like" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Dislike" fill="#ef4444" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Row 3: Hourly Usage */}
      <div className="chart-card chart-card-full">
        <div className="chart-card-header">
          <div>
            <h3 className="chart-title" style={{ marginBottom: '2px' }}>Lưu lượng truy vấn theo Khung giờ</h3>
            <p className="chart-subtitle">Phân bố số lượng câu hỏi tích lũy theo từng giờ trong ngày (0h – 23h)</p>
          </div>
        </div>
        {hourlyData.length === 0 ? (
          <div className="chart-empty">Chưa có dữ liệu</div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={hourlyData} margin={{ top: 8, right: 16, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="hourlyGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <XAxis dataKey="hour" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} interval={1} dy={10} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomAreaTooltip />} cursor={{ stroke: '#6366f1', strokeWidth: 1, strokeDasharray: '4 2' }} />
              <Area
                type="monotone"
                dataKey="Lượt hỏi"
                stroke="#6366f1"
                strokeWidth={2.5}
                fill="url(#hourlyGradient)"
                dot={{ r: 3, fill: '#6366f1', strokeWidth: 0 }}
                activeDot={{ r: 5 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

function DetailPanel({ item, onClose, onSave, onDelete, onCopy }) {
  const [status, setStatus] = useState(item?.status || 'pending');
  const [notes, setNotes] = useState(item?.admin_notes || '');
  const [saving, setSaving] = useState(false);
  const [expandedSource, setExpandedSource] = useState(null);

  useEffect(() => {
    if (item) {
      setStatus(item.status || 'pending');
      setNotes(item.admin_notes || '');
      setExpandedSource(null);
    }
  }, [item]);

  if (!item) {
    return (
      <div className="detail-panel empty-state fade-in">
        <div className="empty-state-content">
          <Layers size={48} className="empty-icon" />
          <p>Hãy chọn một truy vấn từ danh sách bên trái để tiếp tục rà soát</p>
        </div>
      </div>
    );
  }

  const handleSave = async () => {
    setSaving(true);
    await onSave(item.id, { status, admin_notes: notes });
    setSaving(false);
  };

  return (
    <div className="detail-panel fade-in">
      <div className="detail-header">
        <div className="detail-header-left">
          <Layers size={18} className="detail-header-icon" />
          <h3>Không Gian Đối Chiếu RAG</h3>
        </div>
        <button className="icon-btn" onClick={onClose}><X size={18} /></button>
      </div>

      <div className="detail-scroll detail-cards-layout">

        {/* Cột Trái: Chat & RAG Context */}
        <div className="detail-card chat-context-card">
          <h4 className="card-title">Nội dung Giao tiếp</h4>
          <div className="chat-bubbles-container">
            <div className="chat-bubble user-bubble">
              <div className="bubble-label">Truy vấn (Query)</div>
              <div className="bubble-content flex-between">
                <span>{item.query || <em>Không có</em>}</span>
                {item.query && (
                  <button className="icon-copy" onClick={() => onCopy(item.query)} data-tooltip="Sao chép truy vấn">
                    <Copy size={14} />
                  </button>
                )}
              </div>
            </div>
            <div className="chat-bubble ai-bubble">
              <div className="bubble-label">Câu trả lời AI</div>
              <div className="bubble-content">
                {item.ai_response ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {item.ai_response}
                  </ReactMarkdown>
                ) : (
                  <em>Không có</em>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Cột Phải: Action Board */}
        <div className="detail-card action-board-card">
          <h4 className="card-title">Xử lý Phản hồi</h4>

          {item.retrieved_sources && item.retrieved_sources.length > 0 && (
            <div className="action-section rag-sources-action">
              <label className="action-label">Nguồn dữ liệu truy xuất ({item.retrieved_sources.length})</label>
              <div className="sources-wrap">
                {item.retrieved_sources.map((src, i) => {
                  const doc_id = typeof src === 'string' ? src : src.doc_id;
                  const isExpanded = expandedSource === i;

                  return (
                    <span
                      key={i}
                      className={`source-chip ${isExpanded ? 'active' : ''}`}
                      onClick={() => setExpandedSource(isExpanded ? null : i)}
                    >
                      {doc_id}
                    </span>
                  );
                })}
              </div>

              {expandedSource !== null && item.retrieved_sources[expandedSource] && (
                <div className="source-detail-container fade-in">
                  {(() => {
                    const src = item.retrieved_sources[expandedSource];
                    const isString = typeof src === 'string';

                    if (isString) {
                      return (
                        <div className="source-detail-box">
                          <em>(Không có nội dung chi tiết cho nguồn này)</em>
                        </div>
                      );
                    }
                    return (
                      <div className="source-detail-box">
                        <div className="source-detail-row">
                          <strong>Câu hỏi:</strong> {src.question}
                        </div>
                        <div className="source-detail-row">
                          <strong>Trích xuất:</strong> {src.answer}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          )}

          {item.reason_tags && item.reason_tags.length > 0 && (
            <div className="action-section">
              <label className="action-label">Phân Loại Lỗi</label>
              <div className="tags-wrap-action">
                {item.reason_tags.map((tag, i) => (
                  <span key={i} className="tag-chip error-chip">
                    {getTagConfig(tag).icon} <span style={{ marginLeft: '4px' }}>{getTagConfig(tag).label}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {item.text_feedback && (
            <div className="action-section">
              <label className="action-label">Mô tả thêm của user</label>
              <div className="user-note-block">{item.text_feedback}</div>
            </div>
          )}

          {item.rating !== 1 && (
            <>
              <div className="action-section">
                <label className="action-label">Cập nhật trạng thái</label>
                <div className="status-select-wrap">
                  {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
                    <button
                      key={key}
                      className={`status-choice ${status === key ? 'selected' : ''}`}
                      onClick={() => setStatus(key)}
                    >
                      {cfg.icon} {cfg.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="action-section">
                <label className="action-label">Ghi chú Admin</label>
                <textarea
                  className="admin-notes-input"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="VD: Đã điều chỉnh tham số..."
                  rows={4}
                />
              </div>
            </>
          )}

        </div>
      </div>

      {/* Action Footer */}
      <div className="action-board-footer">
        <button className="btn-delete" onClick={() => onDelete(item.id)} disabled={saving}>
          <Trash size={15} /> Xóa
        </button>
        <div className="footer-main-actions">
          <button className="btn-cancel" onClick={onClose}>Đóng</button>
          {item.rating !== 1 && (
            <button className="btn-save" onClick={handleSave} disabled={saving}>
              {saving ? <RefreshCw size={15} className="spin" /> : <Save size={15} />}
              {saving ? 'Đang lưu...' : 'Lưu Hồ Sơ'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function DataPane({
  title,
  items,
  loading,
  page,
  totalPages,
  setPage,
  selectedId,
  onRowClick,
  toolbar,
  isMaster,
  viewMode
}) {
  return (
    <div className={`table-pane ${isMaster ? 'compact-master-pane' : 'full-width-pane'}`}>
      <div className="pane-header">
        <div className="pane-header-left">
          <h3>{title}</h3>
          <span className="count-badge">{items.length}</span>
        </div>
        {toolbar}
      </div>

      {loading ? (
        <div className="admin-loading"><RefreshCw size={18} className="spin" /> Đang tải...</div>
      ) : items.length === 0 ? (
        <div className="admin-empty">
          <AlertOctagon size={32} className="empty-icon" />
          <p>Không có dữ liệu</p>
        </div>
      ) : (
        <div className="table-scroll-wrap">
          {isMaster ? (
            <div className="compact-list">
              {items.map(item => (
                <div
                  key={item.id}
                  className={`compact-card ${selectedId === item.id ? 'selected' : ''} ${item.rating === -1 ? 'is-flagged' : 'is-verified'}`}
                  onClick={() => onRowClick(item)}
                >
                  <div className="compact-card-header">
                    <span className="compact-date">{item.created_at ? new Date(item.created_at).toLocaleDateString('vi-VN') : ''}</span>
                    {item.rating === -1 ? <ThumbsDown size={12} color="#ef4444" /> : <ThumbsUp size={12} color="#10b981" />}
                  </div>
                  <div className="compact-query">{item.query || 'Không có truy vấn'}</div>
                  {item.rating === -1 && item.status && (
                    <div className="compact-status">
                      <span className={`status-badge status-${item.status}`}>
                        {item.status === 'pending' ? 'Chưa xử lý' : item.status === 'resolved' ? 'Đã xử lý' : 'Bỏ qua'}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <table className="feedback-table">
              <thead>
                <tr>
                  <th className="col-rating">Loại</th>
                  <th className="col-query">Truy vấn (Query)</th>
                  {viewMode !== 'verified' && <th className="col-tags">Phân loại lỗi</th>}
                  {viewMode !== 'verified' && <th className="col-status">Trạng thái</th>}
                  <th className="col-date">Ngày tạo</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => {
                  const isCritical = item.status === 'pending' && (item.reason_tags || []).some(t => t === 'wrong_medical_info' || t === 'ignored_allergy' || t === 'dangerous_advice' || t === 'hallucination');
                  return (
                    <tr
                      key={item.id}
                      className={`${selectedId === item.id ? 'row-selected' : ''} ${item.rating === -1 ? 'row-dislike' : 'row-like'} ${isCritical ? 'row-critical' : ''}`}
                      onClick={() => onRowClick(item)}
                    >
                      <td className="col-rating">
                        {item.rating === -1 ? <ThumbsDown className="rating-dislike" size={16} color="#ef4444" /> : <ThumbsUp className="rating-like" size={16} color="#10b981" />}
                      </td>
                      <td className="col-query">
                        <div className="query-preview">{item.query || <em>Không có</em>}</div>
                      </td>
                      {viewMode !== 'verified' && (
                        <td className="col-tags">
                          {item.reason_tags && item.reason_tags.length > 0 ? (
                            <div className="tags-wrap">
                              {item.reason_tags.map(t => {
                                const cfg = getTagConfig(t);
                                return (
                                  <span key={t} className="tag-chip small" data-tooltip={cfg.label} style={{ cursor: 'help' }}>
                                    {cfg.icon}
                                  </span>
                                );
                              })}
                            </div>
                          ) : <span style={{ color: '#9898b0', fontSize: '12px' }}>-</span>}
                        </td>
                      )}
                      {viewMode !== 'verified' && (
                        <td className="col-status">
                          {item.rating === -1 ? (
                            <span className={`status-badge status-${item.status}`}>
                              {item.status === 'pending' ? 'Chưa xử lý' : item.status === 'resolved' ? 'Đã xử lý' : 'Bỏ qua'}
                            </span>
                          ) : <span style={{ color: '#9898b0', fontSize: '12px' }}>-</span>}
                        </td>
                      )}
                      <td className="col-date">
                        {item.created_at ? new Date(item.created_at).toLocaleDateString('vi-VN') : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="pagination">
          <button className="page-btn" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
            <ChevronLeft size={16} />
          </button>
          <span className="page-info">{page} / {totalPages}</span>
          <button className="page-btn" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

function TabFeedbackInbox({ onSaveNote }) {
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [filterTag, setFilterTag] = useState('');
  const [dateRange, setDateRange] = useState('');
  const [viewMode, setViewMode] = useState('all'); // 'all' | 'flagged' | 'verified'

  const [selectedItem, setSelectedItem] = useState(null);
  const [bulkResolving, setBulkResolving] = useState(false);
  const [toast, setToast] = useState(null);
  const [showBulkResolveConfirm, setShowBulkResolveConfirm] = useState(false);
  const [feedbackToDelete, setFeedbackToDelete] = useState(null);

  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, limit: 15 };
      if (filterTag) params.tag = filterTag;
      if (dateRange) params.date_range = dateRange;
      if (viewMode === 'flagged') params.rating = -1;
      if (viewMode === 'verified') params.rating = 1;

      const data = await getAdminFeedbacks(params);
      setItems(data.items || []);
      setTotalPages(data.total_pages || 1);
    } catch (e) {
      console.error('Error loading feedbacks', e);
    } finally {
      setLoading(false);
    }
  }, [page, filterTag, dateRange, viewMode]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  const handleSave = async (id, payload) => {
    setItems(prev => prev.map(item => item.id === id ? { ...item, status: payload.status, admin_notes: payload.admin_notes } : item));

    try {
      await onSaveNote(id, payload);
      setSelectedItem(null);
    } catch (e) {
      fetchItems();
      showToast('Lỗi khi lưu phản hồi', 'error');
    }
  };

  const handleRowClick = (item) => {
    if (selectedItem?.id === item.id) {
      setSelectedItem(null);
    } else {
      setSelectedItem(item);
    }
  };

  const closeDetail = () => {
    setSelectedItem(null);
  };

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    showToast('Đã copy truy vấn vào Clipboard!');
  };

  const handleDelete = async (id) => {
    setFeedbackToDelete(id);
  };

  const handleExportJsonl = async () => {
    try {
      showToast('Đang chuẩn bị dữ liệu xuất...');
      const res = await getAdminFeedbacks({ limit: 10000, rating: 1, date_range: dateRange });
      const exportItems = res.items || [];
      if (exportItems.length === 0) {
        showToast('Không có dữ liệu để xuất', 'error');
        return;
      }

      const jsonl = exportItems.map(item => {
        return JSON.stringify({
          messages: [
            { role: "user", content: item.query || "" },
            { role: "assistant", content: item.ai_response || "" }
          ]
        });
      }).join('\n');

      const blob = new Blob([jsonl], { type: 'application/jsonl' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'verified_dataset.jsonl';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      showToast(`Đã xuất ${exportItems.length} mẫu dữ liệu!`);
    } catch (e) {
      showToast('Lỗi xuất dữ liệu', 'error');
    }
  };

  const isCriticalFilter = filterTag === 'wrong_medical_info' || filterTag === 'ignored_allergy' || filterTag === 'dangerous_advice' || filterTag === 'hallucination';

  const handleBulkResolve = () => {
    const hasPendingNonCritical = items.some(item =>
      item.rating === -1 && item.status === 'pending' &&
      !(item.reason_tags || []).includes('wrong_medical_info') &&
      !(item.reason_tags || []).includes('ignored_allergy') &&
      !(item.reason_tags || []).includes('dangerous_advice') &&
      !(item.reason_tags || []).includes('hallucination')
    );

    if (!hasPendingNonCritical) {
      showToast('Không có phản hồi nào cần xử lý (Hoặc bị chặn bởi Bộ lọc Rỗng)', 'error');
      return;
    }

    setShowBulkResolveConfirm(true);
  };

  const handleBulkResolveConfirm = async () => {
    if (bulkResolving) return;
    setShowBulkResolveConfirm(false);
    setBulkResolving(true);
    try {
      const res = await bulkResolveFeedbacks(filterTag);
      showToast(`Đã Đóng Hồ Sơ thành công ${res.modified_count} phản hồi!`);
      fetchItems();
    } catch (e) {
      showToast('Lỗi xử lý hàng loạt', 'error');
    } finally {
      setBulkResolving(false);
    }
  };

  const isDeepDive = selectedItem !== null;

  return (
    <div className="tab-inbox bifurcated-container">
      {toast && (
        <div className={`admin-toast ${toast.type} fade-in`}>
          {toast.message}
        </div>
      )}

      {/* Unified Filters Header */}
      <div className="unified-toolbar">
        <div className="view-mode-tabs">
          <button className={`view-mode-btn ${viewMode === 'all' ? 'active' : ''}`} onClick={() => { setViewMode('all'); setPage(1); }}>
            Tất cả
          </button>
          <button className={`view-mode-btn ${viewMode === 'flagged' ? 'active' : ''}`} onClick={() => { setViewMode('flagged'); setPage(1); }}>
            Cần Rà Soát
          </button>
          <button className={`view-mode-btn ${viewMode === 'verified' ? 'active' : ''}`} onClick={() => { setViewMode('verified'); setPage(1); }}>
            Đạt Chuẩn
          </button>
        </div>

        <div className="filter-group">
          <select className="filter-select" value={dateRange} onChange={(e) => { setDateRange(e.target.value); setPage(1); }}>
            <option value="">Tất cả thời gian</option>
            <option value="today">Hôm nay</option>
            <option value="7days">7 ngày qua</option>
            <option value="this_month">Tháng này</option>
          </select>
          {viewMode !== 'verified' && (
            <select className="filter-select" value={filterTag} onChange={(e) => { setFilterTag(e.target.value); setPage(1); }}>
              <option value="">Tất cả lỗi (Tags)</option>
              {Object.entries(TAG_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          )}
          {viewMode !== 'verified' && (
            <button
              className="btn-bulk-resolve"
              onClick={handleBulkResolve}
              disabled={isCriticalFilter || bulkResolving}
              data-tooltip={isCriticalFilter ? "Bị khóa đối với lỗi an toàn lâm sàng" : "Đóng Hồ Sơ Hàng Loạt"}
            >
              {bulkResolving ? <RefreshCw size={15} className="spin" /> : <CheckCheck size={15} />}
              Đóng Hàng Loạt
            </button>
          )}
          <button className="btn-export" onClick={handleExportJsonl} data-tooltip="Xuất Dữ Liệu Vàng (JSONL)">
            <Download size={15} /> Xuất Dữ Liệu
          </button>
          <button
            className="icon-btn"
            onClick={fetchItems}
            disabled={loading}
            data-tooltip="Làm mới danh sách phản hồi"
          >
            <RefreshCw size={16} className={loading ? "spin" : ""} />
          </button>
        </div>
      </div>

      <div className={`bifurcated-layout ${isDeepDive ? 'deep-dive-state' : 'equilibrium-state'}`}>

        <DataPane
          title="Danh sách Phản hồi"
          isMaster={isDeepDive}
          items={items}
          loading={loading}
          page={page}
          totalPages={totalPages}
          setPage={setPage}
          selectedId={selectedItem?.id}
          onRowClick={handleRowClick}
          viewMode={viewMode}
        />

        {/* Khung Phân Tích Sâu (Detail Pane) */}
        {isDeepDive && (
          <div className="detail-pane-wrapper fade-in">
            <DetailPanel
              item={selectedItem}
              onClose={closeDetail}
              onSave={handleSave}
              onDelete={handleDelete}
              onCopy={handleCopy}
            />
          </div>
        )}
      </div>

      {showBulkResolveConfirm && (
        <div className="modal-overlay" onClick={() => !bulkResolving && setShowBulkResolveConfirm(false)}>
          <div className="confirm-modal" onClick={e => e.stopPropagation()}>
            <CheckCheck size={32} style={{ color: '#3ecf8e', marginBottom: 12 }} />
            <h3>Xác nhận đóng hàng loạt?</h3>
            <p style={{ color: 'var(--med-text-sub)', margin: '8px 0 20px', lineHeight: '1.6' }}>
              Bạn có chắc chắn muốn Đóng Hồ Sơ Hàng Loạt tất cả các phản hồi hiện tại (ngoại trừ các lỗi lâm sàng nghiêm trọng đã được bảo vệ)?
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button className="btn-cancel" onClick={() => setShowBulkResolveConfirm(false)} disabled={bulkResolving}>Hủy</button>
              <button className="btn-save" onClick={handleBulkResolveConfirm} disabled={bulkResolving}>{bulkResolving ? 'Đang xử lý...' : 'Đồng ý'}</button>
            </div>
          </div>
        </div>
      )}

      {feedbackToDelete && (
        <div className="modal-overlay" onClick={() => setFeedbackToDelete(null)}>
          <div className="confirm-modal" onClick={e => e.stopPropagation()}>
            <Trash size={32} style={{ color: '#ef4444', marginBottom: 12 }} />
            <h3>Xác nhận xóa phản hồi?</h3>
            <p style={{ color: 'var(--med-text-sub)', margin: '8px 0 20px', lineHeight: '1.6' }}>
              Bạn chắc chắn muốn xóa phản hồi này? Hành động này không thể hoàn tác.
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button className="btn-cancel" onClick={() => setFeedbackToDelete(null)}>Hủy</button>
              <button className="btn-save" style={{ backgroundColor: '#ef4444' }} onClick={async () => {
                try {
                  await deleteFeedback(feedbackToDelete);
                  showToast('Đã xóa vĩnh viễn phản hồi!');
                  fetchItems();
                  setSelectedItem(null);
                } catch (e) {
                  showToast('Lỗi khi xóa phản hồi', 'error');
                } finally {
                  setFeedbackToDelete(null);
                }
              }}>Xóa</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TabSystemTuning({ onDirtyChange }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState(null);
  const [initialSettings, setInitialSettings] = useState(null);
  const [showSaveConfirm, setShowSaveConfirm] = useState(false);
  // Settings state
  const [systemInfo, setSystemInfo] = useState(null);
  const [topK, setTopK] = useState(5);
  const [simThreshold, setSimThreshold] = useState(0.75);
  const [strictMode, setStrictMode] = useState(false);
  const [fallbackMessage, setFallbackMessage] = useState('');

  // Fetch settings on mount
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await getSystemSettings();
        setSystemInfo(data.system_info || null);
        const tk = data.top_k ?? 5;
        const st = data.similarity_threshold ?? 0.75;
        const sm = data.strict_mode ?? false;
        const fm = data.fallback_message || '';
        setTopK(tk);
        setSimThreshold(st);
        setStrictMode(sm);
        setFallbackMessage(fm);
        setInitialSettings({ topK: tk, simThreshold: st, strictMode: sm, fallbackMessage: fm });
      } catch (e) {
        console.error('Failed to load system settings:', e);
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, []);

  useEffect(() => {
    if (initialSettings) {
      const dirty = topK !== initialSettings.topK || simThreshold !== initialSettings.simThreshold || strictMode !== initialSettings.strictMode || fallbackMessage !== initialSettings.fallbackMessage;
      if (onDirtyChange) onDirtyChange(dirty);
    }
  }, [topK, simThreshold, strictMode, fallbackMessage, initialSettings, onDirtyChange]);

  const handleSaveSettings = async () => {
    if (saving) return;
    setSaving(true);
    setSaveResult(null);
    try {
      await updateSystemSettings({
        top_k: topK,
        similarity_threshold: simThreshold,
        strict_mode: strictMode,
        fallback_message: fallbackMessage,
      });
      setSaveResult({ ok: true, msg: 'Cấu hình đã được lưu thành công!' });
      setInitialSettings({ topK, simThreshold, strictMode, fallbackMessage });
      if (onDirtyChange) onDirtyChange(false);
      setTimeout(() => setSaveResult(null), 3000);
    } catch (e) {
      setSaveResult({ ok: false, msg: 'Lỗi khi lưu cấu hình.' });
    } finally {
      setSaving(false);
    }
  };

  const handleRefreshCache = async () => {
    if (refreshing) return;
    setRefreshing(true);
    setRefreshResult(null);
    try {
      const data = await refreshSuggestionCache();
      setRefreshResult({ ok: true, msg: data.message || 'Thành công!' });
    } catch (e) {
      setRefreshResult({ ok: false, msg: 'Lỗi khi làm mới cache.' });
    } finally {
      setRefreshing(false);
    }
  };


  if (loading) {
    return (
      <div className="tab-tuning">
        <div className="tuning-loading">
          <RefreshCw size={24} className="spin" />
          <span>Đang tải cấu hình...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="tab-tuning">
      <div className="tuning-grid">

        {/* Card 1: System Core Info */}
        <div className="tuning-card tuning-card--info">
          <div className="tuning-card-header">
            <Cpu size={18} />
            <h3>Thông tin Hệ thống</h3>
            <span className="badge badge--readonly">
              <Lock size={11} /> Chỉ đọc
            </span>
          </div>
          {systemInfo && (
            <div className="system-info-grid">
              <div className="info-row">
                <span className="info-label">Medical RAG Agent</span>
                <span className="info-badge badge--blue">{systemInfo.clinical_rag_model}</span>
                <span className="info-badge badge--green">Active</span>
              </div>
              <div className="info-row">
                <span className="info-label">Triage / Safety Agent</span>
                <span className="info-badge badge--blue">{systemInfo.triage_safety_model}</span>
                <span className="info-badge badge--green">Active</span>
              </div>
              <div className="info-row">
                <span className="info-label">Nhiệt độ (Temperature)</span>
                <span className="info-badge badge--amber">{systemInfo.temperature}</span>
                <span className="info-lock-note"><Lock size={12} /> Khóa cứng vì An toàn Y khoa</span>
              </div>
              <div className="info-row">
                <span className="info-label">Embedding Model</span>
                <span className="info-badge badge--purple">{systemInfo.embedding_model.split('/').pop()}</span>
              </div>
              <div className="info-row">
                <span className="info-label">Reranker</span>
                <span className="info-badge badge--purple">{systemInfo.reranker_model}</span>
              </div>
            </div>
          )}
        </div>

        {/* Card 3: RAG Settings */}
        <div className="tuning-card tuning-card--rag">
          <div className="tuning-card-header">
            <Sliders size={18} />
            <h3>Cấu hình Trích xuất RAG</h3>
          </div>

          <div className="slider-group">
            <div className="slider-label">
              <span>Số lượng tài liệu truy xuất (Top-K)</span>
              <span className="slider-value">{topK}</span>
            </div>
            <input
              type="range"
              min={1}
              max={10}
              step={1}
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value))}
              className="range-slider"
            />
            <div className="slider-range-labels">
              <span>1</span>
              <span>10</span>
            </div>
          </div>

          <div className="slider-group">
            <div className="slider-label">
              <span>Ngưỡng tương đồng tối thiểu</span>
              <span className="slider-value">{simThreshold.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={simThreshold}
              onChange={(e) => setSimThreshold(parseFloat(e.target.value))}
              className="range-slider"
            />
            <div className="slider-range-labels">
              <span>0.00</span>
              <span>1.00</span>
            </div>
            <p className="slider-hint">
              Tài liệu có độ khớp thấp hơn mức này sẽ bị loại bỏ, giúp giảm nhiễu cho AI.
            </p>
          </div>
        </div>

        {/* Card 4: Safety Guardrails */}
        <div className="tuning-card tuning-card--safety">
          <div className="tuning-card-header">
            <Shield size={18} />
            <h3>Hệ thống Phòng vệ</h3>
          </div>

          {/* Strict Mode Toggle */}
          <div className="toggle-group">
            <div className="toggle-left">
              <span className="toggle-title">Chế độ Nghiêm ngặt (Strict Mode)</span>
              <span className="toggle-desc">
                Bắt buộc AI chỉ trả lời dựa trên tài liệu RAG, từ chối mọi câu hỏi ngoài luồng.
              </span>
            </div>
            <button
              className={`toggle-switch ${strictMode ? 'on' : 'off'}`}
              onClick={() => setStrictMode(!strictMode)}
              data-tooltip={strictMode ? 'Bật' : 'Tắt'}
            >
              {strictMode ? <ToggleRight size={32} /> : <ToggleLeft size={32} />}
            </button>
          </div>

          {/* Fallback Message */}
          <div className="action-section" style={{ marginTop: 'auto' }}>
            <label className="action-label">Thông điệp Từ chối (Fallback)</label>
            <textarea
              className="admin-notes-input"
              value={fallbackMessage}
              onChange={(e) => setFallbackMessage(e.target.value)}
              placeholder="Nhập nội dung câu trả lời khi AI từ chối..."
              rows={3}
              spellCheck={false}
            />
          </div>
        </div>

        {/* Card 2: Performance */}
        <div className="tuning-card tuning-card--performance">
          <div className="tuning-card-header">
            <Zap size={18} />
            <h3>Tối ưu Hiệu suất</h3>
          </div>
          <p className="tuning-desc">
            Nạp lại dữ liệu gợi ý (thuốc, bệnh, hoạt chất) vào bộ nhớ RAM của RapidFuzz Engine mà không cần khởi động lại server.
          </p>

          {systemInfo && systemInfo.suggestion_cache && (
            <div className="system-info-grid" style={{ marginBottom: '20px' }}>
              <div className="info-row">
                <span className="info-label">Gợi ý Bệnh mạn tính</span>
                <span className="info-badge badge--green">{systemInfo.suggestion_cache.conditions_count} bản ghi</span>
              </div>
              <div className="info-row">
                <span className="info-label">Gợi ý Thuốc y khoa</span>
                <span className="info-badge badge--green">{systemInfo.suggestion_cache.medications_count} bản ghi</span>
              </div>
              <div className="info-row">
                <span className="info-label">Gợi ý Hoạt chất</span>
                <span className="info-badge badge--green">{systemInfo.suggestion_cache.ingredients_count} bản ghi</span>
              </div>
            </div>
          )}

          <button
            className="btn-hotreload"
            onClick={handleRefreshCache}
            disabled={refreshing}
            style={{ marginTop: 'auto' }}
          >
            <RefreshCw size={16} className={refreshing ? 'spin' : ''} />
            {refreshing ? 'Đang làm mới...' : 'Làm mới bộ nhớ RapidFuzz'}
          </button>
          {refreshResult && (
            <div className={`tuning-result ${refreshResult.ok ? 'ok' : 'err'}`} style={{ marginTop: 8 }}>
              {refreshResult.ok ? <Check size={14} /> : <X size={14} />}
              {refreshResult.msg}
            </div>
          )}
        </div>
      </div>

      {/* Global Save Bar */}
      <div className="tuning-save-bar">
        {saveResult && (
          <div className={`tuning-result ${saveResult.ok ? 'ok' : 'err'}`}>
            {saveResult.ok ? <Check size={14} /> : <X size={14} />}
            {saveResult.msg}
          </div>
        )}
        <button className="btn-save-settings" disabled={saving} onClick={() => setShowSaveConfirm(true)}>
          <Save size={16} />
          {saving ? 'Đang lưu...' : 'Lưu Toàn bộ Cấu hình'}
        </button>
      </div>

      {showSaveConfirm && (
        <div className="modal-overlay" onClick={() => setShowSaveConfirm(false)}>
          <div className="confirm-modal" onClick={e => e.stopPropagation()}>
            <h3 style={{ marginBottom: 12 }}>Xác nhận lưu cấu hình?</h3>
            <p style={{ color: 'var(--med-text-sub)', marginBottom: 24 }}>Bạn có chắc chắn muốn áp dụng các thay đổi này cho hệ thống AI?</p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button className="btn-cancel" onClick={() => setShowSaveConfirm(false)}>Hủy</button>
              <button className="btn-save" onClick={() => { setShowSaveConfirm(false); handleSaveSettings(); }}>Đồng ý</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


const DICT_SUB_TABS = [
  {
    id: 'conditions', label: 'Bệnh mạn tính', fields: [
      { key: 'icd_code', label: 'Mã ICD-10', required: true },
      { key: 'label', label: 'Tên bệnh', required: true },
      { key: 'category', label: 'Nhóm bệnh', required: true },
    ]
  },
  {
    id: 'medications', label: 'Thuốc', fields: [
      { key: 'drug_name', label: 'Tên thuốc', required: true },
      { key: 'ingredients', label: 'Hoạt chất (cách nhau bởi dấu phẩy)', required: false },
      { key: 'category', label: 'Nhóm thuốc', required: true },
    ]
  },
  {
    id: 'ingredients', label: 'Hoạt chất', fields: [
      { key: 'name', label: 'Tên hoạt chất', required: true },
    ]
  },
];

const DICT_TABLE_COLS = {
  conditions: [
    { key: 'icd_code', label: 'Mã ICD-10', width: '120px' },
    { key: 'label', label: 'Tên bệnh' },
    { key: 'category', label: 'Nhóm bệnh', width: '180px' },
  ],
  medications: [
    { key: 'drug_name', label: 'Tên thuốc' },
    { key: 'category', label: 'Nhóm thuốc', width: '200px' },
    { key: 'ingredients', label: 'Hoạt chất', width: '250px', render: (v) => Array.isArray(v) ? v.join(', ') : v },
  ],
  ingredients: [
    { key: 'name', label: 'Tên hoạt chất' },
  ],
};

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

function TabDictionary() {
  const [subTab, setSubTab] = useState('conditions');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [searchField, setSearchField] = useState('all');
  const [letterFilter, setLetterFilter] = useState('');
  const [showLetterPicker, setShowLetterPicker] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null); // null = thêm mới
  const [formData, setFormData] = useState({});
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [itemToDelete, setItemToDelete] = useState(null);

  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getDictionaryItems(subTab, { q: searchQ, field: searchField, letter: letterFilter, page, limit: 15 });
      setItems(res.items || []);
      setTotalPages(Math.ceil((res.total || 0) / 15));
      setTotal(res.total || 0);
    } catch (e) {
      console.error('Dict load error:', e);
    } finally {
      setLoading(false);
    }
  }, [subTab, searchQ, searchField, letterFilter, page]);

  useEffect(() => { setPage(1); setSearchQ(''); setLetterFilter(''); setSearchField('all'); }, [subTab]);
  useEffect(() => { loadItems(); }, [loadItems]);

  const openCreate = () => {
    setEditingItem(null);
    setFormData({});
    setModalOpen(true);
  };

  const openEdit = (item) => {
    setEditingItem(item);
    const tabCfg = DICT_SUB_TABS.find(t => t.id === subTab);
    const data = {};
    tabCfg.fields.forEach(f => {
      const val = item[f.key];
      data[f.key] = Array.isArray(val) ? val.join(', ') : (val || '');
    });
    setFormData(data);
    setModalOpen(true);
  };

  const handleDelete = async (item) => {
    setItemToDelete(item);
  };

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);
    try {
      let dataToSend = { ...formData };
      if (subTab === 'medications' && typeof dataToSend.ingredients === 'string') {
        dataToSend.ingredients = dataToSend.ingredients
          .split(',')
          .map(i => i.trim())
          .filter(Boolean);
      }
      if (editingItem) {
        await updateDictionaryItem(subTab, editingItem.id, dataToSend);
        showToast('Đã cập nhật mục từ điển thành công!');
      } else {
        await createDictionaryItem(subTab, dataToSend);
        showToast('Đã tạo mới mục từ điển thành công!');
      }
      setModalOpen(false);
      loadItems();
    } catch (e) {
      showToast('Lỗi khi lưu.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const tabCfg = DICT_SUB_TABS.find(t => t.id === subTab);
  const cols = DICT_TABLE_COLS[subTab] || [];

  return (
    <div className="tab-dictionary">
      {toast && (
        <div className={`admin-toast ${toast.type} fade-in`}>
          {toast.message}
        </div>
      )}
      {/* Sub-tabs */}
      <div className="dict-sub-tabs">
        {DICT_SUB_TABS.map(t => (
          <button
            key={t.id}
            className={`dict-sub-tab ${subTab === t.id ? 'active' : ''}`}
            onClick={() => setSubTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Toolbar */}
      <div className="dict-toolbar">
        <div className="dict-toolbar-left" style={{ display: 'flex', gap: '12px', alignItems: 'center', flex: 1 }}>
          <div className="dict-search-wrap">
            <Search size={15} className="dict-search-icon" />
            <input
              className="dict-search-input"
              placeholder={`Tìm kiếm ${tabCfg.label.toLowerCase()}...`}
              value={searchQ}
              onChange={(e) => { setSearchQ(e.target.value); setPage(1); }}
            />
          </div>
          {subTab !== 'ingredients' && (
            <select
              className="dict-search-field-select"
              value={searchField}
              onChange={(e) => { setSearchField(e.target.value); setPage(1); }}
            >
              {subTab === 'conditions' ? (
                <>
                  <option value="all">Bộ lọc tìm kiếm</option>
                  <option value="label">Tên bệnh</option>
                  <option value="icd_code">Mã ICD-10</option>
                  <option value="category">Nhóm bệnh</option>
                </>
              ) : (
                <>
                  <option value="all">Bộ lọc tìm kiếm</option>
                  <option value="drug_name">Tên thuốc</option>
                  <option value="category">Nhóm thuốc</option>
                  <option value="ingredients">Hoạt chất</option>
                </>
              )}
            </select>
          )}
          {subTab === 'ingredients' && (
            <div className="letter-filter-wrap">
              <button
                className={`btn-letter-filter ${letterFilter ? 'active' : ''}`}
                onClick={() => setShowLetterPicker(!showLetterPicker)}
              >
                {letterFilter ? `Chữ cái: ${letterFilter}` : 'Tìm theo chữ cái đầu'}
                <ChevronDown size={14} />
              </button>
              {showLetterPicker && (
                <div className="letter-picker-popover">
                  <div className="letter-picker-header">
                    <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--med-text-main)' }}>Lọc theo chữ cái</span>
                    <button className="icon-btn" onClick={() => setShowLetterPicker(false)}><X size={14} /></button>
                  </div>
                  <div className="letter-picker-grid">
                    <button
                      className={`letter-btn ${!letterFilter ? 'active' : ''}`}
                      onClick={() => { setLetterFilter(''); setShowLetterPicker(false); setPage(1); }}
                    >
                      Tất cả
                    </button>
                    {ALPHABET.map(l => (
                      <button
                        key={l}
                        className={`letter-btn ${letterFilter === l ? 'active' : ''}`}
                        onClick={() => { setLetterFilter(l); setShowLetterPicker(false); setPage(1); }}
                      >
                        {l}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
        <div className="dict-toolbar-right">
          <span className="dict-total">{total} bản ghi</span>
          <button className="btn-dict-add" onClick={openCreate}>
            <Plus size={15} /> Thêm mới
          </button>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="admin-loading"><RefreshCw size={18} className="spin" /> Đang tải...</div>
      ) : items.length === 0 ? (
        <div className="admin-empty">
          <AlertOctagon size={32} className="empty-icon" />
          <p>Không có dữ liệu</p>
        </div>
      ) : (
        <div className="dict-table-wrap">
          <table className="dict-table">
            <thead>
              <tr>
                <th style={{ width: '50px' }}>#</th>
                {cols.map(c => (
                  <th key={c.key} style={c.width ? { width: c.width } : {}}>{c.label}</th>
                ))}
                <th style={{ width: '90px', textAlign: 'center' }}>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => (
                <tr key={item.id}>
                  <td className="dict-row-num">{(page - 1) * 15 + idx + 1}</td>
                  {cols.map(c => (
                    <td key={c.key}>{c.render ? c.render(item[c.key]) : (item[c.key] || '')}</td>
                  ))}
                  <td className="dict-actions">
                    <button className="dict-action-btn edit" onClick={() => openEdit(item)} data-tooltip="Sửa"><Pencil size={14} /></button>
                    <button className="dict-action-btn delete" onClick={() => handleDelete(item)} data-tooltip="Xóa"><Trash size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="dict-pagination">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft size={16} /></button>
          <span>Trang {page} / {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}><ChevronRight size={16} /></button>
        </div>
      )}

      {/* Modal */}
      {modalOpen && (
        <div className="dict-modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="dict-modal" onClick={(e) => e.stopPropagation()}>
            <div className="dict-modal-header">
              <h3>{editingItem ? 'Chỉnh sửa' : 'Thêm mới'} {tabCfg.label}</h3>
              <button className="icon-btn" onClick={() => setModalOpen(false)}><X size={18} /></button>
            </div>
            <div className="dict-modal-body">
              {tabCfg.fields.map(f => (
                <div key={f.key} className="dict-form-group">
                  <label className="dict-form-label">
                    {f.label}
                    {f.required && <span className="dict-required">*</span>}
                  </label>
                  <input
                    className="dict-form-input"
                    value={formData[f.key] || ''}
                    onChange={(e) => setFormData(prev => ({ ...prev, [f.key]: e.target.value }))}
                    placeholder={f.label}
                  />
                </div>
              ))}
            </div>
            <div className="dict-modal-footer">
              <button className="btn-cancel" onClick={() => setModalOpen(false)}>Hủy</button>
              <button className="btn-save" onClick={handleSave} disabled={saving}>
                {saving ? <RefreshCw size={14} className="spin" /> : <Save size={14} />}
                {saving ? ' Đang lưu...' : ' Lưu'}
              </button>
            </div>
          </div>
        </div>
      )}

      {itemToDelete && (
        <div className="modal-overlay" onClick={() => setItemToDelete(null)}>
          <div className="confirm-modal" onClick={e => e.stopPropagation()}>
            <Trash size={32} style={{ color: '#ef4444', marginBottom: 12 }} />
            <h3>Xác nhận xóa mục từ điển?</h3>
            <p style={{ color: 'var(--med-text-sub)', margin: '8px 0 20px', lineHeight: '1.6' }}>
              Bạn có chắc muốn xóa mục <strong>"{itemToDelete.name || itemToDelete.title || itemToDelete.drug_name || itemToDelete.label || itemToDelete.id}"</strong> không? Hành động này không thể hoàn tác.
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button className="btn-cancel" onClick={() => setItemToDelete(null)}>Hủy</button>
              <button className="btn-save" style={{ backgroundColor: '#ef4444' }} onClick={async () => {
                try {
                  await deleteDictionaryItem(subTab, itemToDelete.id);
                  showToast('Đã xóa vĩnh viễn mục từ điển!');
                  loadItems();
                } catch (e) {
                  showToast('Lỗi khi xóa.', 'error');
                } finally {
                  setItemToDelete(null);
                }
              }}>Xóa</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const TABS = [
  { id: 'overview', label: 'Tổng quan', icon: <LayoutDashboard size={17} /> },
  { id: 'safety', label: 'Giám sát An toàn', icon: <ShieldAlert size={17} /> },
  { id: 'inbox', label: 'Quản lý phản hồi', icon: <Inbox size={17} /> },
  { id: 'dictionary', label: 'Từ điển Y khoa', icon: <BookOpen size={17} /> },
  { id: 'tuning', label: 'Tinh chỉnh hệ thống', icon: <Wrench size={17} /> },
];

const AdminDashboard = ({ onBack }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [pendingTab, setPendingTab] = useState(null);
  const [showUnsavedModal, setShowUnsavedModal] = useState(false);
  const [isTuningDirty, setIsTuningDirty] = useState(false);

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const data = await getAdminStats();
      setStats(data);
    } catch (e) {
      console.error('Failed to load stats:', e);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'overview') loadStats();
  }, [activeTab, loadStats]);

  const handleSaveNote = async (id, payload) => {
    try {
      await updateFeedbackStatus(id, payload);
    } catch (e) {
      console.error('Failed to update feedback:', e);
      throw e;
    }
  };

  return (
    <div className="admin-layout">
      <aside className={`admin-sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          {!isSidebarCollapsed ? (
            <>
              <img src="/images/Logo_name_light.png?v=20260601-0250" alt="A.I.M Care Logo" className="admin-sidebar-logo" />
              <button className="icon-btn toggle-sidebar-btn" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}>
                <Menu size={20} />
              </button>
            </>
          ) : (
            <button className="icon-btn toggle-sidebar-btn collapsed-logo-btn" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}>
              <img src="/images/Logo_chat.png" alt="Logo" className="logo-chat-icon" />
              <Menu size={20} className="menu-hover-icon" />
            </button>
          )}
        </div>

        <nav className="sidebar-nav">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`sidebar-nav-btn ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => {
                if (activeTab === 'tuning' && isTuningDirty && tab.id !== 'tuning') {
                  setPendingTab(tab.id);
                  setShowUnsavedModal(true);
                } else {
                  setActiveTab(tab.id);
                }
              }}
              data-tooltip={isSidebarCollapsed ? tab.label : undefined}
            >
              {tab.icon}
              {!isSidebarCollapsed && <span>{tab.label}</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button className="btn-exit" onClick={onBack} data-tooltip={isSidebarCollapsed ? "Quay lại" : undefined}>
            <ChevronLeft size={16} />
            {!isSidebarCollapsed && <span>Quay lại</span>}
          </button>
        </div>
      </aside>

      <div className="admin-main">
        <header className="admin-header-new">
          <div className="header-search">
            {/* Tương lai: Global Search */}
            <span className="search-placeholder"></span>
          </div>
          <div className="header-actions">
            <UserButton
              appearance={{
                elements: {
                  avatarBox: { width: '36px', height: '36px' },
                },
              }}
            />
          </div>
        </header>

        <main className="admin-content-new">
          {activeTab === 'overview' && (
            <TabOverview stats={stats} onRefresh={loadStats} loading={statsLoading} />
          )}
          {activeTab === 'safety' && <TabSafetyMonitor />}
          {activeTab === 'inbox' && (
            <TabFeedbackInbox onSaveNote={handleSaveNote} />
          )}
          {activeTab === 'dictionary' && <TabDictionary />}
          {activeTab === 'tuning' && <TabSystemTuning onDirtyChange={setIsTuningDirty} />}
        </main>

        {showUnsavedModal && (
          <div className="modal-overlay" onClick={() => setShowUnsavedModal(false)}>
            <div className="confirm-modal" onClick={e => e.stopPropagation()}>
              <h3 style={{ marginBottom: 12 }}>Xác nhận thay đổi hay không?</h3>
              <p style={{ color: 'var(--med-text-sub)', marginBottom: 24 }}>Bạn có những thay đổi chưa được lưu. Rời đi sẽ hủy bỏ các thay đổi này.</p>
              <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
                <button className="btn-cancel" onClick={() => { setShowUnsavedModal(false); setPendingTab(null); }}>Hủy</button>
                <button className="btn-danger" onClick={() => { setShowUnsavedModal(false); setIsTuningDirty(false); setActiveTab(pendingTab); setPendingTab(null); }}>Đồng ý</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminDashboard;
