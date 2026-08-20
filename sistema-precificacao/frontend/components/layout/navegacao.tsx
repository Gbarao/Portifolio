"use client";

/**
 * Navegacao lateral pelos cinco modulos da especificacao (secao 1 do pedido):
 * Cadastros, Operacoes, Motor Tributario, Cotacoes e Painel Gerencial.
 */

import {
  Boxes,
  Calculator,
  ChartNoAxesCombined,
  Factory,
  Landmark,
  Recycle,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cx } from "@/lib/utilitarios";

interface ItemNavegacao {
  titulo: string;
  href: string;
  Icone: typeof Boxes;
  filhos?: { titulo: string; href: string }[];
  emBreve?: boolean;
}

const MODULOS: ItemNavegacao[] = [
  {
    titulo: "Cadastros",
    href: "/cadastros/materiais",
    Icone: Boxes,
    filhos: [
      { titulo: "Materiais", href: "/cadastros/materiais" },
      { titulo: "Parceiros", href: "/cadastros/parceiros" },
      { titulo: "Unidades e parâmetros", href: "/cadastros/unidades" },
    ],
  },
  {
    titulo: "Operações",
    href: "/operacoes/lotes",
    Icone: Factory,
    filhos: [{ titulo: "Lotes de compra", href: "/operacoes/lotes" }],
  },
  {
    titulo: "Motor tributário",
    href: "/tributario/regras",
    Icone: Landmark,
    filhos: [
      { titulo: "Matriz de regras", href: "/tributario/regras" },
      { titulo: "Simples Nacional", href: "/tributario/simples" },
    ],
  },
  { titulo: "Cotações", href: "/cotacoes", Icone: Calculator },
  { titulo: "Painel gerencial", href: "/painel", Icone: ChartNoAxesCombined },
];

export function Navegacao() {
  const caminho = usePathname();

  return (
    <nav className="flex h-full flex-col gap-1 p-3" aria-label="Módulos do sistema">
      <Link
        href="/"
        className="mb-4 flex items-center gap-2.5 rounded-lg px-2 py-2 transition-colors hover:bg-fundo-sutil"
      >
        <span className="flex size-8 items-center justify-center rounded-lg bg-marca-600 text-white">
          <Recycle className="size-4" aria-hidden />
        </span>
        <span className="min-w-0">
          <span className="block text-sm leading-tight font-semibold">
            Precificação
          </span>
          <span className="block text-xs text-texto-tenue">Reciclagem</span>
        </span>
      </Link>

      {MODULOS.map((modulo) => {
        const ativo = caminho.startsWith(`/${modulo.href.split("/")[1]}`);
        return (
          <div key={modulo.titulo}>
            <Link
              href={modulo.emBreve ? "#" : modulo.href}
              aria-disabled={modulo.emBreve}
              aria-current={ativo ? "page" : undefined}
              className={cx(
                "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
                ativo
                  ? "bg-marca-50 font-medium text-marca-700"
                  : "text-texto-suave hover:bg-fundo-sutil hover:text-texto",
                modulo.emBreve && "pointer-events-none opacity-45",
              )}
            >
              <modulo.Icone className="size-4 shrink-0" aria-hidden />
              <span className="flex-1">{modulo.titulo}</span>
              {modulo.emBreve ? (
                <span className="text-[10px] tracking-wide text-texto-tenue uppercase">
                  Passo 6
                </span>
              ) : null}
            </Link>

            {ativo && modulo.filhos ? (
              <ul className="mt-0.5 ml-6 space-y-0.5 border-l border-borda pl-3">
                {modulo.filhos.map((filho) => (
                  <li key={filho.href}>
                    <Link
                      href={filho.href}
                      aria-current={caminho === filho.href ? "page" : undefined}
                      className={cx(
                        "block rounded-md px-2 py-1.5 text-sm transition-colors",
                        caminho === filho.href
                          ? "font-medium text-texto"
                          : "text-texto-suave hover:text-texto",
                      )}
                    >
                      {filho.titulo}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        );
      })}
    </nav>
  );
}
