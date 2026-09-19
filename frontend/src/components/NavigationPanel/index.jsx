import { useState, useEffect } from 'react';
import { useStore } from '../../store';
import {
    getPreferredRouteIndex,
    getSelectedRouteMetrics,
    getSignalQualityLabel,
} from '../../utils/routeBlend';
import AnimatedNumber from '../AnimatedNumber';
import MagneticButton from '../MagneticButton';

const HOUR_MS = 60 * 60 * 1000;

function getProfileColor(score = 0) {
    if (score >= 85) return '#3b82f6';
    if (score >= 65) return '#22c55e';
    if (score >= 40) return '#facc15';
    if (score >= 25) return '#f97316';
    return '#ef4444';
}

function SignalProfileBar({ profile = [] }) {
    const segments = Array.isArray(profile)
        ? profile.filter((point) => Number(point.progress_end ?? 0) > Number(point.progress_start ?? 0))
        : [];

    if (segments.length === 0) {
        return null;
    }

    return (
        <div className="bg-black/45 rounded-xl p-3 border border-white/10">
            <div className="flex items-center justify-between mb-2">
                <span className="text-[9px] text-slate-400 uppercase tracking-widest font-bold">
                    Signal along this route
                </span>
                <div className="flex items-center gap-2 text-[9px] font-semibold text-slate-500">
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#3b82f6]"></span>Strong</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#facc15]"></span>Fair</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#ef4444]"></span>Dead</span>
                </div>
            </div>
            <div className="relative w-full h-4 overflow-hidden rounded-md bg-slate-900/80 ring-1 ring-white/10">
                {segments.map((point, index) => {
                    const widthPct = Math.max(
                        0.8,
                        (Number(point.progress_end) - Number(point.progress_start)) * 100,
                    );
                    const leftPct = Number(point.progress_start) * 100;
                    const score = Math.round(Number(point.score ?? 0));
                    const bandwidth = Number(point.expected_bandwidth_mbps ?? 0);
                    const band = point.dominant_band || 'LTE_900';

                    return (
                        <div
                            key={`${point.progress_start}-${point.progress_end}-${index}`}
                            title={`${score}/100 signal, ${band}, ${bandwidth.toFixed(1)} Mbps`}
                            className="absolute top-0 h-full border-r border-black/20"
                            style={{
                                left: `${leftPct}%`,
                                width: `${widthPct}%`,
                                backgroundColor: getProfileColor(score),
                            }}
                        />
                    );
                })}
            </div>
            <div className="flex justify-between mt-1.5 text-[8px] text-slate-500 font-bold uppercase tracking-widest">
                <span>Start</span>
                <span>Route signal evidence</span>
                <span>End</span>
            </div>
        </div>
    );
}

function RouteChoice({ route, index, selected }) {
    if (!route) return null;

    const metrics = getSelectedRouteMetrics([route], 0);
    const persona = useStore.getState().personaPreset;
    const isSignalRoute = index === 0;
    const tone = isSignalRoute
        ? 'border-emerald-400/40 bg-emerald-400/10'
        : 'border-sky-400/40 bg-sky-400/10';
    const textTone = isSignalRoute ? 'text-emerald-300' : 'text-sky-300';
    const metricLabel = persona === 'safe_commute'
        ? `Safety ${Math.round(metrics.safetyScore || 50)}`
        : persona === 'suv'
            ? `SUV ${Math.round(metrics.suvScore || 0)}`
            : persona === 'ev'
                ? `Signal ${Math.round(metrics.connectivityScore)}`
                : `Signal ${Math.round(metrics.connectivityScore)}`;

    return (
        <div className={`min-w-0 rounded-xl border px-3 py-2.5 transition-all ${selected ? `${tone} shadow-[0_8px_22px_rgba(0,0,0,0.18)]` : 'border-white/10 bg-white/[0.035] opacity-70'}`}>
            <div className="flex items-center justify-between gap-2">
                <span className={`text-[10px] font-bold ${selected ? textTone : 'text-slate-300'}`}>{metrics.routeLabel}</span>
                {selected && <span className="text-[8px] font-bold uppercase tracking-wider text-white/80">Selected</span>}
            </div>
            <div className="flex items-baseline gap-2 mt-1">
                <span className="text-base font-bold text-white">{Math.max(1, Math.round(metrics.durationSecs / 60))} min</span>
                <span className="text-[10px] text-slate-400">
                    {metricLabel}
                </span>
            </div>
        </div>
    );
}

export default function NavigationPanel() {
    const {
        alpha,
        personaPreset,
        isNavigating,
        setIsNavigating,
        navProgress,
        dynamicRouteData,
        simulationHoursAhead,
        currentNavSignal,
        isEvMode,
        evRouteOptions,
        evChargers,
        evHeatmapMeta,
    } = useStore();
    const [navDetailsOpen, setNavDetailsOpen] = useState(false);
    const [currentTime, setCurrentTime] = useState(
        () => new Date(Date.now() + simulationHoursAhead * HOUR_MS)
    );

    useEffect(() => {
        if (isNavigating) {
            setNavDetailsOpen(false);
        }
    }, [isNavigating]);

    // Keep the ETA fresh while navigation progress is animating, using the simulated clock.
    useEffect(() => {
        const updateCurrentTime = () => {
            setCurrentTime(new Date(Date.now() + simulationHoursAhead * HOUR_MS));
        };

        updateCurrentTime();
        const timer = setInterval(updateCurrentTime, isNavigating ? 1000 : 60000);
        return () => clearInterval(timer);
    }, [isNavigating, simulationHoursAhead]);

    // Use dynamic OSRM data if available, otherwise fallback to mock values
    const hasRouteData = dynamicRouteData && dynamicRouteData.length > 0;
    const routeUnavailable = Array.isArray(dynamicRouteData) && dynamicRouteData.length === 0;
    const preferredRouteIndex = getPreferredRouteIndex(dynamicRouteData, alpha);
    const preferRouteA = preferredRouteIndex === 0;
    const routeChoices = hasRouteData ? dynamicRouteData.slice(0, 2) : [];
    let totalEtaMins = 28;
    let totalEtaSeconds = totalEtaMins * 60;
    let totalDistanceKm = 12.4;

    // Backend Intelligence Metrics
    let connectivityScore = 95;
    let safetyScore = 50;
    let safetyHardBlockCount = 0;
    let suvScore = 0;
    let suvHardBlockCount = 0;
    let deadZoneCount = 0;
    let dominantBand = "5G_NR";
    let trafficDelaySeconds = 0;
    let routeLabel = "Route";
    let signalProfile = [];
    let activeConditions = [];
    let safetyExplanation = "";

    if (dynamicRouteData && dynamicRouteData.length > 0) {
        const selectedMetrics = getSelectedRouteMetrics(dynamicRouteData, alpha);

        totalDistanceKm = Number((selectedMetrics.distanceMeters / 1000).toFixed(1));
        totalEtaSeconds = Math.max(60, selectedMetrics.durationSecs);
        totalEtaMins = Math.max(1, Math.round(totalEtaSeconds / 60));
        connectivityScore = Math.round(selectedMetrics.connectivityScore);
        safetyScore = Math.round(selectedMetrics.safetyScore || 50);
        safetyHardBlockCount = selectedMetrics.safetyHardBlockCount || 0;
        suvScore = Math.round(selectedMetrics.suvScore || 0);
        suvHardBlockCount = selectedMetrics.suvHardBlockCount || 0;
        deadZoneCount = selectedMetrics.deadZoneCount;
        dominantBand = selectedMetrics.dominantBand || "5G_NR";
        trafficDelaySeconds = selectedMetrics.trafficDelaySeconds || 0;
        routeLabel = selectedMetrics.routeLabel || "Route";
        signalProfile = selectedMetrics.signalProfile || [];
        activeConditions = selectedMetrics.activeConditions || [];
        safetyExplanation = selectedMetrics.safetyExplanation || "";
    }

    const primaryCondition = activeConditions[0] || null;
    const trafficDelayMins = trafficDelaySeconds > 0 ? Math.max(1, Math.round(trafficDelaySeconds / 60)) : 0;
    const trafficSummary = primaryCondition
        ? primaryCondition.type === 'venue_event'
            ? `${primaryCondition.reason} near ${primaryCondition.label}`
            : `${primaryCondition.reason} at ${primaryCondition.label}`
        : null;
    const evRoute = evRouteOptions?.routes?.find(route => route.routeType === 'ev_optimized') || evRouteOptions?.routes?.[0] || null;
    const evAlternate = evRouteOptions?.alternateViaChargerRoute || null;
    const evArrivalSoc = evRoute ? Math.max(0, Math.round(evRoute.predictedArrivalSoCPercent ?? 0)) : null;
    const evEnergyKwh = evRoute ? Number(evRoute.energyConsumedKwh ?? 0) : null;
    const evEfficiency = evRoute ? Number(evRoute.efficiencyKwhPerKm ?? 0) : null;
    const evChargerCount = Array.isArray(evChargers) ? evChargers.length : 0;

    // Dynamic values based on navProgress
    const remainingEtaSeconds = Math.max(0, totalEtaSeconds * (1 - navProgress));
    const currentEtaMins = Math.max(0, Math.ceil(remainingEtaSeconds / 60));
    const currentDistKm = Math.max(0, totalDistanceKm * (1 - navProgress)).toFixed(1);

    const displayedEtaSeconds = isNavigating ? remainingEtaSeconds : totalEtaSeconds;
    const arrivalTime = new Date(currentTime.getTime() + displayedEtaSeconds * 1000);
    const arrivalString = arrivalTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Static Navigation Status
    let instructionTitle = "Active Navigation";
    let instructionSub = "Monitoring 5G Signal Strength...";
    let icon = "M13 10V3L4 14h7v7l9-11h-7z"; // lightning bolt

    if (trafficSummary) {
        instructionSub = trafficSummary;
    }

    if (isNavigating) {
        const liveBandwidth = currentNavSignal?.expectedBandwidthMbps ?? null;
        const liveScore = Math.round(currentNavSignal?.score ?? connectivityScore);
        const liveBand = currentNavSignal?.dominantBand || dominantBand;
        const liveQuality = getSignalQualityLabel(liveScore);
        const bandwidthToneClass = liveScore < 25
            ? 'text-red-400'
            : liveScore < 40
                ? 'text-orange-300'
                : liveScore < 65
                    ? 'text-amber-300'
                    : 'text-emerald-300';
        const activeMetricLabel = isEvMode ? 'Battery' : personaPreset === 'safe_commute' ? 'Safety' : personaPreset === 'suv' ? 'SUV' : 'Signal';
        const activeMetricValue = isEvMode ? (evArrivalSoc ?? 0) : personaPreset === 'safe_commute' ? safetyScore : personaPreset === 'suv' ? suvScore : liveScore;
        const activeMetricToneClass = isEvMode
            ? evArrivalSoc === null ? 'text-slate-300' : evArrivalSoc < 20 ? 'text-red-400' : evArrivalSoc < 35 ? 'text-amber-300' : 'text-lime-300'
            : personaPreset === 'safe_commute' || personaPreset === 'suv'
            ? 'text-amber-300'
            : bandwidthToneClass;
        const navProgressPct = Math.max(0, Math.min(100, Math.round(navProgress * 100)));

        if (!navDetailsOpen) {
            return (
                <div className="absolute bottom-4 left-6 z-20 w-[min(44rem,calc(100vw-1rem))] rounded-2xl border border-white/15 bg-slate-950/90 px-3 py-2.5 shadow-[0_18px_45px_rgba(0,0,0,0.52)] backdrop-blur-2xl">
                    <div className="flex flex-wrap items-center gap-2.5">
                        <div className={`h-9 w-9 shrink-0 rounded-xl border ${preferRouteA ? 'border-emerald-400/30 bg-emerald-400/15 text-emerald-300' : 'border-sky-400/30 bg-sky-400/15 text-sky-300'} flex items-center justify-center`}>
                            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d={icon}></path></svg>
                        </div>

                        <div className="min-w-[5.5rem]">
                            <span className="block text-[8px] font-bold uppercase tracking-widest text-slate-500">ETA</span>
                            <span className="text-xl font-bold text-white">{currentEtaMins}<span className="ml-1 text-xs font-semibold text-slate-400">min</span></span>
                        </div>

                        <div className="min-w-[4.5rem]">
                            <span className="block text-[8px] font-bold uppercase tracking-widest text-slate-500">Left</span>
                            <span className="text-sm font-bold text-slate-200">{currentDistKm} km</span>
                        </div>

                        <div className="min-w-[4.5rem]">
                            <span className="block text-[8px] font-bold uppercase tracking-widest text-slate-500">{activeMetricLabel}</span>
                            <span className={`text-sm font-bold ${activeMetricToneClass}`}>{activeMetricValue}<span className="text-[10px] text-slate-500">{isEvMode ? '%' : '/100'}</span></span>
                        </div>

                        <div className="hidden min-w-[7rem] sm:block">
                            <span className="block text-[8px] font-bold uppercase tracking-widest text-slate-500">Bandwidth</span>
                            <span className={`text-sm font-bold ${bandwidthToneClass}`}>
                                {liveBandwidth !== null ? liveBandwidth.toFixed(1) : '--'}
                                <span className="ml-1 text-[10px] text-slate-500">Mbps</span>
                            </span>
                        </div>

                        <div className="hidden min-w-[5rem] md:block">
                            <span className="block text-[8px] font-bold uppercase tracking-widest text-slate-500">Link</span>
                            <span className="block truncate text-sm font-bold text-blue-300">{liveBand}</span>
                        </div>

                        <div className="min-w-[7rem] flex-1">
                            <div className="mb-1 flex items-center justify-between gap-2">
                                <span className="truncate text-[9px] font-bold uppercase tracking-widest text-slate-500">{routeLabel}</span>
                                <span className="text-[9px] font-bold text-slate-400">{navProgressPct}%</span>
                            </div>
                            <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                                <div
                                    className={`h-full rounded-full ${preferRouteA ? 'bg-emerald-400' : 'bg-sky-400'}`}
                                    style={{ width: `${navProgressPct}%` }}
                                />
                            </div>
                        </div>

                        <button
                            onClick={() => setNavDetailsOpen(true)}
                            className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-200 transition hover:bg-white/10"
                        >
                            Details
                        </button>
                        <button
                            onClick={() => setIsNavigating(false)}
                            className="rounded-xl bg-red-500 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-white shadow-lg shadow-red-500/20 transition hover:bg-red-600"
                        >
                            Exit
                        </button>
                    </div>
                </div>
            );
        }

        return (
            <div className="absolute bottom-6 left-6 z-10 w-[min(26rem,calc(100vw-2rem))] bg-slate-950/95 backdrop-blur-3xl border border-white/20 rounded-2xl p-5 shadow-[0_20px_50px_rgba(0,0,0,0.55)] flex flex-col gap-4 transition-all">
                <div className="flex items-center gap-5">
                    <div className="bg-emerald-500/20 p-3 rounded-xl border border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.2)]">
                        <svg className="w-10 h-10 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d={icon}></path></svg>
                    </div>
                    <div>
                        <h2 className="text-white font-bold text-2xl">{instructionTitle}</h2>
                        <p className="text-emerald-300 text-xs font-bold tracking-wider uppercase mt-1">{instructionSub}</p>
                    </div>
                    <button
                        onClick={() => setNavDetailsOpen(false)}
                        className="ml-auto rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-300 transition hover:bg-white/10"
                    >
                        Collapse
                    </button>
                </div>

                <div className="grid grid-cols-3 gap-3">
                    <div className="bg-white/5 border border-white/10 rounded-xl px-3 py-3">
                        <span className="block text-[9px] text-slate-500 uppercase tracking-widest font-bold mb-1">
                            Bandwidth
                        </span>
                        <span className={`text-2xl font-bold ${bandwidthToneClass}`}>
                            {liveBandwidth !== null ? liveBandwidth.toFixed(1) : '--'}
                        </span>
                        <span className="ml-1 text-xs font-semibold text-slate-400">Mbps</span>
                    </div>
                    <div className="bg-white/5 border border-white/10 rounded-xl px-3 py-3">
                        <span className="block text-[9px] text-slate-500 uppercase tracking-widest font-bold mb-1">
                            {isEvMode ? 'Battery' : personaPreset === 'safe_commute' ? 'Safety' : personaPreset === 'suv' ? 'SUV fit' : 'Signal'}
                        </span>
                        <span className={`text-2xl font-bold ${isEvMode ? (evArrivalSoc !== null && evArrivalSoc < 20 ? 'text-red-400' : 'text-lime-300') : personaPreset === 'safe_commute' || personaPreset === 'suv' ? 'text-amber-300' : 'text-white'}`}>
                            {isEvMode ? (evArrivalSoc ?? '--') : personaPreset === 'safe_commute' ? safetyScore : personaPreset === 'suv' ? suvScore : liveScore}
                        </span>
                        <span className="ml-1 text-xs font-semibold text-slate-400">{isEvMode ? '%' : '/100'}</span>
                    </div>
                    <div className="bg-white/5 border border-white/10 rounded-xl px-3 py-3">
                        <span className="block text-[9px] text-slate-500 uppercase tracking-widest font-bold mb-1">
                            Link
                        </span>
                        <span className="block text-sm font-bold text-blue-300 truncate">{liveBand}</span>
                        <span className="block text-[11px] font-semibold text-slate-400 mt-1">{liveQuality}</span>
                    </div>
                </div>

                <SignalProfileBar profile={signalProfile} />

                <div className="flex justify-between items-end mt-2 pt-5 border-t border-white/10">
                    <div className="flex gap-4 items-baseline">
                        <span className="text-slate-400 font-bold uppercase text-xs tracking-widest">{routeLabel}</span>
                        <span className={`font-bold text-3xl ${preferRouteA ? 'text-emerald-400' : 'text-blue-400'}`}>{currentEtaMins} <span className="text-base font-normal text-slate-400">min</span></span>
                        <span className="text-slate-300 font-semibold">{currentDistKm} km</span>
                        <span className="text-slate-400 font-medium">ETA {arrivalString}</span>
                    </div>
                    <button
                        onClick={() => setIsNavigating(false)}
                        className="bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-500/30 px-6 py-3 rounded-xl text-sm font-bold transition-all uppercase tracking-widest"
                    >
                        Exit
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="absolute bottom-6 left-6 z-10 w-[min(30rem,calc(100vw-2rem))] bg-slate-950/90 backdrop-blur-2xl border border-white/15 rounded-2xl p-5 shadow-[0_22px_60px_rgba(0,0,0,0.52)] flex flex-col gap-4 transition-all">
            <div className="flex justify-between items-start gap-4">
                <div>
                    <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${preferRouteA ? 'bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.8)]' : 'bg-sky-400 shadow-[0_0_12px_rgba(56,189,248,0.8)]'}`}></span>
                        <span className={`text-[10px] font-bold uppercase tracking-widest ${preferRouteA ? 'text-emerald-300' : 'text-sky-300'}`}>{routeLabel} selected</span>
                    </div>
                    <div className="flex items-baseline gap-2 mt-1">
                        <span className="text-4xl font-bold text-white tracking-tight"><AnimatedNumber value={totalEtaMins} /></span>
                        <span className="text-lg font-semibold text-slate-300">min</span>
                        <span className="text-sm text-slate-400">{totalDistanceKm} km</span>
                    </div>
                </div>
                <div className="text-right pt-1">
                    <span className="block text-[9px] text-slate-500 uppercase tracking-widest font-bold">Arrival</span>
                    <span className="text-sm font-semibold text-slate-200">{arrivalString}</span>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
                {routeChoices.map((route, index) => (
                    <RouteChoice key={`${route.route_id || routeLabel}-${index}`} route={route} index={index} selected={preferredRouteIndex === index} />
                ))}
            </div>

            {trafficDelayMins > 0 && (
                <div className="bg-amber-400/10 text-amber-100 rounded-lg px-3 py-2 border border-amber-300/20 text-[11px] leading-relaxed">
                    ETA includes +{trafficDelayMins} min for conditions {primaryCondition ? `near ${primaryCondition.label}` : 'on this route'}.
                </div>
            )}

            {trafficSummary && !trafficDelayMins && (
                <div className="bg-amber-400/10 text-amber-100 rounded-lg px-3 py-2 border border-amber-300/20 text-[11px] leading-relaxed">
                    Monitoring {trafficSummary}.
                </div>
            )}

            {isEvMode && (
                <div className="rounded-xl border border-lime-300/20 bg-lime-400/10 px-3 py-3 text-lime-50">
                    <div className="flex items-center justify-between gap-3">
                        <div>
                            <span className="block text-[8px] font-bold uppercase tracking-widest text-lime-200/80">EV route</span>
                            <span className={`text-2xl font-bold ${evArrivalSoc !== null && evArrivalSoc < 20 ? 'text-red-300' : 'text-lime-200'}`}>
                                {evArrivalSoc === null ? '--' : evArrivalSoc}<span className="ml-1 text-xs text-lime-100/70">%</span>
                            </span>
                        </div>
                        <div className="text-right text-[10px] font-semibold text-lime-100/80">
                            <div>{evEnergyKwh === null ? '--' : evEnergyKwh.toFixed(1)} kWh</div>
                            <div>{evEfficiency === null ? '--' : evEfficiency.toFixed(2)} kWh/km</div>
                            <div>{evChargerCount} chargers</div>
                        </div>
                    </div>
                    {evAlternate?.chargerWaypoints?.[0] && (
                        <div className="mt-2 rounded-lg border border-lime-200/15 bg-black/20 px-2.5 py-2 text-[11px] leading-relaxed text-lime-50/90">
                            Charger detour: {evAlternate.chargerWaypoints[0].name || 'fast charger'} · {Number(evAlternate.chargerWaypoints[0].capacity_kw || 0).toFixed(0)} kW.
                        </div>
                    )}
                    {evHeatmapMeta?.truncated && (
                        <div className="mt-2 text-[10px] text-lime-100/65">
                            Showing {evHeatmapMeta.count} EV heat segments in view.
                        </div>
                    )}
                </div>
            )}



            <div className="grid grid-cols-3 bg-black/45 rounded-xl border border-white/10 divide-x divide-white/10">
                <div className="px-3 py-3 text-center">
                    <span className="block text-[8px] text-slate-500 uppercase tracking-widest font-bold mb-1">
                        {isEvMode ? 'Battery' : personaPreset === 'safe_commute' ? 'Safety' : personaPreset === 'suv' ? 'SUV fit' : 'Signal'}
                    </span>
                    {isEvMode ? (
                        <span className={`text-xl font-bold ${evArrivalSoc !== null && evArrivalSoc < 20 ? 'text-red-400' : evArrivalSoc !== null && evArrivalSoc < 35 ? 'text-amber-300' : 'text-lime-300'}`}>{evArrivalSoc === null ? '--' : <AnimatedNumber value={evArrivalSoc} />}<span className="text-xs text-slate-400">%</span></span>
                    ) : personaPreset === 'safe_commute' ? (
                        <span className={`text-xl font-bold ${safetyScore < 50 ? 'text-red-400' : safetyScore < 80 ? 'text-amber-300' : 'text-emerald-300'}`}><AnimatedNumber value={safetyScore} /><span className="text-xs text-slate-400">/100</span></span>
                    ) : personaPreset === 'suv' ? (
                        <span className={`text-xl font-bold ${suvScore < 50 ? 'text-red-400' : suvScore < 80 ? 'text-amber-300' : 'text-emerald-300'}`}><AnimatedNumber value={suvScore} /><span className="text-xs text-slate-400">/100</span></span>
                    ) : (
                        <span className={`text-xl font-bold ${connectivityScore < 50 ? 'text-red-400' : connectivityScore < 80 ? 'text-amber-300' : 'text-emerald-300'}`}><AnimatedNumber value={connectivityScore} /><span className="text-xs text-slate-400">/100</span></span>
                    )}
                </div>
                <div className="px-3 py-3 text-center">
                    <span className="block text-[8px] text-slate-500 uppercase tracking-widest font-bold mb-1">
                        {isEvMode ? 'Chargers' : personaPreset === 'safe_commute' || personaPreset === 'suv' ? 'Hard blocks' : 'Dead zones'}
                    </span>
                    <span className={`text-xl font-bold ${isEvMode ? 'text-lime-300' : (personaPreset === 'safe_commute' ? safetyHardBlockCount : personaPreset === 'suv' ? suvHardBlockCount : deadZoneCount) > 0 ? 'text-red-400' : (personaPreset === 'safe_commute' || personaPreset === 'suv' ? 'text-amber-300' : 'text-emerald-300')}`}>
                        {isEvMode ? evChargerCount : personaPreset === 'safe_commute' ? safetyHardBlockCount : personaPreset === 'suv' ? suvHardBlockCount : deadZoneCount}
                    </span>
                </div>
                <div className="px-3 py-3 text-center">
                    <span className="block text-[8px] text-slate-500 uppercase tracking-widest font-bold mb-1">{isEvMode ? 'Energy' : 'Network'}</span>
                    <span className={`text-base font-bold ${isEvMode ? 'text-lime-300' : 'text-sky-300'}`}>{isEvMode ? (evEnergyKwh === null ? '--' : `${evEnergyKwh.toFixed(1)} kWh`) : dominantBand}</span>
                </div>
            </div>

            <SignalProfileBar profile={signalProfile} />

            <MagneticButton
                onClick={() => setIsNavigating(true)}
                disabled={!hasRouteData}
                className={`w-full py-3.5 rounded-xl font-bold text-base text-white shadow-lg transition-all uppercase tracking-widest disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400 disabled:shadow-none ${preferRouteA ? 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-950/80' : 'bg-sky-600 hover:bg-sky-500 shadow-sky-950/80'}`}
            >
                {hasRouteData ? 'Start Navigation' : routeUnavailable ? 'Route Unavailable' : 'Loading Route...'}
            </MagneticButton>
        </div>
    );
}
