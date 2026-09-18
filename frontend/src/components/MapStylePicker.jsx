import { useState } from 'react';
import { Map as MapIcon, Mountain, Satellite, X } from 'lucide-react';
import { useStore } from '../store';

export default function MapStylePicker() {
    const { mapStyle, setMapStyle } = useStore();
    const [isOpen, setIsOpen] = useState(false);

    const options = [
        { id: 'normal', label: 'Normal', icon: MapIcon },
        { id: 'hybrid', label: 'Hybrid', icon: Satellite },
        { id: 'terrain', label: 'Terrain', icon: Mountain },
    ];

    const handleStyleChange = (id) => {
        if (id === mapStyle) {
            setIsOpen(false);
            return;
        }

        setMapStyle(id);
        window.location.reload();
    };

    return (
        <div className="relative h-11">
            {!isOpen ? (
                <button
                    type="button"
                    onClick={() => setIsOpen(true)}
                    title="Map style"
                    className="h-11 w-11 bg-slate-950/85 backdrop-blur-xl hover:bg-slate-800 text-slate-200 rounded-xl shadow-[0_14px_40px_rgba(0,0,0,0.38)] border border-white/15 transition-all flex items-center justify-center"
                >
                    <MapIcon className="h-5 w-5" />
                </button>
            ) : (
                <div className="h-11 bg-slate-950/90 backdrop-blur-xl border border-white/15 rounded-2xl shadow-[0_14px_40px_rgba(0,0,0,0.38)] flex items-center gap-1 p-1">
                    {options.map(({ id, label, icon: Icon }) => (
                        <button
                            type="button"
                            key={id}
                            onClick={() => handleStyleChange(id)}
                            className={`h-9 px-3 rounded-xl flex items-center gap-2 transition-all ${
                                mapStyle === id
                                    ? 'bg-sky-500/20 text-sky-300 border border-sky-400/30'
                                    : 'text-slate-300 hover:bg-white/5 border border-transparent'
                            }`}
                        >
                            <Icon className="h-4 w-4" />
                            <span className="text-xs font-bold">{label}</span>
                        </button>
                    ))}
                    <button
                        type="button"
                        onClick={() => setIsOpen(false)}
                        className="h-9 w-9 rounded-xl flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/5"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>
            )}
        </div>
    );
}
