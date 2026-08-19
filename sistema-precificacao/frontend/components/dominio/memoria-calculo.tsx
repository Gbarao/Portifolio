"use client";

/**
 * Visualizacao da memoria de calculo.
 *
 * A secao 15 e explicita: o agente deve conversar em linguagem gerencial, mas
 * nunca ocultar a matematica. Este componente e a materializacao disso -- cada
 * passo mostra formula, entradas, resultado, fonte e vigencia da regra.
 */

import { ChevronDown, FileText } from "lucide-react";
import * as React from "react";

import { Botao, Distintivo, Rotulo } from "@/components/ui/primitivos";
import { numero } from "@/lib/formato";
import { cx } from "@/lib/utilitarios";
import type { Memoria, PassoMemoria } from "@/lib/tipos";

function Passo({ passo }: { passo: PassoMemoria }) {
  const [aberto, setAberto] = React.useState(false);

  return (
    <li className="border-b border-borda/60 last:border-0">
      <button
        type="button"
        onClick={() => setAberto((v) => !v)}
        aria-expanded={aberto}
        className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-fundo-sutil"
      >
        <span className="numerico w-6 shrink-0 text-xs text-texto-tenue">
          {passo.ordem}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{passo.rotulo}</span>
          <span className="block truncate font-mono text-xs text-texto-tenue">
            {passo.formula}
          </span>
        </span>
        <span className="numerico shrink-0 text-sm font-medium">
          {numero(passo.resultado, 4)}
          <span className="ml-1 text-xs font-normal text-texto-tenue">
            {passo.unidade}
          </span>
        </span>
        {passo.alerta ? (
          <span
            className="size-1.5 shrink-0 rounded-full bg-atencao"
            aria-label="passo com alerta"
          />
        ) : null}
        <ChevronDown
          className={cx(
            "size-4 shrink-0 text-texto-tenue transition-transform",
            aberto && "rotate-180",
          )}
          aria-hidden
        />
      </button>

      {aberto ? (
        <div className="space-y-3 bg-fundo-sutil/60 px-5 pt-1 pb-4 pl-14">
          <div>
            <Rotulo>Fórmula</Rotulo>
            <p className="mt-1 font-mono text-xs">{passo.formula}</p>
          </div>

          <div>
            <Rotulo>Entradas</Rotulo>
            <dl className="mt-1 grid gap-x-6 gap-y-1 sm:grid-cols-2">
              {Object.entries(passo.entradas).map(([chave, valor]) => (
                <div key={chave} className="flex justify-between gap-4 text-xs">
                  <dt className="text-texto-suave">{chave}</dt>
                  <dd className="numerico">{valor}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            {passo.fonte ? (
              <Distintivo tom="neutro">Fonte: {passo.fonte}</Distintivo>
            ) : null}
            {passo.vigencia_regra ? (
              <Distintivo tom="neutro">Vigência: {passo.vigencia_regra}</Distintivo>
            ) : null}
            <Distintivo tom={passo.status_dado === "CONFIRMADO" ? "ok" : "atencao"}>
              {passo.status_dado}
            </Distintivo>
          </div>

          {passo.alerta ? (
            <p className="rounded-md border border-atencao/30 bg-atencao-fundo px-3 py-2 text-xs">
              {passo.alerta}
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

export function MemoriaCalculo({ memoria }: { memoria: Memoria }) {
  const [tudoAberto, setTudoAberto] = React.useState(false);

  function exportar() {
    const conteudo = JSON.stringify(memoria, null, 2);
    const blob = new Blob([conteudo], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `memoria-${memoria.titulo.toLowerCase().replace(/\s+/g, "-")}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="rounded-xl border border-borda bg-fundo-elevado">
      <div className="flex items-center justify-between gap-4 border-b border-borda px-5 py-4">
        <div className="flex items-center gap-2">
          <FileText className="size-4 text-texto-tenue" aria-hidden />
          <div>
            <h2 className="text-sm font-semibold">Memória de cálculo</h2>
            <p className="text-xs text-texto-suave">
              {memoria.passos.length} passos — cada preço pode ser refeito à mão
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Botao variante="secundario" tamanho="sm" onClick={exportar}>
            Exportar JSON
          </Botao>
          <Botao
            variante="fantasma"
            tamanho="sm"
            onClick={() => setTudoAberto((v) => !v)}
          >
            {tudoAberto ? "Recolher" : "Expandir"} tudo
          </Botao>
        </div>
      </div>

      <ul key={String(tudoAberto)}>
        {memoria.passos.map((passo) => (
          <PassoControlado
            key={`${passo.ordem}-${passo.rotulo}`}
            passo={passo}
            inicialmenteAberto={tudoAberto}
          />
        ))}
      </ul>
    </div>
  );
}

/** Passo cujo estado inicial acompanha o "expandir tudo". */
function PassoControlado({
  passo,
  inicialmenteAberto,
}: {
  passo: PassoMemoria;
  inicialmenteAberto: boolean;
}) {
  if (!inicialmenteAberto) return <Passo passo={passo} />;
  return <PassoAberto passo={passo} />;
}

function PassoAberto({ passo }: { passo: PassoMemoria }) {
  return (
    <li className="border-b border-borda/60 px-5 py-3 last:border-0">
      <div className="flex items-baseline gap-3">
        <span className="numerico w-6 shrink-0 text-xs text-texto-tenue">
          {passo.ordem}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{passo.rotulo}</p>
          <p className="font-mono text-xs text-texto-tenue">{passo.formula}</p>
          <dl className="mt-2 grid gap-x-6 gap-y-1 sm:grid-cols-2">
            {Object.entries(passo.entradas).map(([chave, valor]) => (
              <div key={chave} className="flex justify-between gap-4 text-xs">
                <dt className="text-texto-suave">{chave}</dt>
                <dd className="numerico">{valor}</dd>
              </div>
            ))}
          </dl>
          {passo.alerta ? (
            <p className="mt-2 rounded-md border border-atencao/30 bg-atencao-fundo px-3 py-2 text-xs">
              {passo.alerta}
            </p>
          ) : null}
        </div>
        <span className="numerico shrink-0 text-sm font-medium">
          {numero(passo.resultado, 4)}
          <span className="ml-1 text-xs font-normal text-texto-tenue">
            {passo.unidade}
          </span>
        </span>
      </div>
    </li>
  );
}
