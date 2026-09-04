import { useState } from 'react';

export default function PosterImage({ src, title, className = '' }) {
  const [errored, setErrored] = useState(false);
  const showImage = src && !errored;

  if (showImage) {
    return (
      <img
        src={src}
        alt={title ? `${title} poster` : 'Series poster'}
        className={`w-full h-full object-cover ${className}`}
        loading="lazy"
        onError={() => setErrored(true)}
      />
    );
  }

  return (
    <div className={`w-full h-full flex items-center justify-center bg-surface-2 ${className}`}>
      <div className="text-center px-4">
        <div className="text-3xl mb-2 opacity-30">B</div>
        <p className="text-xs text-text-muted leading-tight">No poster available</p>
      </div>
    </div>
  );
}
