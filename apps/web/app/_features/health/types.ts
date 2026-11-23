export type Health = {
  status: "ok" | "degraded";
  app_server: {
    running: boolean;
    authenticated: boolean;
    version: string | null;
    platform: string | null;
  };
};
