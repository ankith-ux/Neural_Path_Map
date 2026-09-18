import { create } from 'zustand'

export const useStore = create((set) => ({
    carrier: 'composite',
    simulationHoursAhead: 0,
    weatherScenario: 'live',
    heatTiles: [],
    origin: null,
    destination: null,
    routes: [],
    selectedRouteIdx: 0,
    alpha: 0.65,
    persona: 'default',
    personaPreset: 'default',
    setCarrier: (carrier) => set({ carrier }),
    setSimulationHoursAhead: (simulationHoursAhead) => set({ simulationHoursAhead }),
    setWeatherScenario: (weatherScenario) => set({ weatherScenario }),
    setAlpha: (alpha) => set({ alpha }),
    setPersonaPreset: (personaPreset) => set({
        personaPreset,
        persona: personaPreset === 'custom' ? 'default' : personaPreset,
    }),
    isNavigating: false,
    currentNavSignal: null,
    setCurrentNavSignal: (currentNavSignal) => set({ currentNavSignal }),
    setIsNavigating: (val) => set({ isNavigating: val, navProgress: 0, currentNavSignal: null }),
    navProgress: 0,
    setNavProgress: (val) => set({ navProgress: val }),
    originCoords: [77.7081, 13.1989], // default start
    destinationCoords: [77.665, 12.846], // default end
    setOriginCoords: (coords) => set({ originCoords: coords }),
    setDestinationCoords: (coords) => set({ destinationCoords: coords }),
    dynamicRouteData: null,
    setDynamicRouteData: (data) => set({ dynamicRouteData: data }),
    weatherConditions: null,
    setWeatherConditions: (weatherConditions) => set({ weatherConditions }),
    
    // BACKEND INTEGRATION STATES
    routeCacheKey: null,
    setRouteCacheKey: (key) => set({ routeCacheKey: key })
}))
