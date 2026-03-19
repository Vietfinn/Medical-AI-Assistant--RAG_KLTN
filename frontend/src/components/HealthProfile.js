import React, { useState } from 'react';
import { User, Plus, X, Save } from 'lucide-react';
import './HealthProfile.css';

const HealthProfile = ({ profile, onProfileChange }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [newDisease, setNewDisease] = useState('');
  const [newAllergy, setNewAllergy] = useState('');
  const [newMedication, setNewMedication] = useState('');

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

  return (
    <div className="health-profile">
      <div className="profile-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="profile-title">
          <User size={20} />
          <h3>Hồ sơ Sức khỏe</h3>
        </div>
        <button className="expand-btn">
          {isExpanded ? '−' : '+'}
        </button>
      </div>

      {isExpanded && (
        <div className="profile-content fade-in">
          {/* Chronic Diseases */}
          <div className="profile-section">
            <h4>🏥 Bệnh Mãn tính</h4>
            <div className="tags">
              {profile.chronic_diseases?.map((disease, index) => (
                <div key={index} className="tag">
                  <span>{disease}</span>
                  <button onClick={() => handleRemoveDisease(index)}>
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
            <div className="add-input">
              <input
                type="text"
                value={newDisease}
                onChange={(e) => setNewDisease(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddDisease()}
                placeholder="Nhập bệnh (VD: Đau dạ dày, Tiểu đường...)"
              />
              <button onClick={handleAddDisease}>
                <Plus size={16} />
              </button>
            </div>
          </div>

          {/* Allergies */}
          <div className="profile-section">
            <h4>⚠️ Dị ứng</h4>
            <div className="tags">
              {profile.allergies?.map((allergy, index) => (
                <div key={index} className="tag tag-warning">
                  <span>{allergy}</span>
                  <button onClick={() => handleRemoveAllergy(index)}>
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
            <div className="add-input">
              <input
                type="text"
                value={newAllergy}
                onChange={(e) => setNewAllergy(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddAllergy()}
                placeholder="Nhập dị ứng (VD: Aspirin, Penicillin...)"
              />
              <button onClick={handleAddAllergy}>
                <Plus size={16} />
              </button>
            </div>
          </div>

          {/* Current Medications */}
          <div className="profile-section">
            <h4>💊 Thuốc Đang Dùng</h4>
            <div className="tags">
              {profile.current_medications?.map((medication, index) => (
                <div key={index} className="tag tag-info">
                  <span>{medication}</span>
                  <button onClick={() => handleRemoveMedication(index)}>
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
            <div className="add-input">
              <input
                type="text"
                value={newMedication}
                onChange={(e) => setNewMedication(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddMedication()}
                placeholder="Nhập tên thuốc (VD: Metformin...)"
              />
              <button onClick={handleAddMedication}>
                <Plus size={16} />
              </button>
            </div>
          </div>

          {/* Age and Gender */}
          <div className="profile-section">
            <h4>👤 Thông tin Cá nhân</h4>
            <div className="info-grid">
              <div className="info-field">
                <label>Tuổi:</label>
                <input
                  type="number"
                  value={profile.age || ''}
                  onChange={(e) => onProfileChange({ ...profile, age: parseInt(e.target.value) || null })}
                  placeholder="Nhập tuổi"
                  min="0"
                  max="120"
                />
              </div>
              <div className="info-field">
                <label>Giới tính:</label>
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
            <p>💡 <strong>Lưu ý:</strong> Thông tin hồ sơ giúp hệ thống đưa ra lời khuyên an toàn và phù hợp hơn với tình trạng sức khỏe của bạn.</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default HealthProfile;
