import { useEffect, useRef, useState } from 'react';

export default function CustomSelect({ value, onChange, options, className = "", label = null }) {
    const [isOpen, setIsOpen] = useState(false);
    const ref = useRef(null);
    const selectedOption = options.find((option) => option.value === value) || options[0];

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (ref.current && !ref.current.contains(event.target)) {
                setIsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    return (
        <div className={`relative w-full text-left ${className}`} ref={ref}>
            <button
                type="button"
                onClick={() => setIsOpen((open) => !open)}
                className="w-full flex items-center justify-between bg-white/[0.06] border border-white/10 hover:border-white/20 hover:bg-white/10 transition-all text-white text-xs font-bold py-2.5 px-3 rounded-xl outline-none shadow-sm"
            >
                <span className="flex min-w-0 flex-col items-start gap-0.5 text-left">
                    {label && <span className="block text-[8px] text-slate-500 uppercase tracking-widest font-bold">{label}</span>}
                    <span className="truncate">{selectedOption?.label}</span>
                </span>
                <svg className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M19 9l-7 7-7-7"></path></svg>
            </button>

            {isOpen && (
                <div className="absolute z-50 w-full mt-2 bg-[#0f172a]/95 backdrop-blur-3xl border border-white/15 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.7)] overflow-hidden animate-[fadeIn_120ms_ease-out]">
                    <div className="max-h-60 overflow-y-auto p-1.5 flex flex-col gap-0.5 custom-scrollbar">
                        {options.map((option) => (
                            <button
                                type="button"
                                key={option.value}
                                onClick={() => {
                                    onChange(option.value);
                                    setIsOpen(false);
                                }}
                                className={`w-full text-left px-3 py-2 text-xs font-bold rounded-lg transition-all truncate ${
                                    value === option.value
                                        ? 'bg-sky-500/20 text-sky-300'
                                        : 'text-slate-300 hover:bg-white/5'
                                }`}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
