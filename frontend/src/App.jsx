import { useEffect } from 'react';
import { useStore } from './store';
import MapContainer from './components/Map/MapContainer';
import PersonaPanel from './components/PersonaPanel';
import TelemetryHUD from './components/TelemetryHUD';
import NavigationPanel from './components/NavigationPanel';
import RouteSearch from './components/RouteSearch';
import CameraControls from './components/CameraControls';

function App() {
  const isDarkMode = useStore((state) => state.isDarkMode);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDarkMode);
  }, [isDarkMode]);

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black text-slate-100">
      <RouteSearch />
      <MapContainer />
      <PersonaPanel />
      <TelemetryHUD />
      <CameraControls />
      <NavigationPanel />
    </div>
  )
}

export default App;
