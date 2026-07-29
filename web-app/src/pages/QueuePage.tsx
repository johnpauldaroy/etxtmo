import { useEffect } from "react";

import { CampaignDeliveryPanel } from "./CampaignDeliveryPanel";
import { Branch, Campaign } from "./types";

type QueuePageProps = {
  campaigns: Campaign[];
  token: string;
  branchId: string;
  branches: Branch[];
  isSuperuser: boolean;
  refreshCampaigns: (token: string, branchId: string) => Promise<void>;
};

export function QueuePage({ campaigns, token, branchId, branches, isSuperuser, refreshCampaigns }: QueuePageProps) {
  useEffect(() => {
    if (!token || !branchId) return;

    const refresh = () => {
      void refreshCampaigns(token, branchId).catch(() => undefined);
    };

    refresh();
    const intervalId = window.setInterval(refresh, 5_000);
    return () => window.clearInterval(intervalId);
  }, [branchId, refreshCampaigns, token]);

  return <CampaignDeliveryPanel campaigns={campaigns} token={token} branches={branches} isSuperuser={isSuperuser} />;
}
