import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import type { CustomerView, Dossier, DraftResult, EnquiryResult, Portfolio } from "../api/types";

export const keys = {
  portfolio: ["portfolio"] as const,
  dossier: (id: string) => ["dossier", id] as const,
  plan: (id: string) => ["plan", id] as const,
  customer: (id: string) => ["customer", id] as const,
};

export function useCustomer(id: string) {
  return useQuery({
    queryKey: keys.customer(id),
    queryFn: () => api.get<Omit<CustomerView, "useCases" | "computedAt">>(`/api/customers/${id}`),
  });
}

export function usePortfolio() {
  return useQuery({ queryKey: keys.portfolio, queryFn: () => api.get<Portfolio>("/api/portfolio") });
}

export function useDossier(id: string) {
  return useQuery({ queryKey: keys.dossier(id), queryFn: () => api.get<Dossier>(`/api/use-cases/${id}`) });
}

export function useAccountPlan(customer: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.plan(customer),
    queryFn: () => api.get<string>(`/api/customers/${customer}/plan.md`),
    enabled,
  });
}

/** Passing or reopening a gate replans the whole portfolio, so every cached view is stale. */
export function useGateChange(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ gate, done }: { gate: string; done: boolean }) =>
      api.post<Dossier>(`/api/use-cases/${id}/gates/${gate}`, { done }),
    onSuccess: (d) => {
      qc.setQueryData(keys.dossier(id), d);
      qc.invalidateQueries({ queryKey: keys.portfolio });
    },
  });
}

export function useAsk(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => api.post<EnquiryResult | DraftResult>(`/api/use-cases/${id}/pov`, { message }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.dossier(id) }),
  });
}
