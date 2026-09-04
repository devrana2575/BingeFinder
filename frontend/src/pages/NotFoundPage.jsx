import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div className="text-center py-24">
      <h1 className="text-6xl font-bold text-text-muted mb-4">404</h1>
      <p className="text-text-secondary mb-6">This page doesn't exist.</p>
      <Link to="/" className="btn-primary">Back to Home</Link>
    </div>
  );
}
