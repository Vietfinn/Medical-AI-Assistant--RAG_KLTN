import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

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
 * Save user health profile to backend (synced to MongoDB)
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
export const sendChatMessageStream = async (query, healthProfile, sessionId, callbacks = {}, signal = null) => {
  const { onToken, onStatus, onDone, onWarnings, onReplace, onError, onAbort } = callbacks;

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

export default api;
