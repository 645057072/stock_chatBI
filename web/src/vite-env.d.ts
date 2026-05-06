/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API 路径前缀或完整 http(s) 基地址，见根目录 .env.example */
  readonly VITE_API_PREFIX?: string;
}
