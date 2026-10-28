import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { useState } from "react";

import { UseCasePage } from "../features/dossier/UseCasePage";
import { HealthPage } from "../features/health/HealthPage";
import { PortfolioPage } from "../features/portfolio/PortfolioPage";
import { ApiError } from "../shared/api/client";
import { useRoute } from "../shared/hooks/useRoute";

export function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (n, e) => !(e instanceof ApiError && [401, 403, 404].includes(e.status)) && n < 2,
      },
    },
  });
}

export function App({ client }: { client?: QueryClient }) {
  const [qc] = useState(() => client ?? makeClient());
  const [route, go] = useRoute();
  return (
    <QueryClientProvider client={qc}>
      <MotionConfig reducedMotion="user">
        {route.name === "useCase" ? (
          <UseCasePage id={route.id} tab={route.tab} go={go} />
        ) : route.name === "health" ? (
          <HealthPage customer={route.customer} go={go} />
        ) : (
          <PortfolioPage customer={route.customer} go={go} />
        )}
      </MotionConfig>
    </QueryClientProvider>
  );
}
