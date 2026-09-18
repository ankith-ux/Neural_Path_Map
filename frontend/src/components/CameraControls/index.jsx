import { useState } from 'react';
import { Camera, ChevronRight, Map as MapIcon, Navigation } from 'lucide-react';
import { useStore } from '../../store';

export default function CameraControls() {
    const { cameraMode, setCameraMode, isNavigating } = useStore();
    const [isExpanded, setIsExpanded] = useState(false);

    if (!isNavigating) return null;

    if (!isExpanded) {
        return (
            <button
                type="button"
                onClick={() => setIsExpanded(true)}
                className="absolute bottom-6 left-0 z-20 bg-slate-950/85 backdrop-blur-2xl border border-white/15 border-l-0 rounded-r-3xl py-3 px-4 shadow-[0_15px_40px_rgba(0,0,0,0.6)] flex items-center gap-2 hover:bg-slate-900 transition-all group"
            >
                <span className="text-xs font-bold text-white">Camera</span>
                <Camera className="w-4 h-4 text-slate-300 group-hover:scale-110 transition-transform" />
                <ChevronRight className="w-4 h-4 text-slate-500" />
            </button>
        );
    }

    const modes = [
        { id: 'driver', label: 'Driver', icon: Navigation },
        { id: 'drone', label: 'Drone', icon: Camera },
        { id: 'top-down', label: 'Top-down', icon: MapIcon },
    ];

    return (
        <div className="absolute bottom-6 left-6 z-20 bg-slate-950/85 backdrop-blur-2xl border border-white/15 rounded-3xl p-2 shadow-[0_15px_40px_rgba(0,0,0,0.6)] flex items-center gap-1 transition-all">
            {modes.map(({ id, label, icon: Icon }) => {
                const isActive = cameraMode === id;
                return (
                    <button
                        type="button"
                        key={id}
                        onClick={() => setCameraMode(id)}
                        title={label}
                        className={`relative px-4 py-2 rounded-2xl flex items-center gap-2 transition-all ${
                            isActive
                                ? 'bg-sky-500 text-white shadow-[0_4px_15px_rgba(56,189,248,0.4)]'
                                : 'text-slate-400 hover:text-white hover:bg-white/5'
                        }`}
                    >
                        <Icon className="w-4 h-4" />
                        <span className="text-xs font-bold tracking-wide">{label}</span>
                    </button>
                );
            })}

            <div className="w-px h-6 bg-white/10 mx-1"></div>

            <button
                type="button"
                onClick={() => setIsExpanded(false)}
                className="p-2 hover:bg-white/10 rounded-2xl text-slate-400 hover:text-slate-200 transition-colors"
            >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7"></path></svg>
            </button>
        </div>
    );
}
