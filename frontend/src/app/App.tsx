import { AppShell } from "../components/AppShell";
import { useAuth } from "../auth/AuthContext";
import { resolveAuthScreen } from "../auth/authState";
import { AuthLandingPage, AuthStatusPage } from "../pages/AuthLandingPage";
import { renderRoute, useHashRoute } from "./router";

export function App() {
  const auth = useAuth();
  const activeRoute = useHashRoute(auth.user?.role ?? null);

  if (auth.loadFailed) {
    return <AuthStatusPage mode="error" onRetry={auth.refresh} />;
  }

  const screen = resolveAuthScreen({ initialized: auth.initialized, user: auth.user });
  if (screen === "loading") {
    return <AuthStatusPage mode="loading" onRetry={auth.refresh} />;
  }

  if (screen === "bootstrap" || screen === "login") {
    return (
      <AuthLandingPage
        mode={screen}
        busy={auth.busy}
        errorMessage={auth.errorMessage}
        onBootstrap={auth.bootstrap}
        onLogin={auth.login}
      />
    );
  }

  return (
    <AppShell activeRoute={activeRoute}>
      {renderRoute(activeRoute)}
    </AppShell>
  );
}
