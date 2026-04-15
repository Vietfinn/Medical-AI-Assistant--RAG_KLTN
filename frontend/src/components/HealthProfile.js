import React, { useState, useEffect } from 'react';
import { X, Plus, User, Heart, AlertTriangle, Pill } from 'lucide-react';
import './HealthProfile.css';

const HealthProfile = ({ profile, onProfileChange, isOpen, onClose }) => {
  const [newDisease, setNewDisease] = useState('');
  const [newAllergy, setNewAllergy] = useState('');
  const [newMedication, setNewMedication] = useState('');

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleAddDisease = () => {
    if (newDisease.trim()) {
      onProfileChange({
        ...profile,
        chronic_diseases: [...(profile.chronic_diseases || []), newDisease.trim()],
      });
      setNewDisease('');
    }
  };

  const handleRemoveDisease = (index) => {
    const updated = [...profile.chronic_diseases];
    updated.splice(index, 1);
    onProfileChange({ ...profile, chronic_diseases: updated });
  };

  const handleAddAllergy = () => {
    if (newAllergy.trim()) {
      onProfileChange({
        ...profile,
        allergies: [...(profile.allergies || []), newAllergy.trim()],
      });
      setNewAllergy('');
    }
  };

  const handleRemoveAllergy = (index) => {
    const updated = [...profile.allergies];
    updated.splice(index, 1);
    onProfileChange({ ...profile, allergies: updated });
  };

  const handleAddMedication = () => {
    if (newMedication.trim()) {
      onProfileChange({
        ...profile,
        current_medications: [...(profile.current_medications || []), newMedication.trim()],
      });
      setNewMedication('');
    }
  };

  const handleRemoveMedication = (index) => {
    const updated = [...profile.current_medications];
    updated.splice(index, 1);
    onProfileChange({ ...profile, current_medications: updated });
  };

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-card fade-in">
        <div className="modal-header">
          <div className="modal-title-row">
            <User size={22} />
            <h2>Hồ sơ Sức khỏe</h2>
          </div>
          <button className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {/* Chronic Diseases */}
          <div className="profile-section">
            <div className="section-label">
              <Heart size={16} />
              <h4>Bệnh Mãn tính</h4>
            </div>
            <div className="tags">
              {profile.chronic_diseases?.map((disease, index) => (
                <div key={index} className="tag">
                  <span>{disease}</span>
                  <button onClick={() => handleRemoveDisease(index)}>
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
            <div className="add-input">
              <input
                type="text"
                value={newDisease}
                onChange={(e) => setNewDisease(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddDisease()}
                placeholder="VD: Đau dạ dày, Tiểu đường..."
              />
              <button onClick={handleAddDisease} disabled={!newDisease.trim()}>
                <Plus size={16} />
              </button>
            </div>
          </div>

          {/* Allergies */}
          <div className="profile-section">
            <div className="section-label">
              <AlertTriangle size={16} />
              <h4>Dị ứng</h4>
            </div>
            <div className="tags">
              {profile.allergies?.map((allergy, index) => (
                <div key={index} className="tag tag-warning">
                  <span>{allergy}</span>
                  <button onClick={() => handleRemoveAllergy(index)}>
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
            <div className="add-input">
              <input
                type="text"
                value={newAllergy}
                onChange={(e) => setNewAllergy(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddAllergy()}
                placeholder="VD: Aspirin, Penicillin..."
              />
              <button onClick={handleAddAllergy} disabled={!newAllergy.trim()}>
                <Plus size={16} />
              </button>
            </div>
          </div>

          {/* Current Medications */}
          <div className="profile-section">
            <div className="section-label">
              <Pill size={16} />
              <h4>Thuốc Đang Dùng</h4>
            </div>
            <div className="tags">
              {profile.current_medications?.map((medication, index) => (
                <div key={index} className="tag tag-info">
                  <span>{medication}</span>
                  <button onClick={() => handleRemoveMedication(index)}>
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
            <div className="add-input">
              <input
                type="text"
                value={newMedication}
                onChange={(e) => setNewMedication(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddMedication()}
                placeholder="VD: Metformin, Losartan..."
              />
              <button onClick={handleAddMedication} disabled={!newMedication.trim()}>
                <Plus size={16} />
              </button>
            </div>
          </div>

          {/* Age and Gender */}
          <div className="profile-section">
            <div className="section-label">
              <User size={16} />
              <h4>Thông tin Cá nhân</h4>
            </div>
            <div className="info-grid">
              <div className="info-field">
                <label>Tuổi</label>
                <input
                  type="number"
                  value={profile.age || ''}
                  onChange={(e) =>
                    onProfileChange({ ...profile, age: parseInt(e.target.value) || null })
                  }
                  placeholder="Nhập tuổi"
                  min="0"
                  max="120"
                />
              </div>
              <div className="info-field">
                <label>Giới tính</label>
                <select
                  value={profile.gender || ''}
                  onChange={(e) => onProfileChange({ ...profile, gender: e.target.value })}
                >
                  <option value="">Chọn</option>
                  <option value="Nam">Nam</option>
                  <option value="Nữ">Nữ</option>
                  <option value="Khác">Khác</option>
                </select>
              </div>
            </div>
          </div>

          <div className="profile-note">
            <p>
              💡 <strong>Lưu ý:</strong> Thông tin này giúp AI đưa ra lời khuyên an toàn và phù
              hợp hơn với tình trạng sức khỏe của bạn.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HealthProfile;
