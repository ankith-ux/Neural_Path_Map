import { useState, useEffect } from 'react';
import { useStore } from '../../store';
import { BANGALORE_LOCATIONS } from '../../data/bangaloreLocations';

export default function RouteSearch() {
    const { isNavigating, setOriginCoords, setDestinationCoords } = useStore();
    const [origin, setOrigin] = useState("Kempegowda International Airport");
    const [destination, setDestination] = useState("Electronic City Phase 1");
    
    // Autocomplete State
    const [suggestions, setSuggestions] = useState([]);
    const [activeInput, setActiveInput] = useState(null);

    // Hides the bar smoothly when navigation starts
    const visibilityClass = isNavigating 
        ? 'opacity-0 -translate-y-10 pointer-events-none' 
        : 'opacity-100 translate-y-0';

    const handleSwap = () => {
        setOrigin(destination);
        setDestination(origin);
        
        const currentOriginCoords = useStore.getState().originCoords;
        const currentDestCoords = useStore.getState().destinationCoords;
        useStore.getState().setOriginCoords(currentDestCoords);
        useStore.getState().setDestinationCoords(currentOriginCoords);
    };

    // Instant Local Autocomplete Filtering (Zero Latency!)
    useEffect(() => {
        const query = activeInput === 'origin' ? origin : destination;
        
        if (!activeInput) {
            setSuggestions([]);
            return;
        }

        if (!query || query.length === 0) {
            setSuggestions(BANGALORE_LOCATIONS.slice(0, 10));
            return;
        }

        // Filter the dataset instantly based on what they type
        const filtered = BANGALORE_LOCATIONS.filter(loc => 
            loc.primary.toLowerCase().includes(query.toLowerCase()) || 
            loc.secondary.toLowerCase().includes(query.toLowerCase())
        );
        
        setSuggestions(filtered.slice(0, 10));
    }, [origin, destination, activeInput]);

    const handleSelect = (s) => {
        if (activeInput === 'origin') {
            setOrigin(s.primary);
            setOriginCoords([s.lon, s.lat]);
        } else {
            setDestination(s.primary);
            setDestinationCoords([s.lon, s.lat]);
        }
        setSuggestions([]);
        setActiveInput(null);
    };

    const renderDropdown = (type) => {
        if (activeInput !== type || suggestions.length === 0) return null;
        
        return (
            <div className="absolute top-[110%] left-0 w-full bg-[#0f172a] border border-white/10 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden z-[100]">
                {suggestions.map((s, i) => (
                    <div 
                        key={i} 
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
            </div>
        );
    };

    return (
        <div className={`absolute top-5 left-1/2 -translate-x-1/2 z-[100] flex max-w-[calc(100vw-2rem)] items-center gap-2 bg-slate-950/85 backdrop-blur-2xl border border-white/15 rounded-2xl p-2 shadow-[0_18px_55px_rgba(0,0,0,0.45)] transition-[opacity,transform] duration-700 ease-[cubic-bezier(0.23,1,0.32,1)] ${visibilityClass}`}>
            
            {/* Origin Input */}
            <div className="relative z-50">
                <div className={`bg-white/[0.06] rounded-xl px-3.5 py-2.5 flex flex-col w-[calc((100vw-7rem)/2)] max-w-64 min-w-0 border transition-colors ${activeInput === 'origin' ? 'border-sky-400/70 bg-sky-400/10' : 'border-transparent hover:border-white/15'}`}>
                    <span className="flex items-center gap-1.5 text-[9px] text-slate-400 uppercase tracking-widest font-bold mb-1 pointer-events-none"><span className="w-1.5 h-1.5 rounded-full bg-sky-400"></span>Origin</span>
                    <input 
                        type="text" 
                        value={origin}
                        onChange={(e) => setOrigin(e.target.value)}
                        onFocus={() => setActiveInput('origin')}
                        onBlur={() => setTimeout(() => setActiveInput(null), 200)}
                        className="min-w-0 bg-transparent text-white text-sm font-medium outline-none placeholder-slate-600"
                        placeholder="Where are you?"
                    />
                </div>
                {renderDropdown('origin')}
            </div>
            
            {/* Swap Button */}
            <button 
                onClick={handleSwap}
                title="Swap origin and destination"
                className="flex shrink-0 items-center justify-center bg-white/[0.07] hover:bg-sky-500/20 p-3 rounded-xl border border-white/10 hover:border-sky-400/40 shadow-lg cursor-pointer hover:scale-105 active:scale-95 z-50 transition-all"
            >
                <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path>
                </svg>
            </button>

            {/* Destination Input */}
            <div className="relative z-50">
                <div className={`bg-white/[0.06] rounded-xl px-3.5 py-2.5 flex flex-col w-[calc((100vw-7rem)/2)] max-w-64 min-w-0 border transition-colors ${activeInput === 'destination' ? 'border-emerald-400/70 bg-emerald-400/10' : 'border-transparent hover:border-white/15'}`}>
                    <span className="flex items-center gap-1.5 text-[9px] text-slate-400 uppercase tracking-widest font-bold mb-1 pointer-events-none"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>Destination</span>
                    <input 
                        type="text" 
                        value={destination}
                        onChange={(e) => setDestination(e.target.value)}
                        onFocus={() => setActiveInput('destination')}
                        onBlur={() => setTimeout(() => setActiveInput(null), 200)}
                        className="min-w-0 bg-transparent text-white text-sm font-medium outline-none placeholder-slate-600"
                        placeholder="Where to?"
                    />
                </div>
                {renderDropdown('destination')}
            </div>

        </div>
    );
}
