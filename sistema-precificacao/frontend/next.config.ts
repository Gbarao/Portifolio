import type { NextConfig } from "next";

/**
 * A interface e exportada como arquivos estaticos e servida pelo proprio
 * servidor Python. E isso que permite o sistema rodar como um programa so:
 * quem usa nao precisa de Node.js instalado nem de um segundo processo.
 */
const config: NextConfig = {
  output: "export",
  reactStrictMode: true,
  images: { unoptimized: true },
  // Cada rota vira uma pasta com index.html, servida sem reescrita de URL.
  trailingSlash: true,
  env: {
    // Caminho relativo: a interface conversa com a API pelo mesmo endereco que
    // a serviu, sem configuracao de porta nem CORS. Em desenvolvimento com
    // `npm run dev`, o .env.local aponta para o servidor em outra porta.
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "/api",
  },
};

export default config;
