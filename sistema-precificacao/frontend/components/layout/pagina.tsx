import * as React from "react";

/** Cabecalho padrao de pagina: titulo, descricao e acoes. */
export function CabecalhoPagina({
  titulo,
  descricao,
  acoes,
}: {
  titulo: string;
  descricao?: React.ReactNode;
  acoes?: React.ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4 pb-6">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight">{titulo}</h1>
        {descricao ? (
          <p className="mt-1 max-w-2xl text-sm text-texto-suave">{descricao}</p>
        ) : null}
      </div>
      {acoes ? <div className="flex shrink-0 gap-2">{acoes}</div> : null}
    </header>
  );
}
