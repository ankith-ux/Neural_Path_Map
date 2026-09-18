import { useState } from 'react';
import { ChevronLeft, Signal } from 'lucide-react';
import { useStore } from '../../store';
import {
    getSelectedRouteMetrics,
} from '../../utils/routeBlend';
import CustomSelect from '../CustomSelect';

const WEATHER_OPTIONS = [
    { value: 'live', label: 'Live Weather' },
    { value: 'clear', label: 'Clear' },
    { value: 'cloudy', label: 'Cloudy' },
    { value: 'light_rain', label: 'Light Rain' },
    { value: 'heavy_rain', label: 'Heavy Rain' },
    { value: 'thunderstorm', label: 'Thunderstorm' },
];

function formatWeatherLabel(value = 'clear') {
    return value
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function TelemetryHUD() {
    const [isExpanded, setIsExpanded] = useState(false);
    const {
        alpha,
        carrier,
        setCarrier,
        dynamicRouteData,
        weatherScenario,
        setWeatherScenario,
        weatherConditions,
        isNavigating,
    } = useStore();
    const selectedMetrics = getSelectedRouteMetrics(dynamicRouteData, alpha);
    const isDanger = selectedMetrics.deadZoneCount > 0;
    const dropDurationSeconds = selectedMetrics.dropDurationSeconds;
    const weatherLabel = formatWeatherLabel(weatherConditions?.condition || weatherScenario);
    const weatherSourceLabel = weatherConditions?.source === 'simulation'
        ? 'Simulated'
        : weatherConditions?.source === 'fallback'
            ? 'Fallback'
            : 'Live';
    const weatherAdjusted = Boolean(
        weatherConditions && !['clear', 'cloudy'].includes(weatherConditions.condition)
    );

    if (isNavigating) return null;

    if (!isExpanded) {
        return (
            <button
                type="button"
                onClick={() => setIsExpanded(true)}
                className="absolute top-6 right-0 z-10 bg-slate-950/85 backdrop-blur-2xl border border-white/15 border-r-0 rounded-l-3xl py-3 px-4 shadow-[0_15px_40px_rgba(0,0,0,0.6)] flex items-center gap-2 hover:bg-slate-900 transition-all group"
            >
                <ChevronLeft className="w-4 h-4 text-slate-500" />
                <span className="text-xs font-bold text-white">Conditions</span>
                <Signal className="w-4 h-4 text-slate-300 group-hover:scale-110 transition-transform" />
            </button>
        );
    }

    return (
        <div className="absolute top-6 right-6 z-10 w-72 max-lg:w-56 bg-slate-950/85 backdrop-blur-2xl border border-white/15 rounded-3xl p-4 shadow-[0_15px_40px_rgba(0,0,0,0.6)] flex flex-col gap-3">
            
            {/* Header */}
            <div className="flex justify-between items-center">
                <span className="text-[10px] font-bold text-slate-300 uppercase tracking-widest">Network conditions</span>
                <div className="flex items-center gap-2">
                    <span className={`flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest px-2 py-1 rounded-full ${
                        isDanger ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${isDanger ? 'bg-red-500 animate-pulse' : 'bg-emerald-500'}`}></span>
                        {isDanger ? 'Warning' : 'Secure'}
                    </span>
                    <button
                        type="button"
                        onClick={() => setIsExpanded(false)}
                        className="p-1 hover:bg-white/10 rounded-lg text-slate-400 hover:text-slate-200 transition-colors"
                        title="Collapse conditions"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path></svg>
                    </button>
                </div>
            </div>

            {/* Status Message */}
            <div className="flex flex-col gap-0.5 border-t border-white/10 pt-3">
                <h3 className={`text-lg font-semibold ${isDanger ? 'text-white' : 'text-slate-100'}`}>
                    {isDanger ? 'Drop Predicted' : '5G Continuous'}
                </h3>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                    {isDanger 
                        ? 'Vehicle intersects high-probability dead zone. Media buffers likely.' 
                        : 'Route optimized to maintain continuous high-bandwidth connectivity.'}
                </p>
            </div>

            <div className={`rounded-xl p-3 border ${weatherAdjusted ? 'bg-sky-500/10 border-sky-400/20' : 'bg-white/[0.05] border-white/10'}`}>
                <div className="flex justify-between items-center">
                    <span className="text-[8px] text-slate-500 uppercase tracking-widest font-bold">Weather</span>
                    <span className="text-[9px] font-bold uppercase tracking-widest text-slate-400">{weatherSourceLabel}</span>
                </div>
                <div className="flex items-end justify-between gap-3 mt-2">
                    <span className={`text-sm font-bold ${weatherAdjusted ? 'text-sky-300' : 'text-slate-200'}`}>
                        {weatherLabel}
                    </span>
                    <span className="text-[10px] text-slate-500 font-medium">Signal impact</span>
                </div>
                {weatherAdjusted && <p className="text-[10px] text-slate-400 mt-2 leading-relaxed">Signal and bandwidth are adjusted for this weather.</p>}
            </div>

            {/* Stats & Carrier Grid */}
            <div className="grid grid-cols-2 gap-2 mt-1">
                <div className="bg-white/[0.05] rounded-xl p-2.5 border border-white/10">
                    <span className="block text-[8px] text-slate-500 uppercase tracking-widest mb-1 font-bold">Drop Duration</span>
                    <span className={`font-mono text-base ${isDanger ? 'text-red-400' : 'text-slate-300'}`}>
                        {isDanger ? `${Math.round(dropDurationSeconds)} sec` : '0 sec'}
                    </span>
                </div>
                
                <CustomSelect
                    label="Network Profile"
                    value={carrier}
                    onChange={setCarrier}
                    options={[
                        { value: 'composite', label: 'All Networks' },
                        { value: 'jio', label: 'Jio 5G' },
                        { value: 'airtel', label: 'Airtel 5G' },
                        { value: 'vi', label: 'Vi' },
                        { value: 'bsnl', label: 'BSNL' },
                    ]}
                />
            </div>

            <CustomSelect
                label="Weather Scenario"
                value={weatherScenario}
                onChange={setWeatherScenario}
                options={WEATHER_OPTIONS}
            />

        </div>
    );
}
