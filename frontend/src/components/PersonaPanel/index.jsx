import { useStore } from '../../store';

export default function PersonaPanel() {
    const { alpha, setAlpha, personaPreset, setPersonaPreset } = useStore();
    const favourSignal = alpha < 0.5;

    const personas = [
        { id: 'it_shuttle', label: '🚌 IT Shuttle', targetAlpha: 0.3 },
        { id: 'default', label: '🚗 Standard Car', targetAlpha: 0.65 },
        { id: 'ride_hailing', label: '🚕 Ride Hailing', targetAlpha: 0.8 },
        { id: 'emergency', label: '🚑 Ambulance', targetAlpha: 0.95 }
    ];

    return (
        <div className="absolute bottom-6 left-6 z-10 w-72 max-lg:w-52 bg-slate-950/85 backdrop-blur-2xl border border-white/15 rounded-2xl p-4 shadow-[0_18px_50px_rgba(0,0,0,0.42)] flex flex-col gap-4">
            <div className="flex justify-between items-center">
                <div>
                    <h3 className="text-sm font-bold text-white">Route preference</h3>
                    <span className="text-[10px] text-slate-400">Choose what leads the decision</span>
                </div>
                <span className={`text-[9px] px-2 py-1 rounded-md font-bold tracking-wider border ${favourSignal ? 'bg-emerald-400/10 border-emerald-400/25 text-emerald-300' : 'bg-sky-400/10 border-sky-400/25 text-sky-300'}`}>{favourSignal ? 'BEST SIGNAL' : 'FASTEST'}</span>
            </div>

            <div className="relative">
                <select
                    value={personaPreset}
                    onChange={(e) => {
                        const p = personas.find(p => p.id === e.target.value);
                        if (p) {
                            setPersonaPreset(p.id);
                            setAlpha(p.targetAlpha);
                        }
                    }}
                    className="w-full appearance-none bg-white/[0.06] border border-white/10 hover:border-white/20 hover:bg-white/10 transition-all text-white text-sm font-bold py-3 px-3.5 rounded-xl cursor-pointer outline-none"
                >
                    <option value="custom" className="bg-slate-900 text-white py-2">
                        🎛️ Custom
                    </option>
                    {personas.map(p => (
                        <option key={p.id} value={p.id} className="bg-slate-900 text-white py-2">
                            {p.label}
                        </option>
                    ))}
                </select>
                <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                </div>
            </div>

            <div className="pt-1">
                <div className="flex justify-between text-[10px] font-bold text-slate-300 mb-3">
                    <span className="flex items-center gap-1.5"><span className="w-2 h-2 bg-emerald-400 rounded-full"></span>Best signal</span>
                    <span className="flex items-center gap-1.5">Fastest<span className="w-2 h-2 bg-sky-400 rounded-full"></span></span>
                </div>

                <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={alpha}
                    onChange={(e) => {
                        setPersonaPreset('custom');
                        setAlpha(parseFloat(e.target.value));
                    }}
                    aria-label="Balance signal quality and travel time"
                    className="w-full h-2 bg-white/20 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:shadow-[0_0_12px_rgba(255,255,255,0.6)] transition-all"
                    style={{ background: `linear-gradient(90deg, #34d399 0%, #34d399 ${alpha * 100}%, rgba(255,255,255,0.18) ${alpha * 100}%, rgba(255,255,255,0.18) 100%)` }}
                />

                <div className="mt-3 flex justify-between text-[9px] uppercase tracking-widest font-bold text-slate-500">
                    <span>Resilience</span>
                    <span className="font-mono text-slate-300">{Math.round(alpha * 100)}% time</span>
                    <span>Arrival</span>
                </div>
            </div>
        </div>
    );
}
