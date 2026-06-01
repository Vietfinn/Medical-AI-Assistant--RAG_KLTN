import React, { useState, useEffect, useRef } from 'react';
import { Plus, MoreVertical, Pin, PinOff, Edit2, Trash2, Menu, X, Settings, Moon, Sun, ShieldCheck, Search, FolderPlus, HeartPulse, SquarePen, Check, MoreHorizontal, RefreshCw, ClipboardList } from 'lucide-react';
import { UserButton, useUser } from '@clerk/clerk-react';
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
  isProfileOpen,
  currentView,
  isAdmin,
  onOpenAdmin,
  onOpenSearch,
  healthCorners = [],
  activeCorner,
  currentSession,
  onCreateCornerView,
  onOpenCorner,
  onAssignSession,
  onUpdateCorner,
  onDeleteCorner,
  isMobileSidebarOpen,
  onCloseMobileSidebar,
}) => {
  const { user } = useUser();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [activeCornerMenuId, setActiveCornerMenuId] = useState(null);
  const [assignSessionData, setAssignSessionData] = useState(null); // { id: string, title: string }
  const [sidebarToast, setSidebarToast] = useState(null); // string
  const [isAssigning, setIsAssigning] = useState(false);
  const [menuPosition, setMenuPosition] = useState({ top: null, bottom: null, left: 0 });
  const [moreCornersPosition, setMoreCornersPosition] = useState({ bottom: 0, left: 0, width: 0 });

  // Modals state
  const [renameData, setRenameData] = useState(null); // { id: string, title: string }
  const [deleteData, setDeleteData] = useState(null); // { id: string, title: string }
  const [isActionProcessing, setIsActionProcessing] = useState(false);

  const [showAllCorners, setShowAllCorners] = useState(false);
  const cornersDropdownRef = useRef(null);
  const [hoveredTitle, setHoveredTitle] = useState({ text: '', rect: null });

  // Swipe to close logic
  const touchStartX = useRef(null);

  const handleTouchStart = (e) => {
    touchStartX.current = e.touches[0].clientX;
  };

  const handleTouchEnd = (e) => {
    if (touchStartX.current === null) return;
    const touchEndX = e.changedTouches[0].clientX;
    const diff = touchStartX.current - touchEndX;

    // Swipe left > 50px
    if (diff > 50 && isMobileSidebarOpen && onCloseMobileSidebar) {
      onCloseMobileSidebar();
    }
    touchStartX.current = null;
  };

  const showToastNotification = (message) => {
    setSidebarToast(message);
    setTimeout(() => {
      setSidebarToast(null);
    }, 3000);
  };

  const handleTitleMouseEnter = (e, title) => {
    const item = e.currentTarget;
    const titleEl = item.querySelector('.session-title, .corner-dropdown-name');
    if (titleEl && titleEl.scrollWidth > titleEl.clientWidth) {
      const rect = item.getBoundingClientRect();
      setHoveredTitle({ text: title, rect });
    }
  };

  const handleTitleMouseLeave = () => {
    setHoveredTitle({ text: '', rect: null });
  };

  const handleOptionsBtnMouseEnter = (e) => {
    e.stopPropagation();
    setHoveredTitle({ text: '', rect: null });
  };

  const handleUserHover = (e) => {
    const titleElems = e.currentTarget.querySelectorAll('[title]');
    titleElems.forEach((el) => {
      el.removeAttribute('title');
    });
  };

  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        if (event.target.closest('.session-options-btn')) {
          return;
        }
        setActiveMenuId(null);
        setActiveCornerMenuId(null);
      }
      if (cornersDropdownRef.current && !cornersDropdownRef.current.contains(event.target) && !event.target.closest('.corner-more-btn')) {
        setShowAllCorners(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleCornerMenuClick = (e, cornerId) => {
    e.stopPropagation();
    if (activeCornerMenuId === cornerId) {
      setActiveCornerMenuId(null);
    } else {
      const rect = e.currentTarget.getBoundingClientRect();
      setMenuPosition({
        top: rect.top,
        bottom: null,
        left: rect.right + 8
      });
      setActiveCornerMenuId(cornerId);
      setActiveMenuId(null);
    }
  };

  const handleRenameCorner = (e, corner) => {
    e.stopPropagation();
    setActiveCornerMenuId(null);
    setRenameData({ id: corner._id, title: corner.name, type: 'corner' });
  };

  const handleDeleteCornerClick = (e, corner) => {
    e.stopPropagation();
    setActiveCornerMenuId(null);
    setDeleteData({ id: corner._id, title: corner.name, type: 'corner' });
  };

  const handleMenuClick = (e, sessionId) => {
    e.stopPropagation();
    if (activeMenuId === sessionId) {
      setActiveMenuId(null);
    } else {
      const rect = e.currentTarget.getBoundingClientRect();
      setMenuPosition({
        top: null,
        bottom: window.innerHeight - rect.bottom,
        left: rect.right + 8
      });
      setActiveMenuId(sessionId);
      setActiveCornerMenuId(null);
    }
  };

  const handleMoreCornersClick = (e) => {
    e.stopPropagation();
    if (showAllCorners) {
      setShowAllCorners(false);
    } else {
      const rect = e.currentTarget.getBoundingClientRect();
      setMoreCornersPosition({
        top: rect.top,
        left: rect.right + 8
      });
      setShowAllCorners(true);
      setActiveMenuId(null);
      setActiveCornerMenuId(null);
    }
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
    setRenameData({ id: session._id, title: session.title, type: 'session' });
  };

  const handleRenameSave = async () => {
    if (!renameData.title.trim() || isActionProcessing) return;
    setIsActionProcessing(true);
    try {
      if (renameData.type === 'corner') {
        if (onUpdateCorner) {
          await onUpdateCorner(renameData.id, { name: renameData.title.trim() });
        }
      } else {
        await renameSession(renameData.id, renameData.title);
        if (onRefreshSessions) onRefreshSessions();
      }
    } catch (error) {
      console.error('Lỗi khi đổi tên:', error);
    } finally {
      setIsActionProcessing(false);
      setRenameData(null);
    }
  };

  const handleRenameCancel = () => {
    setRenameData(null);
  };

  const openDelete = (e, session) => {
    e.stopPropagation();
    setActiveMenuId(null);
    setDeleteData({ id: session._id, title: session.title, type: 'session' });
  };

  const handleDeleteConfirm = async () => {
    if (isActionProcessing) return;
    setIsActionProcessing(true);
    try {
      if (deleteData.type === 'corner') {
        if (onDeleteCorner) {
          await onDeleteCorner(deleteData.id);
          showToastNotification(`Đã xóa Góc "${deleteData.title}" thành công!`);
        }
      } else {
        await onDeleteSession(deleteData.id);
        showToastNotification('Đã xóa cuộc hội thoại thành công!');
      }
    } catch (error) {
      console.error('Lỗi khi xoá:', error);
    } finally {
      setIsActionProcessing(false);
      setDeleteData(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteData(null);
  };

  const filteredSessions = sessions?.filter(session => !session.corner_id) || [];

  return (
    <>
      {isOpen && (
        <div className="sidebar-overlay desktop-only" onClick={onToggle} />
      )}

      <aside
        className={`sidebar ${isOpen ? 'open' : 'collapsed'} ${isMobileSidebarOpen ? 'mobile-open' : ''}`}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        <div className="sidebar-top">
          <div className="sidebar-branding">
            {isOpen ? (
              <>
                <img src={theme === 'dark' ? '/images/logo_name_dark.png?v=20260601-0250' : '/images/Logo_name_light.png?v=20260601-0250'} alt="A.I.M Care" className="sidebar-logo-name" />
                <button
                  className="sidebar-toggle open-toggle"
                  onClick={window.innerWidth <= 768 ? onCloseMobileSidebar : onToggle}
                >
                  <X size={20} />
                </button>
              </>
            ) : (
              <button className="sidebar-toggle collapsed-toggle" onClick={onToggle}>
                <img src="/images/Logo_chat.png" alt="Chat" className="sidebar-logo-chat" />
                <div className="hover-menu-icon">
                  <Menu size={20} />
                </div>
              </button>
            )}
          </div>

          <button
            className={`new-chat-btn ${(!currentSessionId && !activeCorner && currentView === 'chat' && !isProfileOpen) ? 'active' : ''}`}
            onClick={onNewChat}
            data-tooltip={!isOpen ? "Cuộc trò chuyện mới" : undefined}
          >
            <SquarePen size={20} />
            <span>Cuộc trò chuyện mới</span>
          </button>

          <button
            className={`search-history-btn ${currentView === 'search' && !isProfileOpen ? 'active' : ''}`}
            onClick={onOpenSearch}
            data-tooltip={!isOpen ? "Tìm kiếm cuộc trò chuyện" : undefined}
          >
            <Search size={20} />
            <span>Tìm kiếm cuộc trò chuyện</span>
          </button>

          <button
            className={`profile-btn sidebar-profile-btn ${isProfileOpen ? 'active' : ''}`}
            onClick={onOpenProfile}
            data-tooltip={!isOpen ? "Hồ sơ sức khỏe" : undefined}
          >
            <ClipboardList size={20} />
            <span>Hồ sơ sức khỏe</span>
            {!profileCompleted && <span className="sidebar-red-dot" />}
          </button>
        </div>

        {/* Unified Scroll Container */}
        <div
          className="sidebar-scroll-container"
          style={{ overflowY: (activeMenuId !== null || activeCornerMenuId !== null || showAllCorners) ? 'hidden' : 'auto' }}
        >
          {/* Health Corners Section */}
          {isOpen && (
            <div className="corner-section" style={{ position: 'relative' }}>
              <div className="sidebar-sessions-header">Góc sức khỏe</div>

              <button className={`corner-add-btn ${currentView === 'corner-create' && !isProfileOpen ? 'active' : ''}`} onClick={onCreateCornerView}>
                <Plus size={20} />
                <span>Góc sức khỏe mới</span>
              </button>

              {healthCorners.slice(0, 2).map(corner => {
                const isCornerActive = !isProfileOpen && (
                  (currentView === 'corner' && activeCorner?._id === corner._id) ||
                  (currentView === 'chat' && currentSession?.corner_id === corner._id)
                );
                return (
                  <div
                    key={corner._id}
                    className={`session-item ${isCornerActive ? 'active' : ''}`}
                    onClick={() => onOpenCorner(corner)}
                    onMouseEnter={(e) => handleTitleMouseEnter(e, corner.name)}
                    onMouseLeave={handleTitleMouseLeave}
                  >
                    <div className="session-title-wrap">
                      <HeartPulse size={20} className="corner-item-icon" />
                      <span className="session-title">{corner.name}</span>
                    </div>

                    <button
                      className={`session-options-btn ${activeCornerMenuId === corner._id ? 'active' : ''}`}
                      onClick={(e) => handleCornerMenuClick(e, corner._id)}
                      onMouseEnter={handleOptionsBtnMouseEnter}
                    >
                      <MoreVertical size={16} />
                    </button>
                  </div>
                );
              })}

              {healthCorners.length > 2 && (
                <button
                  className={`corner-more-btn ${showAllCorners ? 'active' : ''}`}
                  onClick={handleMoreCornersClick}
                >
                  <MoreHorizontal size={20} className="corner-more-icon" />
                  <span>Tất cả góc sức khỏe</span>
                </button>
              )}
            </div>
          )}

          <nav className="sidebar-sessions">
            {(!filteredSessions || filteredSessions.length === 0) ? (
              <div className="empty-sessions">
                <p>Chưa có hội thoại nào</p>
                <span>Bắt đầu bằng cách gửi câu hỏi đầu tiên</span>
              </div>
            ) : (
              <>
                <div className="sidebar-sessions-header">Gần đây</div>
                {filteredSessions.map((session) => {
                  const isSessionActive = currentView === 'chat' && !isProfileOpen && currentSessionId === session._id;
                  return (
                    <div
                      key={session._id}
                      className={`session-item ${isSessionActive ? 'active' : ''}`}
                      onClick={() => onSelectSession(session._id)}
                      onMouseEnter={(e) => handleTitleMouseEnter(e, session.title)}
                      onMouseLeave={handleTitleMouseLeave}
                    >
                      <div className="session-title-wrap">
                        <span className={`session-title ${session.is_pinned ? 'is-pinned' : ''}`}>
                          {session.title}
                        </span>
                        {session.is_pinned && <Pin size={12} className="pinned-icon" />}
                      </div>

                      <button
                        className={`session-options-btn ${activeMenuId === session._id ? 'active' : ''}`}
                        onClick={(e) => handleMenuClick(e, session._id)}
                        onMouseEnter={handleOptionsBtnMouseEnter}
                      >
                        <MoreVertical size={16} />
                      </button>
                    </div>
                  );
                })}
              </>
            )}
          </nav>
        </div>

        <div className="sidebar-bottom">
          <div className="sidebar-bottom-row">
            <div
              className="sidebar-user-container"
              onMouseOver={handleUserHover}
            >
              <div className="sidebar-user-btn-container">
                <UserButton
                  appearance={{
                    elements: {
                      avatarBox: { width: '32px', height: '32px' },
                      userButtonPopoverCard: {
                        width: '280px',
                        maxWidth: '280px',
                      },
                      userButtonPopoverHeader: {
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        textAlign: 'center',
                      },
                      userButtonPopoverHeaderBox: {
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        textAlign: 'center',
                      },
                      userButtonPopoverHeaderTitle: {
                        textAlign: 'center',
                      },
                      userButtonPopoverHeaderSubtitle: {
                        textAlign: 'center',
                      },
                      userButtonPopoverActionButton: {
                        justifyContent: 'center',
                        textAlign: 'center',
                      },
                      userButtonPopoverActionButtonText: {
                        textAlign: 'center',
                        flex: 'none',
                      },
                      userButtonPopoverFooter: {
                        justifyContent: 'center',
                        textAlign: 'center',
                      }
                    },
                  }}
                />
              </div>
              {isOpen && user && (
                <div className="sidebar-user-info">
                  <span className="sidebar-username">
                    {user.fullName || user.username || user.primaryEmailAddress?.emailAddress || 'Tài khoản'}
                  </span>
                </div>
              )}
              {user && (
                <div className="custom-user-tooltip">
                  <div className="tooltip-line title">Tài khoản Google</div>
                  <div className="tooltip-line name">{user.fullName || user.username || 'Tài khoản'}</div>
                  <div className="tooltip-line email">{user.primaryEmailAddress?.emailAddress || ''}</div>
                </div>
              )}
            </div>

            <div className="settings-wrapper">
              <button
                className={`sidebar-settings-btn ${isSettingsOpen ? 'active' : ''}`}
                onClick={() => setIsSettingsOpen(!isSettingsOpen)}
              >
                <Settings size={20} />
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
                    {isAdmin && (
                      <button
                        className="dropdown-item admin-nav-btn"
                        onClick={() => {
                          onOpenAdmin();
                          setIsSettingsOpen(false);
                        }}
                      >
                        <ShieldCheck size={18} />
                        <span>Quản trị hệ thống</span>
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

      </aside>

      {/* Rename Confirmation Modal */}
      {renameData && (
        <div className="modal-overlay">
          <div className="modal-content rename-modal">
            <h3>{renameData.type === 'corner' ? 'Đổi tên cho Góc sức khỏe' : 'Đổi tên cho cuộc trò chuyện này'}</h3>
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
              <button className="modal-btn cancel-text" onClick={handleRenameCancel} disabled={isActionProcessing}>Huỷ</button>
              <button className="modal-btn save-text" onClick={handleRenameSave} disabled={isActionProcessing}>{isActionProcessing ? 'Đang lưu...' : 'Đổi tên'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteData && (
        <div className="modal-overlay">
          <div className="modal-content">
            {deleteData.type === 'corner' ? (
              <>
                <h3>Xóa Góc sức khỏe?</h3>
                <p style={{ lineHeight: '1.6', fontSize: '0.92rem', color: 'var(--text-secondary, #94a3b8)' }}>
                  Bạn có chắc chắn muốn xóa Góc sức khỏe <strong>"{deleteData.title}"</strong> không?
                  <br />
                  <span style={{ color: 'var(--accent-blue, #3b82f6)', fontWeight: '500' }}>Lưu ý:</span> Các cuộc trò chuyện bên trong Góc sẽ <strong style={{ color: 'var(--text-primary, #e2e8f0)' }}>không bị xóa</strong>. Chúng sẽ được tự động chuyển ra danh sách "Gần đây" ở thanh bên.
                </p>
                <div className="modal-actions">
                  <button className="modal-btn cancel" onClick={handleDeleteCancel} disabled={isActionProcessing}>Huỷ</button>
                  <button className="modal-btn delete" onClick={handleDeleteConfirm} disabled={isActionProcessing}>{isActionProcessing ? 'Đang xóa...' : 'Xóa'}</button>
                </div>
              </>
            ) : (
              <>
                <h3>Xoá cuộc hội thoại?</h3>
                <p>Bạn có chắc chắn muốn xoá cuộc hội thoại <strong>"{deleteData.title}"</strong> không? Hành động này không thể hoàn tác.</p>
                <div className="modal-actions">
                  <button className="modal-btn cancel" onClick={handleDeleteCancel} disabled={isActionProcessing}>Huỷ</button>
                  <button className="modal-btn delete" onClick={handleDeleteConfirm} disabled={isActionProcessing}>{isActionProcessing ? 'Đang xóa...' : 'Xoá'}</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Assign Session to Corner Modal */}
      {assignSessionData && (
        <div className="modal-overlay">
          <div className="modal-content assign-modal">
            <div className="assign-modal-header">
              <h3>Di chuyển cuộc trò chuyện</h3>
              <button className="close-btn" onClick={() => !isAssigning && setAssignSessionData(null)} disabled={isAssigning}>
                <X size={18} />
              </button>
            </div>
            <p className="assign-modal-sub">
              Chọn một Góc sức khỏe bạn muốn chuyển cuộc trò chuyện này vào
            </p>
            <div className="assign-corners-list">
              {isAssigning ? (
                <div className="assign-loading">
                  <RefreshCw size={24} className="spin" />
                  <p>Đang di chuyển cuộc trò chuyện...</p>
                </div>
              ) : (
                healthCorners.map(corner => (
                  <button
                    key={corner._id}
                    className="assign-corner-item"
                    disabled={isAssigning}
                    onClick={async () => {
                      setIsAssigning(true);
                      try {
                        await onAssignSession(assignSessionData.id, corner._id);
                        setAssignSessionData(null);
                        showToastNotification(`Đã di chuyển cuộc trò chuyện vào Góc "${corner.name}" thành công!`);
                      } catch (err) {
                        console.error("Error moving session:", err);
                      } finally {
                        setIsAssigning(false);
                      }
                    }}
                  >
                    <HeartPulse size={18} className="assign-corner-icon" />
                    <span className="assign-corner-name">{corner.name}</span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Sidebar Toast Notification */}
      {sidebarToast && (
        <div className="sidebar-toast-notification">
          <Check size={16} style={{ color: '#22c55e' }} />
          <span>{sidebarToast}</span>
        </div>
      )}

      {/* Floating Session Options Menu (Upwards) */}
      {activeMenuId && (
        (() => {
          const session = sessions?.find(s => s._id === activeMenuId);
          if (!session) return null;
          return (
            <div
              className="session-options-menu floating"
              style={{
                position: 'fixed',
                top: 'auto',
                bottom: `${menuPosition.bottom}px`,
                left: `${menuPosition.left}px`,
                zIndex: 10000
              }}
              ref={menuRef}
              onClick={(e) => e.stopPropagation()}
            >
              <button className="option-item" onClick={(e) => handlePin(e, session)}>
                {session.is_pinned ? (
                  <><PinOff size={14} /> Bỏ ghim</>
                ) : (
                  <><Pin size={14} /> Ghim</>
                )}
              </button>
              <button className="option-item" onClick={(e) => openRename(e, session)}>
                <Edit2 size={14} /> Đổi tên
              </button>
              {healthCorners?.length > 0 && (
                <button className="option-item" onClick={(e) => {
                  e.stopPropagation();
                  setActiveMenuId(null);
                  setAssignSessionData({ id: session._id, title: session.title });
                }}>
                  <FolderPlus size={14} /> Đưa vào Góc sức khỏe
                </button>
              )}
              <button className="option-item danger" onClick={(e) => openDelete(e, session)}>
                <Trash2 size={14} /> Xoá
              </button>
            </div>
          );
        })()
      )}

      {/* Floating Corner Options Menu (Downwards) */}
      {activeCornerMenuId && (
        (() => {
          const corner = healthCorners?.find(c => c._id === activeCornerMenuId);
          if (!corner) return null;
          return (
            <div
              className="session-options-menu floating"
              style={{
                position: 'fixed',
                top: `${menuPosition.top}px`,
                bottom: 'auto',
                left: `${menuPosition.left}px`,
                zIndex: 10000
              }}
              ref={menuRef}
              onClick={(e) => e.stopPropagation()}
            >
              <button className="option-item" onClick={(e) => handleRenameCorner(e, corner)}>
                <Edit2 size={14} /> Đổi tên
              </button>
              <button className="option-item option-delete" onClick={(e) => handleDeleteCornerClick(e, corner)}>
                <Trash2 size={14} /> Xoá Góc
              </button>
            </div>
          );
        })()
      )}

      {/* Floating All Corners Dropdown */}
      {showAllCorners && (
        (() => {
          return (
            <div
              className="corner-more-dropdown floating"
              style={{
                position: 'fixed',
                top: `${moreCornersPosition.top}px`,
                bottom: 'auto',
                left: `${moreCornersPosition.left}px`,
                maxHeight: '210px',
                overflowY: 'auto',
                zIndex: 10000
              }}
              ref={cornersDropdownRef}
              onClick={(e) => e.stopPropagation()}
            >
              {healthCorners.map(corner => {
                const isCornerActive = !isProfileOpen && (
                  (currentView === 'corner' && activeCorner?._id === corner._id) ||
                  (currentView === 'chat' && currentSession?.corner_id === corner._id)
                );
                return (
                  <div
                    key={corner._id}
                    className={`corner-dropdown-item ${isCornerActive ? 'active' : ''}`}
                    onClick={() => {
                      onOpenCorner(corner);
                      setShowAllCorners(false);
                    }}
                    onMouseEnter={(e) => handleTitleMouseEnter(e, corner.name)}
                    onMouseLeave={handleTitleMouseLeave}
                  >
                    <HeartPulse size={16} className="corner-dropdown-icon" />
                    <span className="corner-dropdown-name">{corner.name}</span>
                  </div>
                );
              })}
            </div>
          );
        })()
      )}

      {/* Floating Tooltip for Truncated Titles */}
      {hoveredTitle.text && hoveredTitle.rect && (
        <div
          key={hoveredTitle.text}
          className="sidebar-floating-tooltip"
          style={{
            position: 'fixed',
            top: `${hoveredTitle.rect.top + hoveredTitle.rect.height / 2}px`,
            left: `${hoveredTitle.rect.left + hoveredTitle.rect.width + 12}px`,
            zIndex: 100000,
            pointerEvents: 'none'
          }}
        >
          <div className="tooltip-arrow" />
          <div className="tooltip-content">{hoveredTitle.text}</div>
        </div>
      )}
    </>
  );
};

export default Sidebar;
