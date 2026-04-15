import React, { useState, useEffect, useRef } from 'react';
import { Plus, MoreVertical, Pin, PinOff, Edit2, Trash2, Menu, X, Settings, Moon, Sun, User } from 'lucide-react';
import { pinSession, renameSession } from '../services/api';
import './Sidebar.css';

const Sidebar = ({
  sessions,
  currentSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onRefreshSessions,
  theme,
  onToggleTheme,
  isOpen,
  onToggle,
  profileCompleted,
  onOpenProfile,
}) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [activeMenuId, setActiveMenuId] = useState(null);
  
  // Modals state
  const [renameData, setRenameData] = useState(null); // { id: string, title: string }
  const [deleteData, setDeleteData] = useState(null); // { id: string, title: string }

  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setActiveMenuId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleMenuClick = (e, sessionId) => {
    e.stopPropagation();
    setActiveMenuId(activeMenuId === sessionId ? null : sessionId);
  };

  const handlePin = async (e, session) => {
    e.stopPropagation();
    setActiveMenuId(null);
    try {
      await pinSession(session._id, !session.is_pinned);
      if (onRefreshSessions) onRefreshSessions();
    } catch (error) {
      console.error('Lỗi khi ghim/bỏ ghim hội thoại:', error);
    }
  };

  const openRename = (e, session) => {
    e.stopPropagation();
    setActiveMenuId(null);
    setRenameData({ id: session._id, title: session.title });
  };

  const handleRenameSave = async () => {
    if (!renameData.title.trim()) return;
    try {
      await renameSession(renameData.id, renameData.title);
      if (onRefreshSessions) onRefreshSessions();
    } catch (error) {
      console.error('Lỗi khi đổi tên:', error);
    } finally {
      setRenameData(null);
    }
  };

  const handleRenameCancel = () => {
    setRenameData(null);
  };

  const openDelete = (e, session) => {
    e.stopPropagation();
    setActiveMenuId(null);
    setDeleteData({ id: session._id, title: session.title });
  };

  const handleDeleteConfirm = async () => {
    try {
      await onDeleteSession(deleteData.id);
    } catch (error) {
      console.error('Lỗi khi xoá hội thoại:', error);
    } finally {
      setDeleteData(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteData(null);
  };

  return (
    <>
      {isOpen && (
        <div className="sidebar-overlay" onClick={onToggle} />
      )}

      <aside className={`sidebar ${isOpen ? 'open' : 'collapsed'}`}>
        <div className="sidebar-top">
          <button className="sidebar-toggle" onClick={onToggle} title="Đóng menu">
            <X size={20} />
          </button>

          <button className="new-chat-btn" onClick={onNewChat}>
            <Plus size={20} />
            <span>Cuộc trò chuyện mới</span>
          </button>
        </div>

        <nav className="sidebar-sessions">
          {(!sessions || sessions.length === 0) ? (
            <div className="empty-sessions">
              <p>Chưa có hội thoại nào</p>
              <span>Bắt đầu bằng cách gửi câu hỏi đầu tiên</span>
            </div>
          ) : (
            sessions.map((session) => (
              <div
                key={session._id}
                className={`session-item ${currentSessionId === session._id ? 'active' : ''}`}
                onClick={() => onSelectSession(session._id)}
              >
                {/* Session Item Details */}
                <>
                    <div className="session-title-wrap">
                      {session.is_pinned && <Pin size={12} className="pinned-icon" />}
                      <span className={`session-title ${session.is_pinned ? 'is-pinned' : ''}`}>
                        {session.title}
                      </span>
                    </div>

                    <button
                      className={`session-options-btn ${activeMenuId === session._id ? 'active' : ''}`}
                      onClick={(e) => handleMenuClick(e, session._id)}
                      title="Tuỳ chọn"
                    >
                      <MoreVertical size={16} />
                    </button>

                    {activeMenuId === session._id && (
                      <div className="session-options-menu" ref={menuRef} onClick={(e) => e.stopPropagation()}>
                        <button className="option-item" onClick={(e) => handlePin(e, session)}>
                          {session.is_pinned ? (
                            <><PinOff size={14}/> Bỏ ghim</>
                          ) : (
                            <><Pin size={14}/> Ghim</>
                          )}
                        </button>
                        <button className="option-item" onClick={(e) => openRename(e, session)}>
                          <Edit2 size={14}/> Đổi tên
                        </button>
                        <button className="option-item danger" onClick={(e) => openDelete(e, session)}>
                          <Trash2 size={14}/> Xoá
                        </button>
                      </div>
                    )}
                  </>
              </div>
            ))
          )}
        </nav>

        <div className="sidebar-bottom">
          <button className="profile-btn sidebar-profile-btn" onClick={onOpenProfile}>
            <User size={18} />
            <span>Hồ sơ sức khỏe</span>
            {!profileCompleted && <span className="sidebar-red-dot" />}
          </button>

          <div className="settings-wrapper">
            <button className="profile-btn" onClick={() => setIsSettingsOpen(!isSettingsOpen)}>
              <Settings size={18} />
              <span>Cài đặt hệ thống</span>
            </button>
            
            {isSettingsOpen && (
              <div className="sidebar-settings-dropdown fade-in">
                <div className="dropdown-header">
                  <span>Cài đặt hệ thống</span>
                  <button onClick={() => setIsSettingsOpen(false)}><X size={16} /></button>
                </div>
                <div className="dropdown-menu">
                  <button 
                    className="dropdown-item" 
                    onClick={() => {
                      onToggleTheme();
                      setIsSettingsOpen(false);
                    }}
                  >
                    {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
                    <span>Giao diện: {theme === 'dark' ? 'Tối' : 'Sáng'}</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </aside>

      {!isOpen && (
        <button className="sidebar-hamburger" onClick={onToggle} title="Mở menu">
          <Menu size={22} />
        </button>
      )}

      {/* Rename Confirmation Modal */}
      {renameData && (
        <div className="modal-overlay">
          <div className="modal-content rename-modal">
            <h3>Đổi tên cho cuộc trò chuyện này</h3>
            <input
              autoFocus
              className="modal-rename-input"
              value={renameData.title}
              onChange={(e) => setRenameData({ ...renameData, title: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRenameSave();
                if (e.key === 'Escape') handleRenameCancel();
              }}
            />
            <div className="modal-actions">
              <button className="modal-btn cancel-text" onClick={handleRenameCancel}>Huỷ</button>
              <button className="modal-btn save-text" onClick={handleRenameSave}>Đổi tên</button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteData && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Xoá cuộc hội thoại?</h3>
            <p>Bạn có chắc chắn muốn xoá cuộc hội thoại <strong>"{deleteData.title}"</strong> không? Hành động này không thể hoàn tác.</p>
            <div className="modal-actions">
              <button className="modal-btn cancel" onClick={handleDeleteCancel}>Huỷ</button>
              <button className="modal-btn delete" onClick={handleDeleteConfirm}>Xoá</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default Sidebar;
