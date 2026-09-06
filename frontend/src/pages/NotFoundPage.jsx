import { Link } from 'react-router-dom';
import { t } from '../i18n';

export default function NotFoundPage() {
  return (
    <div className="text-center py-24">
      <h1 className="text-6xl font-bold text-text-muted mb-4">404</h1>
      <p className="text-text-secondary mb-6">{t('notFound.message')}</p>
      <Link to="/" className="btn-primary">{t('notFound.home')}</Link>
    </div>
  );
}