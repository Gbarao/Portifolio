"use client";

/**
 * Busca de dados no navegador.
 *
 * As telas passaram a carregar do lado do cliente para que a interface possa
 * ser exportada como arquivos estaticos e servida pelo proprio servidor
 * Python. Isso elimina o Node.js do uso diario: quem usa o sistema roda um
 * programa so.
 */

import * as React from "react";

import { ErroApi, api } from "@/lib/api";

export interface EstadoRequisicao<T> {
  dados: T | null;
  erro: unknown;
  carregando: boolean;
  recarregar: () => void;
}

export function useApi<T>(caminho: string | null): EstadoRequisicao<T> {
  const [dados, setDados] = React.useState<T | null>(null);
  const [erro, setErro] = React.useState<unknown>(null);
  const [carregando, setCarregando] = React.useState(true);
  const [gatilho, setGatilho] = React.useState(0);

  React.useEffect(() => {
    if (caminho === null) {
      setCarregando(false);
      return;
    }

    let cancelado = false;
    setCarregando(true);

    api
      .get<T>(caminho)
      .then((resposta) => {
        if (!cancelado) {
          setDados(resposta);
          setErro(null);
        }
      })
      .catch((e) => {
        if (!cancelado) {
          setErro(e instanceof ErroApi ? e : new Error(String(e)));
          setDados(null);
        }
      })
      .finally(() => {
        if (!cancelado) setCarregando(false);
      });

    return () => {
      cancelado = true;
    };
  }, [caminho, gatilho]);

  return {
    dados,
    erro,
    carregando,
    recarregar: () => setGatilho((g) => g + 1),
  };
}

/** Atalho para endpoints paginados, devolvendo direto a lista. */
export function useLista<T>(caminho: string): EstadoRequisicao<T[]> {
  const estado = useApi<{ itens: T[] }>(caminho);
  return {
    ...estado,
    dados: estado.dados?.itens ?? null,
  };
}
