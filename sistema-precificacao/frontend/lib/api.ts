/**
 * Cliente HTTP da API.
 *
 * Traduz o corpo de erro do backend (`{erro, mensagem, bloqueante}`) em uma
 * excecao tipada, para que a interface possa distinguir bloqueio de regra de
 * negocio -- que merece explicacao -- de falha tecnica.
 */

import type { Pagina } from "./tipos";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ErroApi extends Error {
  constructor(
    readonly status: number,
    readonly codigo: string,
    mensagem: string,
    readonly bloqueante: boolean = false,
  ) {
    super(mensagem);
    this.name = "ErroApi";
  }

  /** Bloqueio de regra de negocio: 409 e 422 carregam causa identificada. */
  get eRegraDeNegocio() {
    return this.status === 409 || this.status === 422;
  }
}

interface Opcoes extends RequestInit {
  /** Segundos de cache do Next; 0 desativa. */
  revalidar?: number;
}

async function requisitar<T>(caminho: string, opcoes: Opcoes = {}): Promise<T> {
  const { revalidar, ...resto } = opcoes;

  let resposta: Response;
  try {
    resposta = await fetch(`${BASE}${caminho}`, {
      ...resto,
      headers: { "Content-Type": "application/json", ...resto.headers },
      next: revalidar === undefined ? { revalidate: 0 } : { revalidate: revalidar },
    });
  } catch {
    throw new ErroApi(
      0,
      "API_INDISPONIVEL",
      `Nao foi possivel falar com a API em ${BASE}. Verifique se o backend esta no ar.`,
    );
  }

  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null);
    throw new ErroApi(
      resposta.status,
      corpo?.erro ?? "ERRO_DESCONHECIDO",
      corpo?.mensagem ?? corpo?.detail ?? resposta.statusText,
      Boolean(corpo?.bloqueante),
    );
  }

  if (resposta.status === 204) return undefined as T;
  return (await resposta.json()) as T;
}

export const api = {
  get: <T>(caminho: string, opcoes?: Opcoes) => requisitar<T>(caminho, opcoes),

  post: <T>(caminho: string, corpo: unknown, opcoes?: Opcoes) =>
    requisitar<T>(caminho, { ...opcoes, method: "POST", body: JSON.stringify(corpo) }),

  patch: <T>(caminho: string, corpo: unknown, opcoes?: Opcoes) =>
    requisitar<T>(caminho, { ...opcoes, method: "PATCH", body: JSON.stringify(corpo) }),

  /** Atalho para endpoints paginados. */
  lista: <T>(caminho: string, opcoes?: Opcoes) => requisitar<Pagina<T>>(caminho, opcoes),
};

export const BASE_API = BASE;
