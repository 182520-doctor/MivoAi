export type Model = {
  id: string;
  providerId: string;
  providerName: string;
  name: string;
  modelKey: string;
  capabilities: string[];
  executionMode: string;
  configured: boolean;
  integrationStatus: string;
};
export type Preferences = { defaultTextModelId?: string };
