import type { Metadata } from "next";

import { AlternadorTema } from "@/components/layout/cabecalho";
import { Navegacao } from "@/components/layout/navegacao";

import "./globals.css";

export const metadata: Metadata = {
  title: "Precificação para reciclagem",
  description:
    "Sistema de custeio e precificação para operações de reciclagem: custeio por lote, ABC, motor tributário por regime e escada de preços.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen">
        <div className="flex min-h-screen">
          <aside className="hidden w-60 shrink-0 border-r border-borda bg-fundo-elevado lg:block">
            <div className="sticky top-0 h-screen overflow-y-auto">
              <Navegacao />
            </div>
          </aside>

          <div className="flex min-w-0 flex-1 flex-col">
            <header className="sticky top-0 z-10 flex h-14 items-center justify-between gap-4 border-b border-borda bg-fundo-elevado/85 px-6 backdrop-blur">
              <div className="lg:hidden">
                <span className="text-sm font-semibold">Precificação</span>
              </div>
              <div className="ml-auto flex items-center gap-2">
                <AlternadorTema />
              </div>
            </header>

            <main className="flex-1 px-6 py-8">
              <div className="mx-auto w-full max-w-6xl">{children}</div>
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
