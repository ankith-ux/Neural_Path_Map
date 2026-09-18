import { useEffect, useRef, useState } from 'react';

export default function AnimatedNumber({ value, format = Math.round, className = "" }) {
    const [displayValue, setDisplayValue] = useState(value);
    const frameRef = useRef(null);
    const previousRef = useRef(value);

    useEffect(() => {
        const from = Number(previousRef.current) || 0;
        const to = Number(value) || 0;
        const started = performance.now();
        const duration = 450;

        if (frameRef.current) cancelAnimationFrame(frameRef.current);

        const tick = (now) => {
            const progress = Math.min((now - started) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setDisplayValue(from + (to - from) * eased);

            if (progress < 1) {
                frameRef.current = requestAnimationFrame(tick);
            } else {
                previousRef.current = to;
            }
        };

        frameRef.current = requestAnimationFrame(tick);
        return () => {
            if (frameRef.current) cancelAnimationFrame(frameRef.current);
        };
    }, [value]);

    return <span className={className}>{format(displayValue)}</span>;
}
