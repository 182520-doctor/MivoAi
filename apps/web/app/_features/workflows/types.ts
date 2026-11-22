export type WorkflowCatalogItem = {
  filename: string;
  imported: boolean;
  workflowId: string | null;
  name: string;
  capability: string | null;
  status: string;
  modelId: string | null;
  testAssetId: string | null;
  testMessage: string | null;
  parameters: WorkflowParameter[];
};

export type WorkflowParameter = {
  key: string;
  label: string;
  type: "string" | "integer" | "number" | "boolean" | "assets";
  assetType?: "image" | "video" | "audio" | "file";
  semanticKey?: string;
  derived?: boolean;
  required: boolean;
  default?: unknown;
  min?: number;
  max?: number;
  options?: unknown[];
  bindings?: Array<{
    nodeId: string;
    field: string;
    assetIndex?: number;
  }>;
};

export type WorkflowInput = {
  id: string;
  nodeId: string;
  nodeType: string;
  nodeTitle: string;
  field: string;
  fieldLabel: string;
  label: string;
  type: WorkflowParameter["type"];
  default?: unknown;
  linked: boolean;
  linkedTo?: [string, number];
  options?: unknown[];
  assetType?: "image" | "video" | "audio" | "file";
  bindings?: Array<{ nodeId: string; field: string }>;
  subgraph?: boolean;
};

export type WorkflowInputs = {
  workflowId: string;
  inputs: WorkflowInput[];
  parameters: WorkflowParameter[];
  topology: WorkflowTopology;
};

export type WorkflowTopologyNode = {
  id: string;
  classType: string;
  title: string;
  pos: [number, number];
  size: [number, number];
  mode?: number;
  subgraph?: boolean;
};

export type WorkflowTopologyLink = {
  originId: string;
  originSlot: number;
  targetId: string;
  targetSlot?: number;
  targetField?: string;
  type?: string;
};

export type WorkflowTopology = {
  nodes: WorkflowTopologyNode[];
  links: WorkflowTopologyLink[];
};

export type WorkflowCatalog = {
  comfyuiUrl: string;
  available: boolean;
  error: string | null;
  workflows: WorkflowCatalogItem[];
};

export type ImportedWorkflow = {
  id: string;
  sourceFilename: string;
  name: string;
  capability: string;
  status: string;
  bindings: Record<string, { nodeId: string; field: string } | null>;
  outputNodeId: string;
  modelId: string;
  testAssetId: string | null;
  testMessage: string | null;
  testAssetUrl?: string;
  parameters: WorkflowParameter[];
  inputs?: WorkflowInput[];
};
