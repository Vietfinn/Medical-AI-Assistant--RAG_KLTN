import React, { useState, useEffect, useCallback } from 'react';
import { 
  Send, FileText, MoreHorizontal, Trash2,
  X, CornerUpLeft, Edit2, FolderPlus, Menu, Plus, MoreVertical
} from 'lucide-react';
import { getCornerSessions, assignSessionToCorner, getSessions, renameSession } from '../services/api';
import './HealthCornerView.css';

const HealthCornerView = ({
  corner,
  refreshTrigger,
  onSelectSession,
  onNewChatInCorner,
  onBack,
  onDeleteCorner,
  onUpdateCorner,
  onUnassignSession,
  onDeleteSession,
  onRefreshCorners,
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
      await assignSessionToCorner(sessionId, null);
      setSessions(prev => prev.filter(s => s._id !== sessionId));
      if (onUnassignSession) onUnassignSession(sessionId);
      if (onRefreshCorners) onRefreshCorners();
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
                          const newCornerId = window.prompt("Nhập ID của Góc khác:");
                          if (newCornerId) {
                            assignSessionToCorner(session._id, newCornerId).then(() => {
                              setSessions(prev => prev.filter(s => s._id !== session._id));
                              if (onRefreshCorners) onRefreshCorners();
                            });
                          }
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
                          setActiveSessionMenu(null);
                          const newName = window.prompt("Đổi tên cuộc trò chuyện:", session.title);
                          if (newName && newName.trim() && newName !== session.title) {
                            renameSession(session._id, newName.trim()).then(() => {
                              fetchSessions();
                            });
                          }
                        }}>
                          <Edit2 size={14} />
                          <span>Đổi tên</span>
                        </button>
                        <button className="danger" onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm("Bạn có chắc chắn muốn xóa cuộc trò chuyện này?")) {
                            handleDeleteSessionInCorner(session._id);
                          }
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
    </div>
  );
};

export default HealthCornerView;
