import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || `${window.location.protocol}//${window.location.hostname}:8000`;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60 seconds timeout
});

/**
 * Axios interceptor: auto-attach Clerk JWT Bearer token to every request.
 *
 * Uses the global Clerk instance (window.Clerk) which is initialized by
 * <ClerkProvider> in index.js. This approach avoids needing React hooks
 * inside a plain JS module.
 */
api.interceptors.request.use(async (config) => {
  try {
    if (window.Clerk && window.Clerk.session) {
      const token = await window.Clerk.session.getToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
  } catch (error) {
    console.warn('Failed to attach auth token:', error);
  }
  return config;
});

/**
 * Send chat message to API
 */
export const sendChatMessage = async (query, healthProfile, sessionId = null) => {
  try {
    const payload = {
      query,
      health_profile: healthProfile,
    };
    if (sessionId) {
      payload.session_id = sessionId;
    }
    const response = await api.post('/api/chat', payload);
    return response.data;
  } catch (error) {
    console.error('Error sending chat message:', error);
    throw error;
  }
};

/**
 * Retrieve user health profile from backend
 */
export const getHealthProfile = async () => {
  try {
    const response = await api.get('/api/profile');
    return response.data;
  } catch (error) {
    console.error('Error getting health profile:', error);
    throw error;
  }
};


/**
 * Save user health profile to backend (full overwrite)
 */
export const saveHealthProfile = async (profile) => {
  try {
    const response = await api.post('/api/profile', profile);
    return response.data;
  } catch (error) {
    console.error('Error saving health profile:', error);
    throw error;
  }
};

/**
 * Update user health profile partially (Differential Payload)
 */
export const patchHealthProfile = async (partialProfile) => {
  try {
    const response = await api.patch('/api/profile', partialProfile);
    return response.data;
  } catch (error) {
    console.error('Error patching health profile:', error);
    throw error;
  }
};

/**
 * Check API health status
 */
export const checkHealth = async () => {
  try {
    const response = await api.get('/health');
    return response.data;
  } catch (error) {
    console.error('Error checking health:', error);
    throw error;
  }
};

/**
 * Get API statistics
 */
export const getStats = async () => {
  try {
    const response = await api.get('/api/stats');
    return response.data;
  } catch (error) {
    console.error('Error getting stats:', error);
    throw error;
  }
};

/**
 * Get all chat sessions
 */
export const getSessions = async () => {
  try {
    const response = await api.get('/api/sessions');
    return response.data;
  } catch (error) {
    console.error('Error getting sessions:', error);
    throw error;
  }
};

/**
 * Search chat sessions using Hybrid Search (BM25 + Semantic + RRF)
 */
export const searchSessions = async (keyword) => {
  try {
    const response = await api.get('/api/sessions/search', {
      params: { q: keyword },
    });
    return response.data;
  } catch (error) {
    console.error('Error searching sessions:', error);
    throw error;
  }
};

/**
 * Get messages for a specific session
 */
export const getSessionMessages = async (sessionId) => {
  try {
    const response = await api.get(`/api/sessions/${sessionId}/messages`);
    return response.data;
  } catch (error) {
    console.error(`Error getting messages for session ${sessionId}:`, error);
    throw error;
  }
};

/**
 * Delete a specific chat session
 */
export const deleteSession = async (sessionId) => {
  try {
    const response = await api.delete(`/api/sessions/${sessionId}`);
    return response.data;
  } catch (error) {
    console.error(`Error deleting session ${sessionId}:`, error);
    throw error;
  }
};

/**
 * Delete the last Q&A turn of a chat session
 */
export const deleteLastQA = async (sessionId) => {
  try {
    const response = await api.delete(`/api/sessions/${sessionId}/last-qa`);
    return response.data;
  } catch (error) {
    console.error(`Error deleting last Q&A for session ${sessionId}:`, error);
    throw error;
  }
};


/**
 * Rename a specific chat session
 */
export const renameSession = async (sessionId, newTitle) => {
  try {
    const response = await api.put(`/api/sessions/${sessionId}/rename`, { title: newTitle });
    return response.data;
  } catch (error) {
    console.error(`Error renaming session ${sessionId}:`, error);
    throw error;
  }
};

/**
 * Pin or unpin a specific chat session
 */
export const pinSession = async (sessionId, isPinned) => {
  try {
    const response = await api.put(`/api/sessions/${sessionId}/pin`, { is_pinned: isPinned });
    return response.data;
  } catch (error) {
    console.error(`Error pinning session ${sessionId}:`, error);
    throw error;
  }
};

/**
 * Suggestions API: Bệnh tiền sử
 */
export const suggestConditions = async (query) => {
  try {
    const response = await api.get('/api/suggestions/conditions', { params: { q: query } });
    return response.data;
  } catch (error) {
    console.error('Error suggesting conditions:', error);
    return { items: [], total: 0 };
  }
};

/**
 * Suggestions API: Dị ứng hoạt chất
 */
export const suggestIngredients = async (query) => {
  try {
    const response = await api.get('/api/suggestions/ingredients', { params: { q: query } });
    return response.data;
  } catch (error) {
    console.error('Error suggesting ingredients:', error);
    return { items: [], total: 0 };
  }
};

/**
 * Suggestions API: Thuốc đang sử dụng
 */
export const suggestMedications = async (query, category) => {
  try {
    const response = await api.get('/api/suggestions/medications', { 
      params: { q: query, category: category } 
    });
    return response.data;
  } catch (error) {
    console.error('Error suggesting medications:', error);
    return { items: [], total: 0 };
  }
};

/**
 * Suggestions API: Lấy danh sách nhóm thuốc
 */
export const getMedicationCategories = async () => {
  try {
    const response = await api.get('/api/suggestions/categories');
    return response.data;
  } catch (error) {
    console.error('Error getting categories:', error);
    return { categories: [], total: 0 };
  }
};

/**
 * Send chat message with SSE streaming.
 * Uses fetch() + ReadableStream instead of Axios for streaming support.
 *
 * @param {string} query - User's question
 * @param {object} healthProfile - User health profile
 * @param {string|null} sessionId - Existing session ID
 * @param {object} callbacks - Event handlers:
 *   onToken(text), onStatus(message), onDone(data),
 *   onWarnings(warnings), onReplace(content), onError(message),
 *   onAbort() 
 * @param {AbortSignal} signal - Optional AbortSignal to cancel the request
 */
export const sendChatMessageStream = async (query, healthProfile, sessionId, callbacks = {}, signal = null, cornerId = null) => {
  const { onToken, onStatus, onDone, onWarnings, onReplace, onError, onAbort, onSuggestions } = callbacks;

  let token = null;
  try {
    if (window.Clerk && window.Clerk.session) {
      token = await window.Clerk.session.getToken();
    }
  } catch (err) {
    console.warn('Failed to get auth token for streaming:', err);
  }

  const payload = { query };
  if (sessionId) payload.session_id = sessionId;
  if (cornerId) payload.corner_id = cornerId;

  try {
    const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      signal, // Pass the abort signal
    });

    if (!response.ok) {
      const errorText = await response.text();
      if (onError) onError(errorText || `HTTP ${response.status}`);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop();

      let currentEvent = null;
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith('data: ') && currentEvent) {
          const rawData = line.slice(6);
          try {
            const data = JSON.parse(rawData);

            switch (currentEvent) {
              case 'token':
                if (onToken) onToken(data.content);
                break;
              case 'status':
                if (onStatus) onStatus(data.message);
                break;
              case 'done':
                if (onDone) onDone(data);
                break;
              case 'warnings':
                if (onWarnings) onWarnings(data);
                break;
              case 'replace':
                if (onReplace) onReplace(data.content);
                break;
              case 'suggestions':
                if (onSuggestions) onSuggestions(data.items || []);
                break;
              case 'error':
                if (onError) onError(data.message);
                break;
              default:
                break;
            }
          } catch (parseErr) {
            console.warn('SSE parse error:', parseErr, rawData);
          }
          currentEvent = null;
        }
      }
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      console.log('Stream aborted by user');
      if (onAbort) onAbort();
    } else {
      console.error('Fetch error:', error);
      if (onError) onError(error.message);
      throw error;
    }
  }
};

/**
 * Submit user feedback (Like/Dislike) for an AI message.
 * Fire-and-forget: backend trả 202 ngay lập tức.
 */
export const submitFeedback = async (feedbackPayload) => {
  try {
    const response = await api.post('/api/feedback', feedbackPayload);
    return response.data;
  } catch (error) {
    console.error('Error submitting feedback:', error);
    throw error;
  }
};

/**
 * Admin: Lấy danh sách feedback với filter và phân trang.
 */
export const getAdminFeedbacks = async ({ page = 1, limit = 20, status, tag, rating, date_range } = {}) => {
  try {
    const params = { page, limit };
    if (status) params.status = status;
    if (tag) params.tag = tag;
    if (rating !== undefined && rating !== null) params.rating = rating;
    if (date_range) params.date_range = date_range;
    const response = await api.get('/api/admin/feedbacks', { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching admin feedbacks:', error);
    throw error;
  }
};

/**
 * Admin: Xóa vĩnh viễn (Hard Delete) một feedback.
 */
export const deleteFeedback = async (feedbackId) => {
  try {
    const response = await api.delete(`/api/admin/feedbacks/${feedbackId}`);
    return response.data;
  } catch (error) {
    console.error('Error deleting feedback:', error);
    throw error;
  }
};

/**
 * Admin: Cập nhật trạng thái và ghi chú cho một feedback.
 */
export const updateFeedbackStatus = async (feedbackId, { status, admin_notes }) => {
  try {
    const response = await api.patch(`/api/admin/feedbacks/${feedbackId}`, { status, admin_notes });
    return response.data;
  } catch (error) {
    console.error('Error updating feedback:', error);
    throw error;
  }
};

/**
 * Admin: Lấy số liệu thống kê tổng quan cho Dashboard.
 */
export const getAdminStats = async () => {
  try {
    const response = await api.get('/api/admin/stats');
    return response.data;
  } catch (error) {
    console.error('Error fetching admin stats:', error);
    throw error;
  }
};

/**
 * Admin: Xử lý hàng loạt feedback (Bulk Resolve).
 */
export const bulkResolveFeedbacks = async (tag) => {
  try {
    const payload = tag ? { tag } : {};
    const response = await api.patch('/api/admin/feedbacks/bulk-resolve', payload);
    return response.data;
  } catch (error) {
    console.error('Error in bulk resolve:', error);
    throw error;
  }
};

/**
 * Admin: Lấy danh sách từ điển y khoa (conditions / medications / ingredients).
 */
export const getDictionaryItems = async (type, { q = '', field = 'all', letter = '', page = 1, limit = 20 } = {}) => {
  try {
    const response = await api.get(`/api/admin/dictionary/${type}`, { params: { q, field, letter, page, limit } });
    return response.data;
  } catch (error) {
    console.error(`Error fetching dictionary ${type}:`, error);
    throw error;
  }
};

/**
 * Admin: Thêm mới một bản ghi vào từ điển y khoa.
 */
export const createDictionaryItem = async (type, item) => {
  try {
    const response = await api.post(`/api/admin/dictionary/${type}`, item);
    return response.data;
  } catch (error) {
    console.error(`Error creating dictionary ${type}:`, error);
    throw error;
  }
};

/**
 * Admin: Cập nhật bản ghi trong từ điển y khoa.
 */
export const updateDictionaryItem = async (type, id, item) => {
  try {
    const response = await api.put(`/api/admin/dictionary/${type}/${id}`, item);
    return response.data;
  } catch (error) {
    console.error(`Error updating dictionary ${type}/${id}:`, error);
    throw error;
  }
};

/**
 * Admin: Xóa bản ghi khỏi từ điển y khoa.
 */
export const deleteDictionaryItem = async (type, id) => {
  try {
    const response = await api.delete(`/api/admin/dictionary/${type}/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Error deleting dictionary ${type}/${id}:`, error);
    throw error;
  }
};

/**
 * Admin: Lấy cấu hình hệ thống (System Settings).
 */
export const getSystemSettings = async () => {
  try {
    const response = await api.get('/api/admin/system-settings');
    return response.data;
  } catch (error) {
    console.error('Error fetching system settings:', error);
    throw error;
  }
};

/**
 * Admin: Cập nhật cấu hình hệ thống (System Settings).
 */
export const updateSystemSettings = async (settingsData) => {
  try {
    const response = await api.put('/api/admin/system-settings', settingsData);
    return response.data;
  } catch (error) {
    console.error('Error updating system settings:', error);
    throw error;
  }
};

/**
 * Admin: Lấy danh sách Unsafe Logs (Câu hỏi bị chặn).
 * Hỗ trợ lọc theo category và tìm kiếm keyword.
 */
export const getUnsafeLogs = async (page = 1, limit = 20, category = null, search = null) => {
  try {
    const params = { page, limit };
    if (category) params.category = category;
    if (search) params.search = search;
    const response = await api.get('/api/admin/unsafe-logs', { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching unsafe logs:', error);
    throw error;
  }
};

/**
 * Admin: Xóa một unsafe log theo ID.
 */
export const deleteUnsafeLog = async (logId) => {
  try {
    const response = await api.delete(`/api/admin/unsafe-logs/${logId}`);
    return response.data;
  } catch (error) {
    console.error('Error deleting unsafe log:', error);
    throw error;
  }
};

/**
 * Admin: Xóa toàn bộ unsafe logs.
 */
export const clearUnsafeLogs = async () => {
  try {
    const response = await api.delete('/api/admin/unsafe-logs/clear');
    return response.data;
  } catch (error) {
    console.error('Error clearing unsafe logs:', error);
    throw error;
  }
};

/**
 * Admin: Lấy thống kê Unsafe Logs.
 */
export const getUnsafeStats = async () => {
  try {
    const response = await api.get('/api/admin/unsafe-stats');
    return response.data;
  } catch (error) {
    console.error('Error fetching unsafe stats:', error);
    throw error;
  }
};

/**
 * Admin: Lấy danh sách User rủi ro (nhiều vi phạm nhất).
 */
export const getUnsafeUsers = async () => {
  try {
    const response = await api.get('/api/admin/unsafe-users');
    return response.data;
  } catch (error) {
    console.error('Error fetching unsafe users:', error);
    throw error;
  }
};

/**
 * Admin: Cấm/Mở cấm user.
 */
export const toggleBanUser = async (userId) => {
  try {
    const response = await api.post(`/api/admin/users/${userId}/ban`);
    return response.data;
  } catch (error) {
    console.error('Error toggling ban user:', error);
    throw error;
  }
};

/**
 * Admin: Làm mới bộ nhớ đệm (RAM Cache suggestions)
 */
export const refreshSuggestionCache = async () => {
  try {
    const response = await api.post('/api/suggestions/refresh-cache');
    return response.data;
  } catch (error) {
    console.error('Error refreshing suggestion cache:', error);
    throw error;
  }
};

export default api;


// ===== HEALTH CORNERS API =====

/**
 * Lấy danh sách Góc sức khỏe của user hiện tại
 */
export const getCorners = async () => {
  try {
    const response = await api.get('/api/corners');
    return response.data;
  } catch (error) {
    console.error('Error fetching health corners:', error);
    throw error;
  }
};

/**
 * Tạo Góc sức khỏe mới
 * @param {string} name - Tên Góc sức khỏe
 * @param {string} emoji - Emoji đại diện (default: 🩺)
 */
export const createCorner = async (name, emoji = '🩺') => {
  try {
    const response = await api.post('/api/corners', { name, emoji });
    return response.data;
  } catch (error) {
    console.error('Error creating health corner:', error);
    throw error;
  }
};

/**
 * Cập nhật tên/emoji Góc sức khỏe
 * @param {string} cornerId - ID của Góc
 * @param {object} data - { name?, emoji? }
 */
export const updateCorner = async (cornerId, data) => {
  try {
    const response = await api.put(`/api/corners/${cornerId}`, data);
    return response.data;
  } catch (error) {
    console.error('Error updating health corner:', error);
    throw error;
  }
};

/**
 * Xóa Góc sức khỏe (sessions sẽ được unlink, không bị xóa)
 * @param {string} cornerId - ID của Góc
 */
export const deleteCorner = async (cornerId) => {
  try {
    const response = await api.delete(`/api/corners/${cornerId}`);
    return response.data;
  } catch (error) {
    console.error('Error deleting health corner:', error);
    throw error;
  }
};

/**
 * Gắn hoặc gỡ session vào/khỏi Góc sức khỏe
 * @param {string} sessionId - ID session
 * @param {string|null} cornerId - ID Góc (null để gỡ)
 */
export const assignSessionToCorner = async (sessionId, cornerId) => {
  try {
    const response = await api.put(`/api/sessions/${sessionId}/corner`, {
      corner_id: cornerId
    });
    return response.data;
  } catch (error) {
    console.error('Error assigning session to corner:', error);
    throw error;
  }
};

/**
 * Lấy danh sách sessions thuộc một Góc sức khỏe
 * @param {string} cornerId - ID của Góc
 */
export const getCornerSessions = async (cornerId) => {
  try {
    const response = await api.get(`/api/corners/${cornerId}/sessions`);
    return response.data;
  } catch (error) {
    console.error('Error fetching corner sessions:', error);
    throw error;
  }
};
