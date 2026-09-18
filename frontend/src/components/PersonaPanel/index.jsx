import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { useStore } from '../../store';
import CustomSelect from '../CustomSelect';

export default function PersonaPanel() {
    const { alpha, setAlpha, personaPreset, setPersonaPreset, isNavigating } = useStore();
    const [isExpanded, setIsExpanded] = useState(false);
    const favourSignal = alpha < 0.5;

    const personas = [
        { id: 'default', label: 'Standard Car', targetAlpha: 0.65 },
        { id: 'suv', label: 'SUV', targetAlpha: 0.40 },
        { id: 'safe_commute', label: 'Safe Commute', targetAlpha: 0.15 }
    ];

    if (isNavigating) return null;

    if (!isExpanded) {
        return (
            <button
                type="button"
                onClick={() => setIsExpanded(true)}
                className="absolute top-6 left-0 z-10 bg-slate-950/85 backdrop-blur-2xl border border-white/15 border-l-0 rounded-r-3xl py-3 px-4 shadow-[0_15px_40px_rgba(0,0,0,0.6)] flex items-center gap-2 hover:bg-slate-900 transition-all group"
            >
                <span className="text-xs font-bold text-white">Route Prefs</span>
                <ChevronRight className="w-4 h-4 text-slate-500" />
            </button>
        );
    }

    return (
        <div className="absolute top-6 left-6 z-10 w-72 max-lg:w-56 bg-slate-950/85 backdrop-blur-2xl border border-white/15 rounded-3xl p-4 shadow-[0_15px_40px_rgba(0,0,0,0.6)] flex flex-col gap-4 transition-all">
            <div className="flex justify-between items-center">
                <div>
                    <h3 className="text-sm font-bold text-white">Route preference</h3>
                    <span className="text-[10px] text-slate-400">Choose what leads the decision</span>
                </div>
                {personaPreset === 'safe_commute' ? (
                    <span className="text-[9px] px-2 py-1 rounded-md font-bold tracking-wider border bg-amber-400/10 border-amber-400/25 text-amber-300">SAFEST</span>
                ) : personaPreset === 'suv' ? (
                    <span className="text-[9px] px-2 py-1 rounded-md font-bold tracking-wider border bg-amber-400/10 border-amber-400/25 text-amber-300">SUV ROUTE</span>
                ) : (
                    <span className={`text-[9px] px-2 py-1 rounded-md font-bold tracking-wider border ${favourSignal ? 'bg-emerald-400/10 border-emerald-400/25 text-emerald-300' : 'bg-sky-400/10 border-sky-400/25 text-sky-300'}`}>{favourSignal ? 'BEST SIGNAL' : 'FASTEST'}</span>
                )}
                <button
                    type="button"
                    onClick={() => setIsExpanded(false)}
                    className="ml-1 p-1.5 hover:bg-white/10 rounded-lg text-slate-400 hover:text-slate-200 transition-colors"
                    title="Collapse route preferences"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7"></path></svg>
                </button>
            </div>

            <div className="relative">
                <CustomSelect
                    value={personaPreset}
                    onChange={(value) => {
                        const p = personas.find(p => p.id === value);
                        if (p) {
                            setPersonaPreset(p.id);
                            setAlpha(p.targetAlpha);
                        }
                    }}
                    options={[
                        { value: 'custom', label: 'Custom' },
                        ...personas.map(p => ({ value: p.id, label: p.label })),
                    ]}
                />
            </div>

            <div className="pt-1">
                <div className="flex justify-between text-[10px] font-bold text-slate-300 mb-3">
                    {['safe_commute', 'suv'].includes(personaPreset) ? (
                        <span className="flex items-center gap-1.5"><span className="w-2 h-2 bg-amber-400 rounded-full"></span>{personaPreset === 'suv' ? 'SUV Route' : 'Safest'}</span>
                    ) : (
                        <span className="flex items-center gap-1.5"><span className="w-2 h-2 bg-emerald-400 rounded-full"></span>Best signal</span>
                    )}
                    <span className="flex items-center gap-1.5">Fastest<span className="w-2 h-2 bg-sky-400 rounded-full"></span></span>
                </div>

                <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={alpha}
                    disabled={['safe_commute', 'suv'].includes(personaPreset)}
                    onChange={(e) => {
                        setPersonaPreset('custom');
                        setAlpha(parseFloat(e.target.value));
                    }}
                    aria-label="Balance signal quality and travel time"
                    className={`w-full h-2 bg-white/20 rounded-lg appearance-none transition-all ${['safe_commute', 'suv'].includes(personaPreset) ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'} [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:shadow-[0_0_12px_rgba(255,255,255,0.6)]`}
                    style={{ background: `linear-gradient(90deg, ${['safe_commute', 'suv'].includes(personaPreset) ? '#fbbf24' : '#34d399'} 0%, ${['safe_commute', 'suv'].includes(personaPreset) ? '#fbbf24' : '#34d399'} ${alpha * 100}%, rgba(255,255,255,0.18) ${alpha * 100}%, rgba(255,255,255,0.18) 100%)` }}
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
