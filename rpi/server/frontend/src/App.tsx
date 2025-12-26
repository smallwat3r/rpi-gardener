import { useEffect, useRef, useState } from 'preact/hooks';
import { AdminSettings } from '@/components/AdminSettings';
import { Dashboard } from '@/components/Dashboard';
import { Modal } from '@/components/Modal';
import './styles/global.css';

export function App() {
  const [showAdmin, setShowAdmin] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [thresholdVersion, setThresholdVersion] = useState(0);
  const successTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (successTimerRef.current !== null) {
        clearTimeout(successTimerRef.current);
      }
    };
  }, []);

  const handleOpenAdmin = () => setShowAdmin(true);
  const handleCloseAdmin = () => setShowAdmin(false);

  const handleSaveAdmin = () => {
    setShowAdmin(false);
    setSuccessMessage('Settings saved successfully!');
    setThresholdVersion((v) => v + 1);
    if (successTimerRef.current !== null) {
      clearTimeout(successTimerRef.current);
    }
    successTimerRef.current = window.setTimeout(() => {
      setSuccessMessage(null);
    }, 3000);
  };

  return (
    <>
      <Dashboard onSettingsClick={handleOpenAdmin} thresholdVersion={thresholdVersion} />
      {successMessage && <div class="toast-success">{successMessage}</div>}
      <Modal isOpen={showAdmin} onClose={handleCloseAdmin} title="Settings">
        <AdminSettings onClose={handleCloseAdmin} onSave={handleSaveAdmin} />
      </Modal>
    </>
  );
}
