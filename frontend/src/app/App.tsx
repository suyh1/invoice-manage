import { AppShell } from "../components/AppShell";
import { renderRoute, useHashRoute } from "./router";

export function App() {
  const activeRoute = useHashRoute();

  return <AppShell activeRoute={activeRoute}>{renderRoute(activeRoute)}</AppShell>;
}
