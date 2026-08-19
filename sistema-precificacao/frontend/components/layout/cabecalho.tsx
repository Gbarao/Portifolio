"use client";

import { Moon, Sun } from "lucide-react";
import * as React from "react";

import { Botao } from "@/components/ui/primitivos";

/** Alternador de tema. O padrao segue a preferencia do sistema. */
export function AlternadorTema() {
  const [tema, setTema] = React.useState<"claro" | "escuro" | null>(null);

  React.useEffect(() => {
    const salvo = window.localStorage.getItem("tema") as "claro" | "escuro" | null;
    if (salvo) {
      document.documentElement.dataset.tema = salvo;
      setTema(salvo);
    }
  }, []);

  function alternar() {
    const atual =
      tema ??
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "escuro" : "claro");
    const proximo = atual === "escuro" ? "claro" : "escuro";
    document.documentElement.dataset.tema = proximo;
    window.localStorage.setItem("tema", proximo);
    setTema(proximo);
  }

  return (
    <Botao
      variante="fantasma"
      tamanho="sm"
      onClick={alternar}
      aria-label="Alternar entre tema claro e escuro"
    >
      <Sun className="size-4 dark:hidden" aria-hidden />
      <Moon className="hidden size-4 dark:block" aria-hidden />
    </Botao>
  );
}
