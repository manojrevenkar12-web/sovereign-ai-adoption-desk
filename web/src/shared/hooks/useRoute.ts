import { useCallback, useEffect, useState } from "react";

// Three screens do not need a router library: /, /customers/:id, /use-cases/:id.
export type Route =
  | { name: "portfolio"; customer: string | null }
  | { name: "useCase"; id: string; tab: string }
  | { name: "health"; customer: string };

export function parse(pathname: string, search = ""): Route {
  const tab = new URLSearchParams(search).get("tab") ?? "why";
  const uc = pathname.match(/^\/use-cases\/([\w-]+)/);
  if (uc) return { name: "useCase", id: uc[1], tab };
  const health = pathname.match(/^\/customers\/([\w-]+)\/health/);
  if (health) return { name: "health", customer: health[1] };
  const cust = pathname.match(/^\/customers\/([\w-]+)/);
  return { name: "portfolio", customer: cust ? cust[1] : null };
}

export function useRoute(): [Route, (to: string) => void] {
  const [route, setRoute] = useState<Route>(() => parse(window.location.pathname, window.location.search));
  useEffect(() => {
    const on = () => setRoute(parse(window.location.pathname, window.location.search));
    window.addEventListener("popstate", on);
    return () => window.removeEventListener("popstate", on);
  }, []);
  const go = useCallback((to: string) => {
    window.history.pushState(null, "", to);
    setRoute(parse(window.location.pathname, window.location.search));
    window.scrollTo({ top: 0 });
  }, []);
  return [route, go];
}
