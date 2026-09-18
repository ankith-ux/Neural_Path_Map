import { useEffect, useRef, useState } from 'react';
import { useStore } from '../../store';
import { BANGALORE_LOCATIONS } from '../../data/bangaloreLocations';

export default function RouteSearch() {
    const {
        isNavigating,
        originCoords,
        destinationCoords,
        setOriginCoords,
        setDestinationCoords,
        originText,
        setOriginText,
        destinationText,
        setDestinationText,
        setMapSelectionMode,
    } = useStore();
    
    const [suggestions, setSuggestions] = useState([]);
    const [activeInput, setActiveInput] = useState(null);
    const blurTimeoutRef = useRef(null);
    const isLandingState = !originCoords || !destinationCoords;

    const handleSwap = () => {
        setOriginText(destinationText);
        setDestinationText(originText);
        
        const currentOriginCoords = useStore.getState().originCoords;
        const currentDestCoords = useStore.getState().destinationCoords;
        useStore.getState().setOriginCoords(currentDestCoords);
        useStore.getState().setDestinationCoords(currentOriginCoords);
    };

    useEffect(() => {
        const query = activeInput === 'origin' ? originText : destinationText;
        
        if (!activeInput) {
            setSuggestions([]);
            return;
        }

        if (!query || query.length < 2) {
            setSuggestions(BANGALORE_LOCATIONS.slice(0, 8));
            return;
        }

        const filtered = BANGALORE_LOCATIONS.filter(loc => 
            loc.primary.toLowerCase().includes(query.toLowerCase()) || 
            loc.secondary.toLowerCase().includes(query.toLowerCase())
        );
        
        setSuggestions(filtered.slice(0, 8));
    }, [originText, destinationText, activeInput]);

    const handleSelect = (s) => {
        if (activeInput === 'origin') {
            setOriginText(s.primary);
            setOriginCoords([s.lon, s.lat]);
        } else {
            setDestinationText(s.primary);
            setDestinationCoords([s.lon, s.lat]);
        }
        setSuggestions([]);
        setActiveInput(null);
        setMapSelectionMode(null);
    };

    const renderDropdown = (type) => {
        if (activeInput !== type) return null;
        
        return (
            <div className="absolute top-[110%] left-0 w-full bg-[#0f172a]/95 backdrop-blur-3xl border border-white/10 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.6)] overflow-hidden z-[100] max-h-[50vh] flex flex-col">
                <div className="px-4 py-2.5 bg-slate-900/80 border-b border-white/5 flex items-center gap-2 shrink-0">
                    <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122"></path></svg>
                    <span className="text-xs text-slate-500 font-medium tracking-wide">Or click anywhere on the map to set</span>
                </div>
                <div className="overflow-y-auto custom-scrollbar">
                    {suggestions.map((s, i) => (
                        <div 
                            key={`${s.primary}-${i}`} 
                            className="px-4 py-3 hover:bg-white/10 cursor-pointer border-b border-white/5 last:border-0 truncate transition-all"
                            onMouseDown={(e) => {
                                e.preventDefault(); 
                                handleSelect(s);
                            }}
                        >
                            <span className="text-white font-medium block">{s.primary}</span>
                            <span className="text-slate-500 text-xs mt-0.5 block truncate">{s.secondary}</span>
                        </div>
                    ))}
                    {suggestions.length === 0 && (
                        <div className="px-4 py-3 text-sm text-slate-500">No local matches. Click the map to place this point.</div>
                    )}
                </div>
            </div>
        );
    };

    return (
        <div className={`absolute left-1/2 -translate-x-1/2 z-[100] flex max-w-[calc(100vw-2rem)] items-center gap-4 bg-slate-950/85 backdrop-blur-2xl border border-white/15 rounded-[2rem] p-3 transition-all duration-1000 ease-[cubic-bezier(0.23,1,0.32,1)] ${
            isNavigating
                ? 'opacity-0 -translate-y-10 pointer-events-none top-5 shadow-[0_18px_55px_rgba(0,0,0,0.65)]'
                : isLandingState
                    ? 'opacity-100 top-1/2 -translate-y-1/2 scale-110 shadow-[0_0_150px_60px_rgba(0,0,0,0.8)]'
                    : 'opacity-100 top-5 translate-y-0 scale-100 shadow-[0_18px_55px_rgba(0,0,0,0.65)]'
        }`}>
            
            {/* Origin Input */}
            <div className="relative z-50">
                <div className={`px-5 py-2.5 flex flex-col w-[calc((100vw-7rem)/2)] max-w-80 min-w-0 transition-opacity ${activeInput && activeInput !== 'origin' ? 'opacity-50' : 'opacity-100'}`}>
                    <span className="text-[10px] text-sky-400 drop-shadow-[0_0_8px_rgba(56,189,248,0.6)] uppercase tracking-widest font-extrabold mb-1.5 pointer-events-none">Origin</span>
                    <input 
                        type="text" 
                        value={originText}
                        onChange={(e) => setOriginText(e.target.value)}
                        onFocus={() => {
                            if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
                            setActiveInput('origin');
                            setMapSelectionMode('origin');
                        }}
                        onBlur={() => {
                            blurTimeoutRef.current = setTimeout(() => {
                                setActiveInput(null);
                                setMapSelectionMode(null);
                            }, 200);
                        }}
                        className="min-w-0 bg-transparent text-white text-lg font-bold outline-none placeholder-slate-600/80"
                        placeholder="Where are you?"
                    />
                </div>
                {renderDropdown('origin')}
            </div>
            
            {/* Swap Button */}
            <button 
                onClick={handleSwap}
                title="Swap origin and destination"
                className="flex shrink-0 items-center justify-center p-3 text-slate-400 hover:text-white cursor-pointer hover:scale-110 active:scale-95 z-50 transition-all"
            >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path>
                </svg>
            </button>

            {/* Destination Input */}
            <div className="relative z-50">
                <div className={`px-5 py-2.5 flex flex-col w-[calc((100vw-7rem)/2)] max-w-80 min-w-0 transition-opacity ${activeInput && activeInput !== 'destination' ? 'opacity-50' : 'opacity-100'}`}>
                    <span className="text-[10px] text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.6)] uppercase tracking-widest font-extrabold mb-1.5 pointer-events-none">Destination</span>
                    <input 
                        type="text" 
                        value={destinationText}
                        onChange={(e) => setDestinationText(e.target.value)}
                        onFocus={() => {
                            if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
                            setActiveInput('destination');
                            setMapSelectionMode('destination');
                        }}
                        onBlur={() => {
                            blurTimeoutRef.current = setTimeout(() => {
                                setActiveInput(null);
                                setMapSelectionMode(null);
                            }, 200);
                        }}
                        className="min-w-0 bg-transparent text-white text-lg font-bold outline-none placeholder-slate-600/80"
                        placeholder="Where to?"
                    />
                </div>
                {renderDropdown('destination')}
            </div>

        </div>
    );
}
