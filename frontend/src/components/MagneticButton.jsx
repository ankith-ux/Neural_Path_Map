import { useRef, useState } from 'react';

export default function MagneticButton({ children, className = "", onClick, disabled = false, type = "button" }) {
    const ref = useRef(null);
    const [offset, setOffset] = useState({ x: 0, y: 0 });

    const handleMouseMove = (event) => {
        if (!ref.current || disabled) return;

        const rect = ref.current.getBoundingClientRect();
        const x = (event.clientX - (rect.left + rect.width / 2)) * 0.16;
        const y = (event.clientY - (rect.top + rect.height / 2)) * 0.16;
        setOffset({ x, y });
    };

    const reset = () => setOffset({ x: 0, y: 0 });

    return (
        <button
            ref={ref}
            type={type}
            disabled={disabled}
            onClick={onClick}
            onMouseMove={handleMouseMove}
            onMouseLeave={reset}
            className={`relative overflow-hidden transition-transform duration-200 disabled:transform-none ${className}`}
            style={{ transform: `translate3d(${offset.x}px, ${offset.y}px, 0)` }}
        >
            {children}
        </button>
    );
}
