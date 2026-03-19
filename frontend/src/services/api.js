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
 * Send chat message to API
 */
export const sendChatMessage = async (query, healthProfile) => {
  try {
    const response = await api.post('/api/chat', {
      query,
      health_profile: healthProfile,
    });
    return response.data;
  } catch (error) {
    console.error('Error sending chat message:', error);
    throw error;
  }
};

/**
 * Save user health profile
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

export default api;
