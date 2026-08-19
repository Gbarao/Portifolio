/**
 * Apresentacao de falhas da API.
 *
 * Bloqueio de regra de negocio (409/422) merece explicacao completa: e o
 * sistema funcionando como a especificacao manda. Falha tecnica merece
 * instrucao de recuperacao.
 */

import { PlugZap, ShieldAlert } from "lucide-react";

import { Alerta } from "@/components/dominio/indicadores";
import { ErroApi } from "@/lib/api";

export function ErroDeCarregamento({ erro }: { erro: unknown }) {
  if (erro instanceof ErroApi && erro.codigo === "API_INDISPONIVEL") {
    return (
      <Alerta severidade="critico" titulo="API fora do ar">
        <p>{erro.message}</p>
        <p className="mt-2 font-mono text-xs">
          cd backend && .venv/bin/uvicorn app.api.main:app --reload
        </p>
      </Alerta>
    );
  }

  if (erro instanceof ErroApi && erro.eRegraDeNegocio) {
    return (
      <Alerta severidade="atencao" titulo={`Bloqueio: ${erro.codigo}`}>
        <p>{erro.message}</p>
        <p className="mt-2 text-xs text-texto-suave">
          Isto não é uma falha do sistema: é uma regra da especificação impedindo
          um cálculo que seria inválido.
        </p>
      </Alerta>
    );
  }

  const mensagem = erro instanceof Error ? erro.message : String(erro);
  return (
    <Alerta severidade="critico" titulo="Não foi possível carregar">
      {mensagem}
    </Alerta>
  );
}

export function IconeConexao() {
  return <PlugZap className="size-4" aria-hidden />;
}

export function IconeBloqueio() {
  return <ShieldAlert className="size-4" aria-hidden />;
}
