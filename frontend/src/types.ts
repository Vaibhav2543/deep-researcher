// frontend/src/types.ts
export type Source = {
  source: string;
  text: string;
  dist: number;
};

export type QueryResponse = {
  answer?: string;
  sources?: Source[];
  detail?: string;
};
