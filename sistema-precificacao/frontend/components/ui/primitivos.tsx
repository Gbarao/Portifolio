/**
 * Primitivos de interface.
 *
 * Sao poucos e deliberadamente simples: cartao, botao, tabela, campo e
 * distintivo. A complexidade do sistema esta nos numeros, nao nos widgets --
 * a interface tem que sumir para o dado aparecer.
 */

import { Slot } from "@radix-ui/react-slot";
import * as React from "react";

import { cx } from "@/lib/utilitarios";

/* ------------------------------------------------------------------ Cartao */

export function Cartao({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx(
        "rounded-xl border border-borda bg-fundo-elevado shadow-sm",
        className,
      )}
      {...props}
    />
  );
}

export function CartaoCabecalho({
  titulo,
  descricao,
  acao,
  className,
}: {
  titulo: React.ReactNode;
  descricao?: React.ReactNode;
  acao?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "flex items-start justify-between gap-4 border-b border-borda px-5 py-4",
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="text-sm font-semibold tracking-tight">{titulo}</h2>
        {descricao ? (
          <p className="mt-1 text-sm text-texto-suave">{descricao}</p>
        ) : null}
      </div>
      {acao ? <div className="shrink-0">{acao}</div> : null}
    </div>
  );
}

export function CartaoCorpo({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx("px-5 py-4", className)} {...props} />;
}

/* ------------------------------------------------------------------- Botao */

type VarianteBotao = "primario" | "secundario" | "fantasma" | "perigo";
type TamanhoBotao = "sm" | "md";

const VARIANTES: Record<VarianteBotao, string> = {
  primario:
    "bg-marca-600 text-white hover:bg-marca-700 focus-visible:outline-marca-600",
  secundario:
    "border border-borda-forte bg-fundo-elevado hover:bg-fundo-sutil focus-visible:outline-marca-600",
  fantasma: "hover:bg-fundo-sutil focus-visible:outline-marca-600",
  perigo: "bg-critico text-white hover:opacity-90 focus-visible:outline-critico",
};

const TAMANHOS: Record<TamanhoBotao, string> = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-9 px-4 text-sm gap-2",
};

export interface BotaoProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: VarianteBotao;
  tamanho?: TamanhoBotao;
  asChild?: boolean;
}

export const Botao = React.forwardRef<HTMLButtonElement, BotaoProps>(
  function Botao(
    { className, variante = "primario", tamanho = "md", asChild, ...props },
    ref,
  ) {
    const Componente = asChild ? Slot : "button";
    return (
      <Componente
        ref={ref}
        className={cx(
          "inline-flex items-center justify-center rounded-lg font-medium transition-colors",
          "focus-visible:outline-2 focus-visible:outline-offset-2",
          "disabled:pointer-events-none disabled:opacity-50",
          VARIANTES[variante],
          TAMANHOS[tamanho],
          className,
        )}
        {...props}
      />
    );
  },
);

/* -------------------------------------------------------------- Distintivo */

export type TomDistintivo =
  | "neutro"
  | "ok"
  | "info"
  | "atencao"
  | "critico"
  | "marca";

const TONS: Record<TomDistintivo, string> = {
  neutro: "bg-fundo-sutil text-texto-suave border-borda",
  ok: "bg-ok-fundo text-ok border-ok/25",
  info: "bg-info-fundo text-info border-info/25",
  atencao: "bg-atencao-fundo text-atencao border-atencao/30",
  critico: "bg-critico-fundo text-critico border-critico/25",
  marca: "bg-marca-50 text-marca-700 border-marca-200",
};

export function Distintivo({
  tom = "neutro",
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tom?: TomDistintivo }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5",
        "text-xs font-medium whitespace-nowrap",
        TONS[tom],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ Tabela */

export function Tabela({
  className,
  ...props
}: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cx("w-full text-sm", className)} {...props} />
    </div>
  );
}

export function Th({
  className,
  numerica,
  ...props
}: React.ThHTMLAttributes<HTMLTableCellElement> & { numerica?: boolean }) {
  return (
    <th
      className={cx(
        "border-b border-borda px-4 py-2.5 text-xs font-medium tracking-wide",
        "text-texto-tenue uppercase",
        numerica ? "text-right" : "text-left",
        className,
      )}
      {...props}
    />
  );
}

export function Td({
  className,
  numerica,
  ...props
}: React.TdHTMLAttributes<HTMLTableCellElement> & { numerica?: boolean }) {
  return (
    <td
      className={cx(
        "border-b border-borda/60 px-4 py-2.5 align-middle",
        numerica ? "numerico text-right" : "text-left",
        className,
      )}
      {...props}
    />
  );
}

export function LinhaTabela({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={cx("transition-colors hover:bg-fundo-sutil", className)} {...props} />
  );
}

/* ------------------------------------------------------------------- Campo */

export function Campo({
  rotulo,
  dica,
  erro,
  children,
}: {
  rotulo: string;
  dica?: string;
  erro?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="block text-sm font-medium">{rotulo}</span>
      {children}
      {dica && !erro ? (
        <span className="block text-xs text-texto-tenue">{dica}</span>
      ) : null}
      {erro ? <span className="block text-xs text-critico">{erro}</span> : null}
    </label>
  );
}

export const Entrada = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(function Entrada({ className, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={cx(
        "h-9 w-full rounded-lg border border-borda-forte bg-fundo-elevado px-3 text-sm",
        "placeholder:text-texto-tenue",
        "focus:border-marca-500 focus:outline-2 focus:outline-offset-0 focus:outline-marca-500/30",
        className,
      )}
      {...props}
    />
  );
});

export const Selecao = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(function Selecao({ className, ...props }, ref) {
  return (
    <select
      ref={ref}
      className={cx(
        "h-9 w-full rounded-lg border border-borda-forte bg-fundo-elevado px-3 text-sm",
        "focus:border-marca-500 focus:outline-2 focus:outline-offset-0 focus:outline-marca-500/30",
        className,
      )}
      {...props}
    />
  );
});

/* --------------------------------------------------------- Estados vazios */

export function Vazio({
  titulo,
  descricao,
  acao,
}: {
  titulo: string;
  descricao?: string;
  acao?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <p className="text-sm font-medium">{titulo}</p>
      {descricao ? (
        <p className="max-w-md text-sm text-texto-suave">{descricao}</p>
      ) : null}
      {acao ? <div className="mt-2">{acao}</div> : null}
    </div>
  );
}

export function Rotulo({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "text-xs font-medium tracking-wide text-texto-tenue uppercase",
        className,
      )}
    >
      {children}
    </span>
  );
}
