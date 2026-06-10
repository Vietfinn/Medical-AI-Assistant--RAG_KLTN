import React, { useState, useEffect, useCallback } from 'react';
import { 
  Send, FileText, MoreHorizontal, Trash2,
  X, CornerUpLeft, Edit2, FolderPlus, Menu, Plus, MoreVertical, HeartPulse
} from 'lucide-react';
import { getCornerSessions, assignSessionToCorner, getSessions, renameSession } from '../services/api';
import './HealthCornerView.css';

const HealthCornerView = ({
  corner,
  healthCorners = [],
  refreshTrigger,
  onSelectSession,
  onNewChatInCorner,
  onBack,
  onDeleteCorner,
  onUpdateCorner,
  onAssignSession,
  onUnassignSession,
  onDeleteSession,
  onRefreshCorners,
  onRefreshSessions,
  onToggleMobileSidebar,
}) => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showHeaderMenu, setShowHeaderMenu] = useState(false);
  const [activeSessionMenu, setActiveSessionMenu] = useState(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [isChangingEmoji, setIsChangingEmoji] = useState(false);
  const [showAddSessionModal, setShowAddSessionModal] = useState(false);
  const [availableSessions, setAvailableSessions] = useState([]);
  const [loadingAvailable, setLoadingAvailable] = useState(false);
  const [questionText, setQuestionText] = useState('');
  const [isAssigning, setIsAssigning] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // States for session modals
  const [renameSessionData, setRenameSessionData] = useState(null); // { id: string, title: string }
  const [moveSessionData, setMoveSessionData] = useState(null); // { id: string, title: string }
  const [deleteSessionData, setDeleteSessionData] = useState(null); // { id: string, title: string }
  const [isActionProcessing, setIsActionProcessing] = useState(false);

  const fetchSessions = useCallback(async () => {
    if (!corner?._id) return;
    try {
      setLoading(true);
      const data = await getCornerSessions(corner._id);
      setSessions(data);
    } catch (error) {
      console.error('Error loading corner sessions:', error);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [corner?._id, refreshTrigger]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Close menus on outside click
  useEffect(() => {
    const handleClickOutside = () => {
      setShowHeaderMenu(false);
      setActiveSessionMenu(null);
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  const handleRenameSubmit = async () => {
    const trimmed = renameValue.trim();
    if (trimmed && trimmed !== corner.name) {
      await onUpdateCorner(corner._id, { name: trimmed });
    }
    setIsRenaming(false);
  };

  const handleEmojiChange = async (newEmoji) => {
    await onUpdateCorner(corner._id, { emoji: newEmoji });
    setIsChangingEmoji(false);
  };

  const handleUnassignSession = async (sessionId) => {
    try {
      if (onAssignSession) {
        await onAssignSession(sessionId, null);
      } else {
        await assignSessionToCorner(sessionId, null);
        setSessions(prev => prev.filter(s => s._id !== sessionId));
        if (onRefreshCorners) onRefreshCorners();
      }
    } catch (error) {
      console.error('Error unassigning session:', error);
    }
    setActiveSessionMenu(null);
  };

  const handleDeleteSessionInCorner = async (sessionId) => {
    if (onDeleteSession) {
      await onDeleteSession(sessionId);
      setSessions(prev => prev.filter(s => s._id !== sessionId));
      if (onRefreshCorners) onRefreshCorners();
    }
    setActiveSessionMenu(null);
  };

  // eslint-disable-next-line no-unused-vars
  const handleAddExistingSession = async () => {
    setShowAddSessionModal(true);
    setLoadingAvailable(true);
    try {
      const allSessions = await getSessions();
      // Filter sessions that don't have a corner_id
      const filtered = allSessions.filter(s => !s.corner_id);
      setAvailableSessions(filtered);
    } catch (error) {
      console.error('Error loading available sessions:', error);
    } finally {
      setLoadingAvailable(false);
    }
  };

  const handleAssignExisting = async (sessionId) => {
    try {
      setIsAssigning(true);
      await assignSessionToCorner(sessionId, corner._id);
      setAvailableSessions(prev => prev.filter(s => s._id !== sessionId));
      await fetchSessions();
      if (onRefreshCorners) onRefreshCorners();
    } catch (error) {
      console.error('Error assigning session:', error);
    } finally {
      setIsAssigning(false);
    }
  };

  const formatDate = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp * 1000);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Hôm nay';
    if (diffDays === 1) return 'Hôm qua';
    if (diffDays < 7) return `${diffDays} ngày trước`;
    
    return date.toLocaleDateString('vi-VN', { day: 'numeric', month: 'short' });
  };

  const EMOJI_OPTIONS = ['🩺', '💊', '🫀', '🧠', '🦴', '👁️', '🤰', '👶', '🧓', '🏃', '🥗', '😴', '🧬', '💉', '🩹', '❤️'];

  if (!corner) return null;

  return (
    <div className="corner-view-canvas">
      <div className="corner-view-topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, flex: 1 }}>
          <button 
            className="mobile-hamburger-btn corner-hamburger-btn" 
            onClick={onToggleMobileSidebar}
            aria-label="Mở menu"
          >
            <Menu size={20} />
          </button>
        </div>

        <div className="corner-topbar-options-wrapper" onClick={(e) => e.stopPropagation()}>
          <button
            className={`corner-topbar-options-btn ${showHeaderMenu ? 'active' : ''}`}
            onClick={() => setShowHeaderMenu(!showHeaderMenu)}
          >
            <MoreVertical size={20} />
          </button>
          {showHeaderMenu && (
            <div className="corner-topbar-options-menu fade-in">
              <button className="option-item" onClick={() => {
                setRenameValue(corner.name);
                setIsRenaming(true);
                setShowHeaderMenu(false);
              }}>
                <Edit2 size={14} />
                <span>Đổi tên góc</span>
              </button>
              <button className="option-item" onClick={() => {
                setIsChangingEmoji(true);
                setShowHeaderMenu(false);
              }}>
                <FolderPlus size={14} />
                <span>Đổi Emoji</span>
              </button>
              <button className="option-item" onClick={() => {
                handleAddExistingSession();
                setShowHeaderMenu(false);
              }}>
                <Plus size={14} />
                <span>Thêm cuộc trò chuyện</span>
              </button>
              <button className="option-item danger" onClick={() => {
                setShowHeaderMenu(false);
                setShowDeleteConfirm(true);
              }}>
                <Trash2 size={14} />
                <span>Xóa Góc</span>
              </button>
            </div>
          )}
        </div>
      </div>
      <div className="corner-view-content">


        {/* Hero Section */}
        <div className="corner-view-hero">
          {isChangingEmoji ? (
            <div className="corner-emoji-grid center-grid">
              {EMOJI_OPTIONS.map(e => (
                <button
                  key={e}
                  className={`corner-emoji-option ${e === corner.emoji ? 'active' : ''}`}
                  onClick={() => handleEmojiChange(e)}
                >
                  {e}
                </button>
              ))}
            </div>
          ) : (
            <div className="corner-view-emoji-large" onClick={() => setIsChangingEmoji(true)} title="Đổi emoji">
              {corner.emoji}
            </div>
          )}

          {isRenaming ? (
            <input
              className="corner-rename-input center-align"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onBlur={handleRenameSubmit}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRenameSubmit();
                if (e.key === 'Escape') setIsRenaming(false);
              }}
              autoFocus
              maxLength={100}
            />
          ) : (
            <h1 className="corner-view-name-large">{corner.name}</h1>
          )}

          <div className="corner-source-badge" style={{ display: 'none' }}>
            <FileText size={14} />
            <span>{sessions.length} nguồn</span>
          </div>

          <div className="corner-hero-chat-input-wrapper">
            <input
              type="text"
              className="corner-hero-chat-input"
              placeholder="Hỏi A.I.M Care"
              value={questionText}
              onChange={(e) => setQuestionText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && questionText.trim()) {
                  onNewChatInCorner(questionText.trim());
                  setQuestionText('');
                }
              }}
              spellCheck={false}
            />
            <button
              className="corner-hero-chat-send-btn"
              disabled={!questionText.trim()}
              onClick={() => {
                if (questionText.trim()) {
                  onNewChatInCorner(questionText.trim());
                  setQuestionText('');
                }
              }}
            >
              <Send size={18} />
            </button>
          </div>
        </div>

        {/* Session list */}
        <div className="corner-session-list">
          {loading ? (
            <div className="corner-empty-state">
              <div className="corner-loading-spinner" />
              <p>Đang tải...</p>
            </div>
          ) : sessions.length === 0 ? (
            <div className="corner-empty-state">
              <FileText size={40} strokeWidth={1} />
              <p>Các cuộc trò chuyện sẽ xuất hiện ở đây</p>
            </div>
          ) : (
            sessions.map(session => (
              <div
                key={session._id}
                className="corner-session-row"
                onClick={() => onSelectSession(session)}
              >
                <div className="corner-session-info">
                  <span className="corner-session-title">{session.title}</span>
                </div>
                <div className="corner-session-right">
                  <span className="corner-session-date">{formatDate(session.updated_at)}</span>
                  <div className="corner-session-menu-wrapper" onClick={(e) => e.stopPropagation()}>
                    <button
                      className="corner-session-menu-btn"
                      onClick={() => setActiveSessionMenu(
                        activeSessionMenu === session._id ? null : session._id
                      )}
                    >
                      <MoreHorizontal size={16} />
                    </button>
                    {activeSessionMenu === session._id && (
                      <div className="corner-session-dropdown">
                        <button onClick={(e) => {
                          e.stopPropagation();
                          setMoveSessionData({ id: session._id, title: session.title });
                          setActiveSessionMenu(null);
                        }}>
                          <FolderPlus size={14} />
                          <span>Chuyển đến góc khác</span>
                        </button>
                        <button onClick={(e) => {
                          e.stopPropagation();
                          handleUnassignSession(session._id);
                        }}>
                          <CornerUpLeft size={14} />
                          <span>Xóa khỏi góc</span>
                        </button>
                        <button onClick={(e) => {
                          e.stopPropagation();
                          setRenameSessionData({ id: session._id, title: session.title });
                          setActiveSessionMenu(null);
                        }}>
                          <Edit2 size={14} />
                          <span>Đổi tên</span>
                        </button>
                        <button className="danger" onClick={(e) => {
                          e.stopPropagation();
                          setDeleteSessionData({ id: session._id, title: session.title });
                          setActiveSessionMenu(null);
                        }}>
                          <Trash2 size={14} />
                          <span>Xóa</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Modal thêm session hiện có */}
      {showAddSessionModal && (
        <div className="corner-modal-overlay" onClick={() => !isAssigning && setShowAddSessionModal(false)}>
          <div className="corner-modal" onClick={(e) => e.stopPropagation()}>
            <div className="corner-modal-header">
              <h3>Thêm cuộc trò chuyện vào Góc</h3>
              <button className="corner-modal-close" onClick={() => !isAssigning && setShowAddSessionModal(false)} disabled={isAssigning}>
                <X size={18} />
              </button>
            </div>
            <div className="corner-modal-body">
              {loadingAvailable ? (
                <div className="corner-empty-state">
                  <div className="corner-loading-spinner" />
                  <p>Đang tải...</p>
                </div>
              ) : isAssigning ? (
                <div className="corner-empty-state">
                  <div className="corner-loading-spinner" />
                  <p>Đang thêm cuộc trò chuyện vào Góc...</p>
                </div>
              ) : availableSessions.length === 0 ? (
                <div className="corner-empty-state">
                  <p>Không có cuộc trò chuyện nào để thêm</p>
                </div>
              ) : (
                availableSessions.map(session => (
                  <div
                    key={session._id}
                    className="corner-modal-session-row"
                    onClick={() => !isAssigning && handleAssignExisting(session._id)}
                    style={{ pointerEvents: isAssigning ? 'none' : 'auto', opacity: isAssigning ? 0.6 : 1 }}
                  >
                    <FileText size={16} className="corner-session-icon" />
                    <span className="corner-session-title">{session.title || 'Đoạn chat mới'}</span>
                    <span className="corner-session-date">{formatDate(session.updated_at)}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="modal-overlay" onClick={() => !isDeleting && setShowDeleteConfirm(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Xóa Góc sức khỏe?</h3>
            <p style={{ lineHeight: '1.6', fontSize: '0.92rem', color: 'var(--text-secondary, #94a3b8)' }}>
              Bạn có chắc chắn muốn xóa Góc sức khỏe <strong>"{corner.name}"</strong> không?
              <br />
              <span style={{ color: 'var(--accent-blue, #3b82f6)', fontWeight: '500' }}>Lưu ý:</span> Các cuộc trò chuyện bên trong Góc sẽ <strong style={{ color: 'var(--text-primary, #e2e8f0)' }}>không bị xóa</strong>. Chúng sẽ được tự động chuyển ra danh sách "Gần đây" ở thanh bên.
            </p>
            <div className="modal-actions">
              <button 
                className="modal-btn cancel" 
                onClick={() => setShowDeleteConfirm(false)} 
                disabled={isDeleting}
              >
                Huỷ
              </button>
              <button 
                className="modal-btn delete" 
                onClick={async () => {
                  if (isDeleting) return;
                  setIsDeleting(true);
                  try {
                    await onDeleteCorner(corner._id);
                  } catch (err) {
                    console.error("Lỗi khi xóa góc:", err);
                  } finally {
                    setIsDeleting(false);
                    setShowDeleteConfirm(false);
                  }
                }} 
                disabled={isDeleting}
              >
                {isDeleting ? 'Đang xóa...' : 'Xóa'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rename Session Modal */}
      {renameSessionData && (
        <div className="modal-overlay" onClick={() => !isActionProcessing && setRenameSessionData(null)}>
          <div className="modal-content rename-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Đổi tên cuộc trò chuyện</h3>
            <input
              autoFocus
              className="modal-rename-input"
              value={renameSessionData.title}
              onChange={(e) => setRenameSessionData({ ...renameSessionData, title: e.target.value })}
              onKeyDown={async (e) => {
                if (e.key === 'Enter') {
                  const trimmed = renameSessionData.title.trim();
                  if (trimmed) {
                    setIsActionProcessing(true);
                    try {
                      await renameSession(renameSessionData.id, trimmed);
                      await fetchSessions();
                      if (onRefreshSessions) onRefreshSessions();
                      setRenameSessionData(null);
                    } catch (err) {
                      console.error("Error renaming session:", err);
                    } finally {
                      setIsActionProcessing(false);
                    }
                  }
                }
                if (e.key === 'Escape') setRenameSessionData(null);
              }}
              style={{
                width: '100%',
                background: 'var(--bg-primary)',
                border: '1.5px solid var(--accent-blue, #3b82f6)',
                color: 'var(--text-primary)',
                padding: '12px 14px',
                borderRadius: '8px',
                fontSize: '15px',
                outline: 'none',
                marginBottom: '20px',
                marginTop: '12px',
                boxSizing: 'border-box'
              }}
            />
            <div className="modal-actions">
              <button 
                className="modal-btn cancel-text" 
                onClick={() => setRenameSessionData(null)} 
                disabled={isActionProcessing}
              >
                Huỷ
              </button>
              <button 
                className="modal-btn save-text" 
                onClick={async () => {
                  const trimmed = renameSessionData.title.trim();
                  if (trimmed) {
                    setIsActionProcessing(true);
                    try {
                      await renameSession(renameSessionData.id, trimmed);
                      await fetchSessions();
                      if (onRefreshSessions) onRefreshSessions();
                      setRenameSessionData(null);
                    } catch (err) {
                      console.error("Error renaming session:", err);
                    } finally {
                      setIsActionProcessing(false);
                    }
                  }
                }} 
                disabled={isActionProcessing || !renameSessionData.title.trim()}
              >
                {isActionProcessing ? 'Đang lưu...' : 'Đổi tên'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Move Session Modal */}
      {moveSessionData && (
        <div className="modal-overlay" onClick={() => !isActionProcessing && setMoveSessionData(null)}>
          <div className="modal-content assign-modal" onClick={(e) => e.stopPropagation()}>
            <div className="assign-modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0 }}>Di chuyển cuộc trò chuyện</h3>
              <button 
                className="close-btn" 
                onClick={() => !isActionProcessing && setMoveSessionData(null)} 
                disabled={isActionProcessing}
                style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                <X size={18} />
              </button>
            </div>
            <p className="assign-modal-sub" style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', margin: '8px 0 20px 0', lineHeight: '1.5' }}>
              Chọn một Góc sức khỏe bạn muốn chuyển cuộc trò chuyện này vào
            </p>
            <div className="assign-corners-list">
              {isActionProcessing ? (
                <div className="assign-loading">
                  <div className="corner-loading-spinner" />
                  <p>Đang di chuyển cuộc trò chuyện...</p>
                </div>
              ) : (
                healthCorners
                  .filter(c => c._id !== corner._id)
                  .map(c => (
                    <button
                      key={c._id}
                      className="assign-corner-item"
                      disabled={isActionProcessing}
                      onClick={async () => {
                        setIsActionProcessing(true);
                        try {
                          if (onAssignSession) {
                            await onAssignSession(moveSessionData.id, c._id);
                          } else {
                            await assignSessionToCorner(moveSessionData.id, c._id);
                          }
                          setSessions(prev => prev.filter(s => s._id !== moveSessionData.id));
                          if (onRefreshCorners) onRefreshCorners();
                          setMoveSessionData(null);
                        } catch (err) {
                          console.error("Error moving session:", err);
                        } finally {
                          setIsActionProcessing(false);
                        }
                      }}
                    >
                      {c.emoji ? (
                        <span style={{ fontSize: '1.2rem', marginRight: '6px' }}>{c.emoji}</span>
                      ) : (
                        <HeartPulse size={18} className="assign-corner-icon" style={{ marginRight: '6px' }} />
                      )}
                      <span className="assign-corner-name">{c.name}</span>
                    </button>
                  ))
              )}
              {!isActionProcessing && healthCorners.filter(c => c._id !== corner._id).length === 0 && (
                <p style={{ textAlign: 'center', fontSize: '0.9rem', color: 'var(--text-muted)', margin: '20px 0' }}>
                  Không có Góc sức khỏe nào khác để chuyển đến.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Delete Session Confirmation Modal */}
      {deleteSessionData && (
        <div className="modal-overlay" onClick={() => !isActionProcessing && setDeleteSessionData(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Xoá cuộc hội thoại?</h3>
            <p style={{ lineHeight: '1.6', fontSize: '0.92rem', color: 'var(--text-secondary, #94a3b8)', marginBottom: '24px' }}>
              Bạn có chắc chắn muốn xoá cuộc hội thoại <strong>"{deleteSessionData.title}"</strong> không? Hành động này không thể hoàn tác.
            </p>
            <div className="modal-actions">
              <button 
                className="modal-btn cancel" 
                onClick={() => setDeleteSessionData(null)} 
                disabled={isActionProcessing}
              >
                Huỷ
              </button>
              <button 
                className="modal-btn delete" 
                onClick={async () => {
                  setIsActionProcessing(true);
                  try {
                    await handleDeleteSessionInCorner(deleteSessionData.id);
                    setDeleteSessionData(null);
                  } catch (err) {
                    console.error("Error deleting session:", err);
                  } finally {
                    setIsActionProcessing(false);
                  }
                }} 
                disabled={isActionProcessing}
              >
                {isActionProcessing ? 'Đang xóa...' : 'Xoá'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HealthCornerView;
