import React, { useState, useEffect, useCallback } from 'react';
import { X, Plus, Loader2, ClipboardList } from 'lucide-react';
import { 
  suggestConditions, 
  suggestIngredients, 
  suggestMedications, 
  patchHealthProfile 
} from '../services/api';
import './HealthProfile.css';

const HealthProfile = ({ profile, onProfileChange, isOpen, onClose }) => {
  const [draft, setDraft] = useState(profile || {});
  const [isSaving, setIsSaving] = useState(false);
  const [errors, setErrors] = useState({});
  
  const [newDisease, setNewDisease] = useState('');
  const [newAllergy, setNewAllergy] = useState('');
  const [newMedication, setNewMedication] = useState('');
  
  const [diseaseSugg, setDiseaseSugg] = useState([]);
  const [allergySugg, setAllergySugg] = useState([]);
  const [medSugg, setMedSugg] = useState([]);
  
  const [showDiseaseSugg, setShowDiseaseSugg] = useState(false);
  const [showAllergySugg, setShowAllergySugg] = useState(false);
  const [showMedSugg, setShowMedSugg] = useState(false);

  useEffect(() => {
    if (profile) setDraft(profile);
  }, [profile]);

  useEffect(() => {
    if (isOpen) document.body.style.overflow = 'hidden';
    else document.body.style.overflow = '';
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  useEffect(() => {
    const handleClick = (e) => {
      if (!e.target.closest('.hp-input-wrapper')) {
        setShowDiseaseSugg(false);
        setShowAllergySugg(false);
        setShowMedSugg(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const calculateBMI = () => {
    const { height, weight } = draft;
    if (!height || !weight || height <= 0) return null;
    const h_m = height > 3 ? height / 100 : height;
    if (h_m < 0.3 || h_m > 2.5) return null;
    return (weight / (h_m * h_m)).toFixed(1);
  };

  const getBMIStatus = (bmi) => {
    if (!bmi) return '';
    if (bmi < 18.5) return 'Thiếu cân';
    if (bmi < 25) return 'Bình thường';
    if (bmi < 30) return 'Thừa cân';
    return 'Béo phì';
  };

  const getChangedFields = () => {
    const changes = {};
    const fields = ['height', 'weight', 'age', 'gender', 'chronic_diseases', 'allergies', 'current_medications'];
    
    fields.forEach(field => {
      if (Array.isArray(draft[field])) {
        const originalArray = profile[field] || [];
        if (JSON.stringify(draft[field]) !== JSON.stringify(originalArray)) {
          changes[field] = draft[field];
        }
      } else if (draft[field] !== profile[field]) {
        changes[field] = draft[field];
      }
    });
    return changes;
  };

  const handleFinalClose = async () => {
    if (isSaving) return;
    const changes = getChangedFields();
    
    if (Object.keys(changes).length > 0) {
      setIsSaving(true);
      try {
        await patchHealthProfile(changes);
        onProfileChange({ ...profile, ...changes });
        setTimeout(() => {
          setIsSaving(false);
          onClose();
        }, 300);
      } catch (error) {
        console.error("Failed to sync profile:", error);
        setIsSaving(false);
        alert("Không thể lưu hồ sơ. Vui lòng thử lại.");
      }
    } else {
      onClose();
    }
  };

  const debounce = (func, wait) => {
    let timeout;
    return (...args) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const fetchDisease = useCallback(debounce(async (q) => {
    const data = await suggestConditions(q);
    setDiseaseSugg(data.items || []);
  }, 300), []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const fetchAllergy = useCallback(debounce(async (q) => {
    const data = await suggestIngredients(q);
    setAllergySugg(data.items || []);
  }, 300), []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const fetchMed = useCallback(debounce(async (q) => {
    const data = await suggestMedications(q);
    setMedSugg(data.items || []);
  }, 300), []);

  const updateDraft = (key, value) => {
    // Validate for age, height, weight
    if (['age', 'height', 'weight'].includes(key)) {
      if (value !== null && value !== '' && value <= 0) {
        setErrors(prev => ({ ...prev, [key]: 'Giá trị phải lớn hơn 0' }));
        setDraft(prev => ({ ...prev, [key]: '' }));
        return;
      } else {
        // Clear error if valid
        setErrors(prev => ({ ...prev, [key]: null }));
      }
    }
    setDraft(prev => ({ ...prev, [key]: value }));
  };

  const addTag = (key, value) => {
    if (!value.trim()) return;
    const list = draft[key] || [];
    if (!list.includes(value)) {
      updateDraft(key, [...list, value]);
    }
  };

  const removeTag = (key, index) => {
    const list = [...(draft[key] || [])];
    list.splice(index, 1);
    updateDraft(key, list);
  };

  if (!isOpen) return null;
  const bmi = calculateBMI();

  return (
    <div className="hp-modal-overlay" onClick={(e) => e.target === e.currentTarget && handleFinalClose()}>
      <div className={`hp-modal-card ${isSaving ? 'is-saving' : ''}`}>
        
        <div className="hp-modal-header">
          <div className="hp-modal-title-row">
            <ClipboardList className="hp-title-icon" size={22} />
            <h2>Hồ sơ Sức khỏe</h2>
          </div>
          <button className="hp-modal-close" onClick={handleFinalClose} disabled={isSaving}>
            {isSaving ? <Loader2 className="spinner" size={20} /> : <X size={24} />}
          </button>
        </div>

        <div className="hp-modal-body">
          {/* USER INFO */}
          <div className="profile-section">
            <div className="section-label"><h4>Thông tin cá nhân</h4></div>
            <div className="info-grid">
              <div className="info-field">
                <label>Tuổi</label>
                <input 
                  type="number" 
                  className={errors.age ? 'input-error' : ''}
                  value={draft.age || ''} 
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === '') {
                      updateDraft('age', '');
                      return;
                    }
                    const num = parseInt(val, 10);
                    if (!isNaN(num) && num > 0) {
                      updateDraft('age', num);
                    }
                  }}
                  onKeyDown={(e) => {
                    // Chặn phím e, E, +, -, kí tự đặc biệt và dấu chấm thập phân
                    if (['e', 'E', '+', '-', '.'].includes(e.key)) {
                      e.preventDefault();
                    }
                  }}
                  placeholder="Nhập tuổi"
                  min="1"
                />
                {errors.age && <span className="error-text">{errors.age}</span>}
              </div>
              <div className="info-field">
                <label>Giới tính</label>
                <select
                  value={draft.gender || ''}
                  onChange={(e) => updateDraft('gender', e.target.value)}
                >
                  <option value="">-- Chọn --</option>
                  <option value="Nam">Nam</option>
                  <option value="Nữ">Nữ</option>
                  <option value="Khác">Khác</option>
                </select>
              </div>
              <div className="info-field">
                <label>Chiều cao (cm)</label>
                <input 
                  type="number" 
                  className={errors.height ? 'input-error' : ''}
                  value={draft.height || ''} 
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === '') {
                      updateDraft('height', '');
                      return;
                    }
                    const num = parseFloat(val);
                    if (!isNaN(num) && num > 0) {
                      updateDraft('height', num);
                    }
                  }}
                  onKeyDown={(e) => {
                    // Chặn ký tự e, E, +, -, kí tự đặc biệt
                    if (['e', 'E', '+', '-'].includes(e.key)) {
                      e.preventDefault();
                    }
                  }}
                  placeholder="Ví dụ: 170"
                  min="1"
                  step="any"
                />
                {errors.height && <span className="error-text">{errors.height}</span>}
              </div>
              <div className="info-field">
                <label>Cân nặng (kg)</label>
                <input 
                  type="number" 
                  className={errors.weight ? 'input-error' : ''}
                  value={draft.weight || ''} 
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === '') {
                      updateDraft('weight', '');
                      return;
                    }
                    const num = parseFloat(val);
                    if (!isNaN(num) && num > 0) {
                      updateDraft('weight', num);
                    }
                  }}
                  onKeyDown={(e) => {
                    // Chặn ký tự e, E, +, -, kí tự đặc biệt
                    if (['e', 'E', '+', '-'].includes(e.key)) {
                      e.preventDefault();
                    }
                  }}
                  placeholder="Ví dụ: 65"
                  min="1"
                  step="any"
                />
                {errors.weight && <span className="error-text">{errors.weight}</span>}
              </div>
              {bmi && (
                <div className={`hp-bmi-info hp-bmi-${
                  getBMIStatus(bmi) === 'Thiếu cân' ? 'under' :
                  getBMIStatus(bmi) === 'Bình thường' ? 'normal' :
                  getBMIStatus(bmi) === 'Thừa cân' ? 'over' : 'obese'
                }`}>
                  <span className="hp-bmi-icon">🩺</span>
                  <div className="hp-bmi-text">
                    Chỉ số BMI: <strong className="hp-bmi-val">{bmi}</strong>
                    <span className="hp-bmi-divider">•</span>
                    Thể trạng: <strong className="hp-bmi-status">{getBMIStatus(bmi)}</strong>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* DISEASES */}
          <div className={`profile-section ${showDiseaseSugg ? 'active-sugg' : ''}`}>
            <div className="section-label"><h4>Bệnh lý tiền sử</h4></div>
            <div className="tags">
              {draft.chronic_diseases?.map((d, i) => (
                <div key={i} className="tag">
                  {d} <button onClick={() => removeTag('chronic_diseases', i)}><X size={14} /></button>
                </div>
              ))}
            </div>
            <div className="add-input">
              <div className="hp-input-wrapper">
                <input 
                  type="text" 
                  placeholder="Nhập hoặc tìm bệnh lý (VD: Tiểu đường)..."
                  value={newDisease}
                  onChange={(e) => {
                    setNewDisease(e.target.value);
                    setShowDiseaseSugg(true);
                    setShowAllergySugg(false);
                    setShowMedSugg(false);
                    fetchDisease(e.target.value);
                  }}
                  onFocus={() => {
                    setShowDiseaseSugg(true);
                    setShowAllergySugg(false);
                    setShowMedSugg(false);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addTag('chronic_diseases', newDisease);
                      setNewDisease('');
                      setShowDiseaseSugg(false);
                    }
                  }}
                />
                {showDiseaseSugg && diseaseSugg.length > 0 && (
                  <div className="suggestion-dropdown">
                    {diseaseSugg.map((s, i) => (
                      <div key={i} className="suggestion-item" onClick={() => {
                        addTag('chronic_diseases', s.label);
                        setNewDisease('');
                        setShowDiseaseSugg(false);
                      }}>
                        <span className="suggestion-label">{s.label}</span>
                        <span className="suggestion-category">{s.category || s.value}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <button onClick={() => {
                addTag('chronic_diseases', newDisease);
                setNewDisease('');
                setShowDiseaseSugg(false);
              }} disabled={!newDisease.trim()}>
                <Plus size={18} />
              </button>
            </div>
          </div>

          {/* ALLERGIES */}
          <div className={`profile-section ${showAllergySugg ? 'active-sugg' : ''}`}>
            <div className="section-label"><h4>Dị ứng hoạt chất</h4></div>
            <div className="tags">
              {draft.allergies?.map((a, i) => (
                <div key={i} className="tag tag-warning">
                  {a} <button onClick={() => removeTag('allergies', i)}><X size={14} /></button>
                </div>
              ))}
            </div>
            <div className="add-input">
              <div className="hp-input-wrapper">
                <input 
                  type="text" 
                  placeholder="Tìm hoạt chất gây dị ứng (VD: Penicillin)..."
                  value={newAllergy}
                  onChange={(e) => {
                    setNewAllergy(e.target.value);
                    setShowAllergySugg(true);
                    setShowDiseaseSugg(false);
                    setShowMedSugg(false);
                    fetchAllergy(e.target.value);
                  }}
                  onFocus={() => {
                    setShowAllergySugg(true);
                    setShowDiseaseSugg(false);
                    setShowMedSugg(false);
                    if (allergySugg.length === 0) fetchAllergy('');
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addTag('allergies', newAllergy);
                      setNewAllergy('');
                      setShowAllergySugg(false);
                    }
                  }}
                />
                {showAllergySugg && allergySugg.length > 0 && (
                  <div className="suggestion-dropdown">
                    {allergySugg.map((s, i) => (
                      <div key={i} className="suggestion-item" onClick={() => {
                        addTag('allergies', s.label);
                        setNewAllergy('');
                        setShowAllergySugg(false);
                      }}>
                        <span className="suggestion-label">{s.label}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <button onClick={() => {
                addTag('allergies', newAllergy);
                setNewAllergy('');
                setShowAllergySugg(false);
              }} disabled={!newAllergy.trim()}>
                <Plus size={18} />
              </button>
            </div>
          </div>

          {/* MEDICATIONS */}
          <div className={`profile-section ${showMedSugg ? 'active-sugg' : ''}`}>
            <div className="section-label"><h4>Thuốc đang sử dụng</h4></div>
            <div className="tags">
              {draft.current_medications?.map((m, i) => (
                <div key={i} className="tag tag-info">
                  {m} <button onClick={() => removeTag('current_medications', i)}><X size={14} /></button>
                </div>
              ))}
            </div>
            <div className="add-input">
              <div className="hp-input-wrapper">
                <input 
                  type="text" 
                  placeholder="Tìm thuốc bạn đang dùng..."
                  value={newMedication}
                  onChange={(e) => {
                    setNewMedication(e.target.value);
                    setShowMedSugg(true);
                    setShowDiseaseSugg(false);
                    setShowAllergySugg(false);
                    fetchMed(e.target.value);
                  }}
                  onFocus={() => {
                    setShowMedSugg(true);
                    setShowDiseaseSugg(false);
                    setShowAllergySugg(false);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addTag('current_medications', newMedication);
                      setNewMedication('');
                      setShowMedSugg(false);
                    }
                  }}
                />
                {showMedSugg && medSugg.length > 0 && (
                  <div className="suggestion-dropdown">
                    {medSugg.map((s, i) => (
                      <div key={i} className="suggestion-item" onClick={() => {
                        addTag('current_medications', s.label);
                        setNewMedication('');
                        setShowMedSugg(false);
                      }}>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span className="suggestion-label">{s.label}</span>
                          <span className="suggestion-category">{s.category}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <button onClick={() => {
                addTag('current_medications', newMedication);
                setNewMedication('');
                setShowMedSugg(false);
              }} disabled={!newMedication.trim()}>
                <Plus size={18} />
              </button>
            </div>
          </div>

          <div className="profile-note">
            💡 Hồ sơ sức khỏe giúp AI đưa ra lời khuyên y tế chính xác và cá nhân hóa hơn. Thông tin của bạn được bảo mật an toàn.
          </div>
        </div>

        <div className="hp-modal-footer">
          {isSaving ? (
            <div className="saving-indicator">
              <Loader2 className="spinner" size={16} />
              <span>Đang lưu thông tin...</span>
            </div>
          ) : (
            <span>Hệ thống tự động lưu khi bạn đóng cửa sổ này.</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default HealthProfile;
