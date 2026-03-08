import { useState } from 'react';

interface UrlInputProps {
  value: string;
  onChange: (url: string) => void;
  disabled?: boolean;
}

export const UrlInput = ({ value, onChange, disabled = false }: UrlInputProps) => {
  const [touched, setTouched] = useState(false);

  const isValidUrl = value.trim() === '' || value.trim().startsWith('https://');
  const showError = touched && value.trim() !== '' && !isValidUrl;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
  };

  const handleBlur = () => {
    setTouched(true);
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const pastedText = e.clipboardData.getData('text').trim();
    if (pastedText && pastedText.startsWith('https://')) {
      e.preventDefault();
      onChange(pastedText);
      setTouched(true);
    }
  };

  return (
    <div>
      <label htmlFor="url-input" className="block text-sm font-medium text-gray-700 mb-2">
        学習したい Web ページの URL を入力してください
      </label>
      <input
        id="url-input"
        type="url"
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        onPaste={handlePaste}
        placeholder="https://example.com/article"
        className={`w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
          showError ? 'border-red-500' : 'border-gray-300'
        }`}
        disabled={disabled}
        data-testid="url-input"
      />
      {showError && (
        <p className="mt-1 text-sm text-red-500" data-testid="url-error">
          https:// で始まる URL を入力してください
        </p>
      )}
    </div>
  );
};
